from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .config import as_dict, load_settings
from .agent_context import auto_reuse as auto_reuse_agent
from .agent_context import candidates as reuse_candidates
from .agent_context import complete_task as complete_agent_task
from .agent_context import read as read_agent_context
from .agent_context import request_reuse as reuse_agent
from .doctor import run_doctor
from .evaluation import validate_evaluation
from .eval.reporting import build_report, render_markdown
from .eval.oracles import resolve_oracle
from .eval.scoring import score_trial
from .eval.compare import compare_trials
from .eval.trials import collect_trials, load_trials
from .eval.assessment import assess_exported_runs
from .errors import InteractiveCapacityError, WorkflowError
from .ledger import build_ledger, render_ledger
from .lifecycle import record as record_lifecycle
from .inspect_adapter import build_task as build_inspect_task
from .inspect_adapter import run_inspect
from .integrations.swebench import write_prediction
from .manifests import validate_pack, write_checksum_manifest
from .path import absolute_path
from .pack import archive as archive_pack
from .pack import scaffold as scaffold_pack
from .receipts import verify_seal_details
from .sessions import interrupt as interrupt_session
from .sessions import kill as kill_session
from .sessions import launch as launch_session
from .sessions import acknowledge as acknowledge_message
from .sessions import progress as record_progress
from .sessions import observe
from .sessions import restart as restart_session
from .sessions import steer as steer_session
from .sessions import terminate as terminate_session
from .sessions import wait_for_message
from .state import list_statuses, read_status, repair_status, runs_root
from .tmux import attach as attach_tmux
from .util import atomic_write_json, expand_path, read_json
from .scheduler import SchedulerService
from .workflow import snapshot_sha256
from .workflow_service import WorkflowService
from .workflow_templates import AUTHORIZED_TEMPLATES, expand_workflow_template
from .worktrees import create as create_worktree
from .worktrees import list_worktrees
from .worktrees import remove as remove_worktree


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def _verified_receipt_hash(run: Path) -> str:
    """Return the digest of the exact receipt verified from stable bytes."""
    _, digest = verify_seal_details(run)
    return digest


def _print_table(
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str]],
) -> None:
    if not rows:
        print("No records.")
        return
    widths = {key: len(title) for key, title in columns}
    for row in rows:
        for key, _ in columns:
            widths[key] = max(widths[key], len(str(row.get(key, ""))))
    print("  ".join(title.ljust(widths[key]) for key, title in columns))
    print("  ".join("-" * widths[key] for key, _ in columns))
    for row in rows:
        print("  ".join(str(row.get(key, "")).ljust(widths[key]) for key, _ in columns))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-workflow")
    parser.add_argument("--version", action="version", version="%(prog)s 0.2.3")
    parser.add_argument("--config", type=Path, help="override config.toml path")
    parser.add_argument(
        "--json",
        action="store_true",
        help="machine-readable output where supported",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor", help="check environment and configuration")
    workflow = commands.add_parser("workflow", help="workflow scheduler commands")
    workflow_commands = workflow.add_subparsers(dest="workflow_command", required=True)
    wf_validate = workflow_commands.add_parser("validate", help="validate a workflow snapshot")
    wf_validate.add_argument("snapshot", type=Path)
    wf_start = workflow_commands.add_parser("start", help="start a workflow from a snapshot")
    wf_start.add_argument("run_dir", type=Path)
    wf_start.add_argument("snapshot", type=Path)
    wf_status = workflow_commands.add_parser("status", help="show workflow status")
    wf_status.add_argument("run_dir", type=Path)
    wf_status.add_argument("snapshot", type=Path)
    wf_resume = workflow_commands.add_parser("resume", help="resume a workflow after restart")
    wf_resume.add_argument("run_dir", type=Path)
    wf_resume.add_argument("snapshot", type=Path)
    wf_seal = workflow_commands.add_parser("seal", help="seal terminal workflow evidence")
    wf_seal.add_argument("run_dir", type=Path)
    wf_seal.add_argument("snapshot", type=Path)
    wf_verify = workflow_commands.add_parser("verify", help="verify a workflow receipt")
    wf_verify.add_argument("run_dir", type=Path)
    wf_verify.add_argument("snapshot", type=Path)
    wf_template = workflow_commands.add_parser("template", help="expand an authorized workflow template")
    wf_template.add_argument("template", choices=AUTHORIZED_TEMPLATES)
    wf_template.add_argument("spec", type=Path, help="JSON template request")
    wf_template.add_argument("--output", type=Path, required=True)

    completion = commands.add_parser(
        "completion", help="generate shell completion from the live parser"
    )
    completion.add_argument("shell", choices=("bash", "zsh", "tcsh"))

    config = commands.add_parser("config", help="configuration commands")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("show", help="show resolved configuration")

    worktree = commands.add_parser("worktree", help="Git worktree commands")
    worktree_commands = worktree.add_subparsers(dest="worktree_command", required=True)
    create = worktree_commands.add_parser(
        "create", help="create an isolated ticket worktree"
    )
    create.add_argument("repo", type=Path)
    create.add_argument("ticket_id")
    create.add_argument("base_ref")
    create.add_argument("--dest", type=Path)
    create.add_argument("--branch")
    create.add_argument("--allow-dirty", action="store_true")

    remove = worktree_commands.add_parser("remove", help="remove a worktree")
    remove.add_argument("repo", type=Path)
    remove.add_argument("worktree", type=Path)
    remove.add_argument("--force", action="store_true")
    remove.add_argument("--delete-branch", action="store_true")

    listing = worktree_commands.add_parser("list", help="list repository worktrees")
    listing.add_argument("repo", type=Path)

    launch = commands.add_parser(
        "launch", help="launch a prompt in a fresh tmux session"
    )
    launch.add_argument("session_id")
    launch.add_argument("workdir", type=Path)
    launch.add_argument("prompt", type=Path)
    launch.add_argument("--ticket")
    launch.add_argument("--tier", choices=("low", "medium", "high", "critical"))
    launch.add_argument("--pack")
    launch.add_argument("--job", type=Path, help="validated native JSON job in the prompt pack")
    launch.add_argument("--executor")
    launch.add_argument("--agent-name", help="preferred configured agent/pane name")
    launch.add_argument("--agent-class", help="configured agent work classification")
    launch.add_argument("--model", help="configured executor model")
    launch.add_argument(
        "--allow-no-go-model",
        action="store_true",
        help="explicitly authorize a configured no-go model for this run",
    )
    launch.add_argument("--evaluation", type=Path)
    launch.add_argument(
        "--structured",
        action="store_true",
        help="request structured JSON events from known executors",
    )
    launch.add_argument(
        "--interactive",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="run a known executor TUI attached to a tmux PTY",
    )
    launch.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow launching from a Git worktree with uncommitted changes",
    )
    launch.add_argument(
        "--pane-limit-action",
        choices=("prompt", "close-idle", "non-interactive", "cancel"),
        default="prompt",
        help="action when the interactive pane cap is reached",
    )

    commands.add_parser("list", help="list delegation runs")

    assess = commands.add_parser("assess-sealed-runs", help="assess exported sealed-run evidence without inventing unavailable evaluation results")
    assess.add_argument("root", type=Path)
    assess.add_argument("--output", type=Path)

    ledger = commands.add_parser("ledger", help="render a pack run ledger")
    ledger.add_argument("pack", type=Path)
    ledger.add_argument("--runs-root", type=Path)
    ledger.add_argument("--output", type=Path)

    status = commands.add_parser("status", help="inspect a delegation")
    status.add_argument("session_id")
    status.add_argument("--capture", type=int, nargs="?", const=-1, default=0)

    repair = commands.add_parser(
        "repair", help="rebuild a mutable status projection from run authority"
    )
    repair.add_argument("session_id")

    attach = commands.add_parser("attach", help="foreground a delegation")
    attach.add_argument("session_id")

    tail = commands.add_parser("tail", help="follow a delegation log")
    tail.add_argument("session_id")
    tail.add_argument("--lines", type=int, default=50)

    steer = commands.add_parser(
        "steer", help="persist a parent-to-child steering request"
    )
    steer.add_argument("session_id")
    steer.add_argument("content")
    steer.add_argument("--actor", required=True)

    progress = commands.add_parser(
        "progress", help="persist a child-to-parent progress update"
    )
    progress.add_argument("session_id")
    progress.add_argument("content")
    progress.add_argument("--actor", required=True)

    acknowledge = commands.add_parser(
        "ack", help="record application of a steering request"
    )
    acknowledge.add_argument("session_id")
    acknowledge.add_argument("correlation_id")
    acknowledge.add_argument("content")
    acknowledge.add_argument("--actor", required=True)

    watch = commands.add_parser(
        "watch", help="block until a durable session message arrives"
    )
    watch.add_argument("session_id")
    watch.add_argument("--after", type=int, default=0)
    watch.add_argument("--timeout", type=float)

    interrupt = commands.add_parser(
        "interrupt", help="send Ctrl-C without deleting the session"
    )
    interrupt.add_argument("session_id")

    terminate = commands.add_parser(
        "terminate", help="interrupt, wait, then kill tmux if needed"
    )
    terminate.add_argument("session_id")
    terminate.add_argument("--grace-seconds", type=int, default=8)

    kill = commands.add_parser(
        "kill", help="immediately kill tmux and preserve evidence"
    )
    kill.add_argument("session_id")

    restart = commands.add_parser(
        "restart", help="restart a saved delegation in a new session"
    )
    restart.add_argument("session_id")
    restart.add_argument("--new-session")

    agent = commands.add_parser("agent", help="interactive agent context and reuse")
    agent_commands = agent.add_subparsers(dest="agent_command", required=True)
    agent_context = agent_commands.add_parser("context", help="show durable agent context")
    agent_context.add_argument("session_id")
    agent_complete = agent_commands.add_parser(
        "task-complete", help="mark the current interactive assignment complete"
    )
    agent_complete.add_argument("session_id")
    agent_complete.add_argument("--actor", required=True)
    agent_complete.add_argument("--summary", required=True)
    agent_complete.add_argument("--tag", action="append", default=[])
    agent_complete.add_argument("--file", action="append", default=[])
    agent_candidates = agent_commands.add_parser(
        "candidates", help="rank reusable agents for a worktree"
    )
    agent_candidates.add_argument("workdir", type=Path)
    agent_candidates.add_argument("--ticket")
    agent_candidates.add_argument("--pack")
    agent_candidates.add_argument("--retry-of")
    agent_candidates.add_argument("--agent-class")
    agent_candidates.add_argument("--tag", action="append", default=[])
    agent_reuse = agent_commands.add_parser(
        "reuse", help="request a new assignment from one reusable agent"
    )
    agent_reuse.add_argument("session_id")
    agent_reuse.add_argument("prompt", type=Path)
    agent_reuse.add_argument("--actor", required=True)
    agent_reuse.add_argument("--ticket")
    agent_reuse.add_argument("--pack")
    agent_reuse.add_argument("--retry-of")
    agent_reuse.add_argument("--tag", action="append", default=[])
    agent_auto = agent_commands.add_parser(
        "auto-reuse", help="reuse only an exact ticket or retry-lineage match"
    )
    agent_auto.add_argument("workdir", type=Path)
    agent_auto.add_argument("prompt", type=Path)
    agent_auto.add_argument("--actor", required=True)
    agent_auto.add_argument("--ticket")
    agent_auto.add_argument("--pack")
    agent_auto.add_argument("--retry-of")
    agent_auto.add_argument("--agent-class")
    agent_auto.add_argument("--tag", action="append", default=[])

    for name in ("review", "accept", "reject"):
        lifecycle = commands.add_parser(name, help=f"record {name} disposition")
        lifecycle.add_argument("session_id")
        lifecycle.add_argument("--actor", required=True)
        lifecycle.add_argument("--reason", required=True)
        if name == "accept":
            lifecycle.add_argument("--revision", required=True)

    evaluation = commands.add_parser("eval", help="evaluation commands")
    evaluation_commands = evaluation.add_subparsers(dest="eval_command", required=True)
    eval_validate = evaluation_commands.add_parser(
        "validate", help="validate an evaluation plan"
    )
    eval_validate.add_argument("source", type=Path)
    eval_validate.add_argument("--pack", type=Path)
    eval_score = evaluation_commands.add_parser(
        "score", help="score an already sealed run without model calls"
    )
    eval_score.add_argument("run")
    eval_score.add_argument("--output-dir", type=Path)
    eval_score.add_argument("--oracle-root", type=Path)
    eval_report = evaluation_commands.add_parser(
        "report", help="render a report from sealed local receipts"
    )
    eval_report.add_argument("run")
    eval_report.add_argument("--format", choices=("json", "markdown"), default="markdown")
    eval_report.add_argument("--output", type=Path)
    eval_inspect = evaluation_commands.add_parser(
        "inspect", help="run one prompt through the pinned Inspect SWE adapter"
    )
    eval_inspect.add_argument("prompt", type=Path)
    eval_inspect.add_argument("--executor", choices=("codex", "claude"), required=True)
    eval_inspect.add_argument("--model", required=True)
    eval_inspect.add_argument("--dockerfile", type=Path, required=True)
    eval_inspect.add_argument("--log-dir", type=Path, required=True)
    eval_swebench = evaluation_commands.add_parser(
        "swebench-prediction", help="write official SWE-bench prediction JSONL"
    )
    eval_swebench.add_argument("run")
    eval_swebench.add_argument("--instance-id", required=True)
    eval_swebench.add_argument("--model", required=True)
    eval_swebench.add_argument("--output", type=Path, required=True)
    eval_collect = evaluation_commands.add_parser(
        "collect", help="write immutable trial evidence from sealed runs"
    )
    eval_collect.add_argument("--output", type=Path, required=True)
    eval_collect.add_argument("runs", nargs="+", type=Path)
    eval_compare = evaluation_commands.add_parser(
        "compare", help="compare explicit baseline and candidate evidence files"
    )
    eval_compare.add_argument("baseline", type=Path)
    eval_compare.add_argument("candidate", type=Path)
    eval_compare.add_argument("--output", type=Path, required=True)

    pack = commands.add_parser("pack", help="prompt-pack commands")
    pack_commands = pack.add_subparsers(dest="pack_command", required=True)

    scaffold = pack_commands.add_parser(
        "scaffold", help="create a new prompt-pack skeleton"
    )
    scaffold.add_argument("destination", type=Path)
    scaffold.add_argument("--phases", type=int, default=3)
    scaffold.add_argument("--name")

    validate = pack_commands.add_parser(
        "validate", help="validate pack structure and contracts"
    )
    validate.add_argument("source", type=Path)
    validate.add_argument(
        "--verify-checksums",
        action="store_true",
        help="verify an optional MANIFEST.sha256 before transfer",
    )

    checksum = pack_commands.add_parser("checksum", help="write MANIFEST.sha256")
    checksum.add_argument("source", type=Path)

    archive = pack_commands.add_parser(
        "archive", help="validate and create a deterministic tar.zst"
    )
    archive.add_argument("source", type=Path)
    archive.add_argument("output", type=Path)

    return parser


def _parse_args(
    parser: argparse.ArgumentParser,
    argv: list[str] | None,
) -> argparse.Namespace:
    raw = list(sys.argv[1:] if argv is None else argv)
    explicit_command: list[str] | None = None
    if "--" in raw:
        separator = raw.index("--")
        if "launch" not in raw[:separator]:
            parser.error("-- COMMAND is only supported by launch")
        explicit_command = raw[separator + 1 :]
        raw = raw[:separator]
        if not explicit_command:
            parser.error("missing explicit command after --")
    # argparse normally requires global options before the subcommand.  The
    # workflow CLI accepts --json and --config in either position because the
    # documented/operator-friendly form is often `command --json`.  Only the
    # portion before an explicit launch `-- COMMAND...` separator is normalized.
    normalized_globals: list[str] = []
    normalized_rest: list[str] = []
    index = 0
    while index < len(raw):
        token = raw[index]
        if token == "--json":
            normalized_globals.append(token)
            index += 1
            continue
        if token == "--config":
            if index + 1 >= len(raw):
                parser.error("argument --config: expected one argument")
            normalized_globals.extend([token, raw[index + 1]])
            index += 2
            continue
        if token.startswith("--config="):
            normalized_globals.append(token)
            index += 1
            continue
        normalized_rest.append(token)
        index += 1

    args = parser.parse_args(normalized_globals + normalized_rest)
    setattr(args, "explicit_command", explicit_command)
    return args


def _print_mapping(data: dict[str, Any]) -> None:
    for key, value in data.items():
        if key == "capture" and value:
            print("--- terminal capture ---")
            print(str(value).rstrip())
        elif isinstance(value, (dict, list)):
            print(f"{key}: {json.dumps(value, sort_keys=True)}")
        else:
            print(f"{key}: {value}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = _parse_args(parser, argv)
    try:
        settings = load_settings(args.config)
        data: Any

        if args.command == "doctor":
            data = run_doctor(settings)
        elif args.command == "completion":
            try:
                import shtab
            except ModuleNotFoundError as exc:
                raise WorkflowError(
                    "shell completion requires: pip install 'agent-workflow[completion]'"
                ) from exc
            print(shtab.complete(build_parser(), shell=args.shell), end="")
            return 0
        elif args.command == "config":
            data = as_dict(settings)
        elif args.command == "worktree":
            if args.worktree_command == "create":
                data = create_worktree(
                    settings,
                    repo=args.repo,
                    ticket_id=args.ticket_id,
                    base_ref=args.base_ref,
                    destination=args.dest,
                    branch=args.branch,
                    allow_dirty=args.allow_dirty,
                )
            elif args.worktree_command == "remove":
                data = remove_worktree(
                    args.repo,
                    args.worktree,
                    force=args.force,
                    delete_branch=args.delete_branch,
                )
            else:
                data = list_worktrees(args.repo)
        elif args.command == "launch":
            interactive_override = args.interactive
            while True:
                try:
                    data = launch_session(
                        settings,
                        session_id=args.session_id,
                        workdir=args.workdir,
                        prompt_path=args.prompt,
                        executor=args.executor,
                        agent_name=args.agent_name,
                        agent_class=args.agent_class,
                        model=args.model,
                        allow_no_go_model=args.allow_no_go_model,
                        explicit_command=args.explicit_command,
                        ticket_id=args.ticket,
                        tier=args.tier,
                        pack_id=args.pack,
                        job_path=args.job,
                        allow_dirty=args.allow_dirty,
                        structured=args.structured,
                        interactive=interactive_override,
                        evaluation_path=args.evaluation,
                    )
                    break
                except InteractiveCapacityError as exc:
                    action = args.pane_limit_action
                    if action == "prompt":
                        if args.json or not sys.stdin.isatty():
                            raise
                        idle = ", ".join(
                            f"{item.get('agent_name') or item['session_id']} ({item['state']})"
                            for item in exc.idle_sessions
                        ) or "none"
                        print(
                            f"Interactive pane limit reached ({exc.count}/{exc.maximum})."
                        )
                        print(f"Idle interactive panes: {idle}")
                        close_label = (
                            "[c] close idle pane(s) and continue, "
                            if len(exc.idle_sessions) >= exc.required_closures
                            else ""
                        )
                        noninteractive_label = (
                            "[n] launch as a detached non-interactive task, "
                            if args.explicit_command is None
                            else ""
                        )
                        choice = input(close_label + noninteractive_label + "[q] cancel: ").strip().lower()
                        action = {"c": "close-idle", "n": "non-interactive", "q": "cancel"}.get(choice, "cancel")
                    if action == "close-idle":
                        if len(exc.idle_sessions) < exc.required_closures:
                            raise WorkflowError(
                                "not enough explicitly idle interactive panes to close"
                            )
                        for item in exc.idle_sessions[: exc.required_closures]:
                            kill_session(settings, str(item["session_id"]))
                        continue
                    if action == "non-interactive":
                        if args.explicit_command is not None:
                            raise WorkflowError(
                                "cannot convert an explicit command into a non-interactive executor task"
                            )
                        interactive_override = False
                        continue
                    raise WorkflowError("interactive launch cancelled at pane limit")
        elif args.command == "list":
            rows: list[dict[str, Any]] = []
            for item in list_statuses(settings):
                session_id = str(item.get("session_id", ""))
                try:
                    rows.append(observe(settings, session_id))
                except WorkflowError:
                    rows.append(item)
            if args.json:
                _print_json(rows)
            else:
                _print_table(
                    rows,
                    [
                        ("session_id", "SESSION"),
                        ("ticket_id", "TICKET"),
                        ("status", "DURABLE"),
                        ("observed_state", "OBSERVED"),
                        ("branch", "BRANCH"),
                    ],
                )
            return 0
        elif args.command == "workflow":
            if args.workflow_command == "template":
                spec = read_json(expand_path(args.spec))
                snapshot = expand_workflow_template(
                    args.template,
                    workflow_id=str(spec.get("workflow_id", "")),
                    pack_id=str(spec.get("pack_id", "")),
                    pack_manifest_sha256=str(spec.get("pack_manifest_sha256", "")),
                    parameters=spec.get("parameters", {}),
                )
                output = expand_path(args.output)
                atomic_write_json(output, snapshot)
                data = {"output": str(output), "snapshot_sha256": snapshot_sha256(snapshot)}
                if args.json:
                    _print_json(data)
                else:
                    print(output)
                return 0
            run_dir = expand_path(getattr(args, "run_dir", Path.cwd()))
            service = WorkflowService(
                scheduler=SchedulerService(
                    settings=settings,
                    run_dir=run_dir,
                    workdir=run_dir,
                )
            )
            if args.workflow_command == "validate":
                data = service.validate(args.snapshot)
            elif args.workflow_command == "start":
                data = service.start(args.snapshot)
            elif args.workflow_command == "status":
                data = service.status(args.snapshot)
            elif args.workflow_command == "resume":
                data = service.resume(args.snapshot)
            elif args.workflow_command == "seal":
                data = service.seal(args.snapshot)
            else:
                data = service.verify(args.snapshot)
        elif args.command == "assess-sealed-runs":
            data = assess_exported_runs(expand_path(args.root))
            if args.output:
                output = expand_path(args.output)
                atomic_write_json(output, data)
            _print_json(data)
            return 0
        elif args.command == "ledger":
            value = build_ledger(
                expand_path(args.pack),
                expand_path(args.runs_root) if args.runs_root else runs_root(settings),
            )
            rendered = json.dumps(value, indent=2, sort_keys=True) + "\n" if args.json else render_ledger(value)
            if args.output:
                output = expand_path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered, encoding="utf-8")
                data = {"output": str(output), "row_count": len(value["rows"])}
            else:
                print(rendered, end="")
                return 0
        elif args.command == "status":
            capture_lines = (
                settings.capture_lines if args.capture == -1 else args.capture
            )
            data = observe(settings, args.session_id, capture_lines)
        elif args.command == "repair":
            data = repair_status(settings, args.session_id)
        elif args.command == "attach":
            read_status(settings, args.session_id)
            attach_tmux(args.session_id)
            return 0
        elif args.command == "tail":
            status_data = read_status(settings, args.session_id)
            log = Path(str(status_data["log_path"]))
            os.execvp("tail", ["tail", "-n", str(args.lines), "-f", str(log)])
        elif args.command == "steer":
            data = steer_session(
                settings, args.session_id, actor=args.actor, content=args.content
            )
        elif args.command == "progress":
            data = record_progress(
                settings, args.session_id, actor=args.actor, content=args.content
            )
        elif args.command == "ack":
            data = acknowledge_message(
                settings,
                args.session_id,
                actor=args.actor,
                content=args.content,
                correlation_id=args.correlation_id,
            )
        elif args.command == "watch":
            data = wait_for_message(
                settings,
                args.session_id,
                after_sequence=args.after,
                timeout_seconds=args.timeout,
            )
        elif args.command == "interrupt":
            data = interrupt_session(settings, args.session_id)
        elif args.command == "terminate":
            data = terminate_session(settings, args.session_id, args.grace_seconds)
        elif args.command == "kill":
            data = kill_session(settings, args.session_id)
        elif args.command == "restart":
            data = restart_session(settings, args.session_id, args.new_session)
        elif args.command == "agent":
            if args.agent_command == "context":
                data = read_agent_context(settings, args.session_id)
            elif args.agent_command == "task-complete":
                data = complete_agent_task(
                    settings, args.session_id, actor=args.actor,
                    summary=args.summary, tags=args.tag, files=args.file,
                )
            elif args.agent_command == "candidates":
                data = reuse_candidates(
                    settings, workdir=args.workdir, ticket_id=args.ticket,
                    pack_id=args.pack, retry_of=args.retry_of,
                    agent_class=args.agent_class, tags=args.tag,
                )
            elif args.agent_command == "reuse":
                data = reuse_agent(
                    settings, args.session_id, prompt_path=args.prompt,
                    actor=args.actor, ticket_id=args.ticket, pack_id=args.pack,
                    retry_of=args.retry_of, tags=args.tag,
                )
            else:
                data = auto_reuse_agent(
                    settings, workdir=args.workdir, prompt_path=args.prompt,
                    actor=args.actor, ticket_id=args.ticket, pack_id=args.pack,
                    retry_of=args.retry_of, agent_class=args.agent_class,
                    tags=args.tag,
                )
        elif args.command in {"review", "accept", "reject"}:
            action = "reviewed" if args.command == "review" else (
                "accepted" if args.command == "accept" else "rejected"
            )
            data = record_lifecycle(
                settings,
                args.session_id,
                action=action,
                actor=args.actor,
                reason=args.reason,
                revision=args.revision if args.command == "accept" else None,
            )
        elif args.command == "eval":
            if args.eval_command == "validate":
                pack_root = expand_path(args.pack) if args.pack else None
                plan = validate_evaluation(
                    expand_path(args.source),
                    pack_root=pack_root,
                )
                if pack_root is not None:
                    report = validate_pack(pack_root, verify_checksums=False)
                    if not report.ok:
                        raise WorkflowError(
                            "evaluation pack validation failed: "
                            + "; ".join(report.errors)
                        )
                data = {
                    "path": str(plan.path),
                    "schema": plan.data["schema"],
                    "sha256": plan.sha256,
                    "task_ids": list(plan.task_ids),
                }
            elif args.eval_command in {"score", "report"}:
                candidate = expand_path(Path(args.run))
                evaluation_run = (
                    candidate
                    if candidate.is_dir()
                    else runs_root(settings) / args.run
                )
                if not evaluation_run.is_dir():
                    raise WorkflowError(f"run not found: {args.run}")
                if args.eval_command == "score":
                    output_dir = (
                        expand_path(args.output_dir)
                        if args.output_dir
                        else evaluation_run / "scores"
                    )
                    oracle = None
                    canary = None
                    final_receipt, receipt_digest = verify_seal_details(evaluation_run)
                    from .eval.scoring import evaluation_policy_for_run

                    policy = evaluation_policy_for_run(evaluation_run, final_receipt)
                    refs = policy.get("oracle_refs", {})
                    ticket = policy.get("ticket_id")
                    reference = refs.get(ticket) if isinstance(refs, dict) else None
                    if isinstance(reference, dict):
                        configured_root = args.oracle_root or os.environ.get(
                            "AGENT_WORKFLOW_ORACLE_ROOT"
                        )
                        if not configured_root:
                            raise WorkflowError(
                                "evaluation requires --oracle-root or AGENT_WORKFLOW_ORACLE_ROOT"
                            )
                        verified = resolve_oracle(
                            str(reference["id"]),
                            str(reference["sha256"]),
                            expand_path(Path(configured_root)),
                        )
                        canary_path = verified.root / "canary.txt"
                        if not canary_path.is_file():
                            raise WorkflowError(
                                f"oracle canary is missing: {canary_path}"
                            )
                        oracle = verified.manifest
                        canary = canary_path.read_bytes()
                    data = score_trial(
                        evaluation_run,
                        output_dir=output_dir,
                        oracle=oracle,
                        oracle_canary=canary,
                        expected_final_receipt_sha256=receipt_digest,
                    )
                    atomic_write_json(output_dir / "score-set.json", data)
                else:
                    _receipt, receipt_digest = verify_seal_details(evaluation_run)
                    report = build_report(
                        evaluation_run,
                        expected_final_receipt_sha256=receipt_digest,
                    )
                    rendered = (
                        json.dumps(report, indent=2, sort_keys=True) + "\n"
                        if args.format == "json"
                        else render_markdown(report)
                    )
                    if args.output:
                        output = expand_path(args.output)
                        output.parent.mkdir(parents=True, exist_ok=True)
                        output.write_text(rendered, encoding="utf-8")
                        data = {"output": str(output), "format": args.format}
                    else:
                        print(rendered, end="")
                        return 0
            elif args.eval_command == "inspect":
                prompt_path = expand_path(args.prompt)
                if not prompt_path.is_file():
                    raise WorkflowError(f"prompt not found: {prompt_path}")
                task = build_inspect_task(
                    prompt=prompt_path.read_text(encoding="utf-8"),
                    executor=args.executor,
                    sample_id=prompt_path.stem,
                    dockerfile=expand_path(args.dockerfile),
                )
                data = {
                    "logs": run_inspect(
                        task,
                        model=args.model,
                        log_dir=expand_path(args.log_dir),
                    )
                }
            elif args.eval_command == "swebench-prediction":
                candidate = expand_path(Path(args.run))
                evaluation_run = (
                    candidate
                    if candidate.is_dir()
                    else runs_root(settings) / args.run
                )
                _receipt, receipt_digest = verify_seal_details(
                    evaluation_run,
                )
                output = write_prediction(
                    instance_id=args.instance_id,
                    model_name_or_path=args.model,
                    patch_path=evaluation_run / "patch.diff",
                    output=expand_path(args.output),
                    final_receipt_sha256=receipt_digest,
                )
                data = {"output": str(output)}
            elif args.eval_command == "collect":
                output = expand_path(args.output)
                evidence = collect_trials(
                    [expand_path(path) for path in args.runs], output
                )
                data = {"output": str(output), "trials": len(evidence["trials"])}
            elif args.eval_command == "compare":
                baseline, candidate = (
                    load_trials(expand_path(args.baseline)),
                    load_trials(expand_path(args.candidate)),
                )
                currencies = {
                    trial.get("currency")
                    for trial in [*baseline, *candidate]
                    if trial.get("cost") is not None
                }
                if len(currencies) > 1:
                    raise WorkflowError("cannot compare evidence with different currencies")
                output = expand_path(args.output)
                data = compare_trials(baseline, candidate)
                atomic_write_json(output, data)
                data = {"output": str(output), **data}
        elif args.command == "pack":
            if args.pack_command == "scaffold":
                data = scaffold_pack(args.destination, args.phases, args.name)
            elif args.pack_command == "validate":
                report = validate_pack(
                    absolute_path(args.source),
                    verify_checksums=args.verify_checksums,
                )
                data = report.as_dict()
                if args.json:
                    _print_json(data)
                else:
                    print(f"pack: {report.root}")
                    print(
                        f"phases: {report.phases}; tasks: {report.tasks}; "
                        f"valid: {report.ok}"
                    )
                    for warning in report.warnings:
                        print(f"warning: {warning}")
                    for error in report.errors:
                        print(f"error: {error}", file=sys.stderr)
                return 0 if report.ok else 1
            elif args.pack_command == "checksum":
                path = write_checksum_manifest(absolute_path(args.source))
                data = {"manifest": str(path)}
            else:
                data = archive_pack(settings, args.source, args.output)
        else:
            parser.error("unhandled command")
            return 2

        if args.json:
            _print_json(data)
        elif isinstance(data, dict):
            _print_mapping(data)
        else:
            _print_json(data)
        return 0
    except InteractiveCapacityError as exc:
        if args.json:
            _print_json(exc.as_dict())
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    except WorkflowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
