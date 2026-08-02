from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .benchmarking import (
    attest_benchmark_runtime,
    benchmark_readiness,
    check_benchmark_auth,
    cleanup_benchmark,
    consolidate_benchmark,
    create_fixture as create_benchmark_fixture,
    create_plan as create_benchmark_plan,
    export_builtin_suite as export_benchmark_suite,
    prepare_or_submit_review as benchmark_review,
    render_benchmark_report as render_comparative_benchmark_report,
    resume_benchmark,
    run_benchmark,
    score_benchmark,
    seal_benchmark_runtime,
    status_benchmark,
    validate_benchmark as validate_comparative_benchmark,
    verify_benchmark,
    visual_capture_benchmark,
)
from .command_catalog import (
    build_command_catalog,
    filter_catalog,
    render_command_markdown,
)
from .cli_parser import build_parser
from .cli_handlers.index import handle_index_command
from .cli_handlers.workflow import handle_workflow_command
from .cli_handlers.worktree import handle_worktree_command
from .cli_handlers.pack import handle_pack_command
from .cli_handlers.orchestrator import handle_orchestrator_command
from .cli_output import print_json as _print_json
from .cli_output import print_mapping as _print_mapping
from .cli_output import print_table as _print_table
from .archive import archive_runs
from .config import as_dict, defaults, load_settings
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
from .eval.templating import (
    build_benchmark_report,
    build_ledger_row,
    build_lifecycle_archive,
    render_benchmark_markdown,
    validate_benchmark_manifest,
    write_template,
)
from .errors import InteractiveCapacityError, WorkflowError
from .ledger import build_ledger, render_ledger
from .approval import force_accept
from .lifecycle import record as record_lifecycle
from .inspect_adapter import build_task as build_inspect_task
from .inspect_adapter import run_inspect
from .integrations.swebench import write_prediction
from .plugin_api import PluginExecutionContext
from .plugins import EMPTY_PLUGIN_REGISTRY, PluginRegistry, load_plugin_registry
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
from .supervisor import SupervisorOptions, supervise_loop, supervise_once
from .tmux import attach as attach_tmux
from .util import atomic_write_bytes, atomic_write_json, expand_path




def _verified_receipt_hash(run: Path) -> str:
    """Return the digest of the exact receipt verified from stable bytes."""
    _, digest = verify_seal_details(run)
    return digest






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
        if token in {"--json", "--no-plugins"}:
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


def _bootstrap_plugins(
    argv: list[str] | None,
) -> tuple[Any, PluginRegistry]:
    raw = list(sys.argv[1:] if argv is None else argv)
    if "--" in raw:
        raw = raw[: raw.index("--")]
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", type=Path)
    pre_parser.add_argument("--no-plugins", action="store_true")
    known, _ = pre_parser.parse_known_args(raw)
    # Version reporting must remain available even when local configuration or
    # a plugin is broken. All other commands honor configured strict loading.
    if "--version" in raw:
        return defaults(known.config), EMPTY_PLUGIN_REGISTRY
    settings = load_settings(known.config)
    return settings, load_plugin_registry(
        settings.plugins_enabled,
        suppress=known.no_plugins,
    )




def main(argv: list[str] | None = None) -> int:
    args: argparse.Namespace | None = None
    try:
        settings, plugin_registry = _bootstrap_plugins(argv)
        parser = build_parser(plugin_registry)
        args = _parse_args(parser, argv)
        if args.command == "commands":
            catalog = build_command_catalog(
                parser,
                plugin_inventory=plugin_registry.catalog_inventory(),
            )
            output_format = args.format or ("json" if args.json else "markdown")
            if output_format == "json":
                _print_json(filter_catalog(catalog, args.role))
            else:
                print(render_command_markdown(catalog, role=args.role), end="")
            return 0
        data: Any

        if hasattr(args, "_plugin_execute"):
            data = args._plugin_execute(
                args,
                PluginExecutionContext(
                    settings=settings,
                    json_output=args.json,
                    host_version=__version__,
                ),
            )
        elif args.command == "plugins":
            data = {
                "configured_enabled": list(settings.plugins_enabled),
                "suppressed": bool(args.no_plugins),
                "plugins": plugin_registry.inventory(),
            }
        elif args.command == "doctor":
            data = run_doctor(settings)
        elif args.command == "completion":
            try:
                import shtab
            except ModuleNotFoundError as exc:
                raise WorkflowError(
                    "shell completion requires: pip install 'agent-workflow[completion]'"
                ) from exc
            print(shtab.complete(build_parser(plugin_registry), shell=args.shell), end="")
            return 0
        elif args.command == "config":
            data = as_dict(settings)
        elif args.command == "orchestrator":
            data = handle_orchestrator_command(settings, args)
        elif args.command == "worktree":
            data = handle_worktree_command(settings, args)
        elif args.command == "launch":
            interactive_override = args.interactive
            structured_override = args.structured
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
                        reasoning_effort=args.reasoning_effort,
                        allow_no_go_model=args.allow_no_go_model,
                        explicit_command=args.explicit_command,
                        ticket_id=args.ticket,
                        tier=args.tier,
                        pack_id=args.pack,
                        job_path=args.job,
                        allow_dirty=args.allow_dirty,
                        structured=structured_override,
                        interactive=interactive_override,
                        prerequisite_ids=args.prerequisites,
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
                        # Capacity fallback is an evidence-safe structured run,
                        # not merely a detached interactive executor.
                        structured_override = True
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
        elif args.command in {"archive", "clear"}:
            data = archive_runs(
                settings,
                args.session_ids,
                all_verified=args.all_verified,
                confirmed=args.verified,
                dry_run=args.dry_run,
                reason=args.reason,
            )
        elif args.command == "workflow":
            data, output_complete = handle_workflow_command(settings, args)
            if output_complete:
                return 0
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
        elif args.command == "supervisor":
            options = SupervisorOptions.from_settings(
                settings,
                capture_interactive=args.capture_interactive,
                capture_lines=args.capture_lines,
                probe_stalled=args.probe_stalled,
                interrupt_stalled=args.interrupt_stalled,
                restart_orphaned=args.restart_orphaned,
                max_remediation_attempts=args.max_remediation_attempts,
                sync_index_enabled=args.sync_index,
            )
            if args.supervisor_command == "once":
                data = supervise_once(
                    settings,
                    session_ids=args.session,
                    options=options,
                )
            else:
                reports = supervise_loop(
                    settings,
                    interval_seconds=args.interval_seconds,
                    max_cycles=args.max_cycles,
                    session_ids=args.session,
                    options=options,
                )
                data = {
                    "schema": "agent-workflow/supervisor-loop-report/v1",
                    "cycle_count": len(reports),
                    "reports": reports,
                }
        elif args.command == "index":
            data, output_complete = handle_index_command(settings, args)
            if output_complete:
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
                outcome=args.outcome,
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
        elif args.command == "force-accept":
            command = list(sys.argv if argv is None else ["agent-workflow", *argv])
            data = force_accept(
                settings,
                args.session_id,
                actor=args.actor,
                reason=args.reason,
                acknowledgement=args.acknowledge,
                command=command,
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
            elif args.eval_command == "template":
                data = write_template(args.kind, expand_path(args.output))
            elif args.eval_command == "validate-benchmark":
                source = expand_path(args.source)
                pack_root = expand_path(args.pack) if args.pack else None
                manifest = validate_benchmark_manifest(
                    source, pack_root=pack_root
                )
                if pack_root is not None:
                    report = validate_pack(pack_root, verify_checksums=False)
                    if not report.ok:
                        raise WorkflowError(
                            "benchmark pack validation failed: "
                            + "; ".join(report.errors)
                        )
                data = {
                    "path": str(source),
                    "schema": manifest["schema"],
                    "benchmark_id": manifest["benchmark_id"],
                    "case_ids": [case["case_id"] for case in manifest["cases"]],
                }
            elif args.eval_command == "benchmark-report":
                output = expand_path(args.output)
                markdown_output = expand_path(args.markdown) if args.markdown else None
                inputs = {
                    expand_path(args.manifest),
                    expand_path(args.baseline),
                    expand_path(args.candidate),
                }
                if output in inputs or markdown_output in inputs:
                    raise WorkflowError("benchmark report output must not overwrite an input")
                if markdown_output is not None and markdown_output == output:
                    raise WorkflowError("benchmark JSON and Markdown outputs must be different paths")
                report = build_benchmark_report(
                    expand_path(args.manifest),
                    expand_path(args.baseline),
                    expand_path(args.candidate),
                )
                atomic_write_json(output, report)
                if markdown_output is not None:
                    atomic_write_bytes(
                        markdown_output,
                        render_benchmark_markdown(report).encode("utf-8"),
                    )
                data = {
                    "output": str(output),
                    "markdown": str(markdown_output) if markdown_output else None,
                    "benchmark_id": report["benchmark_id"],
                    "paired_n": report["aggregate_metrics"]["paired_n"],
                    "regressions": len(report["regressions"]),
                }
            elif args.eval_command == "ledger-row":
                output = expand_path(args.output)
                row = build_ledger_row(expand_path(args.run))
                atomic_write_json(output, row)
                data = {"output": str(output), **row}
            elif args.eval_command == "archive-plan":
                output = expand_path(args.output)
                plan = build_lifecycle_archive(
                    expand_path(args.run),
                    retention_class=args.retention_class,
                    exclude_paths=(output,),
                )
                atomic_write_json(output, plan)
                data = {
                    "output": str(output),
                    "run_id": plan["run_id"],
                    "retention_class": plan["retention_class"],
                    "artifact_count": len(plan["export_contents"]),
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
        elif args.command == "benchmark":
            if args.benchmark_command == "validate":
                data = validate_comparative_benchmark(args.spec, args.executor)
            elif args.benchmark_command == "auth-check":
                data = check_benchmark_auth(args.executor)
            elif args.benchmark_command == "readiness":
                data = benchmark_readiness(
                    args.spec,
                    args.executor,
                    policy=args.policy,
                    runtime_lock=args.runtime_lock,
                )
            elif args.benchmark_command == "runtime-attest":
                data = attest_benchmark_runtime(args.runtime_lock, claim_level=args.claim_level)
            elif args.benchmark_command == "runtime-seal":
                data = seal_benchmark_runtime(args.base_lock, args.output, container_image=args.container_image)
            elif args.benchmark_command == "suite-export":
                data = export_benchmark_suite(
                    args.destination,
                    benchmark_id=args.benchmark_id,
                    force=args.force,
                )
            elif args.benchmark_command == "fixture-create":
                data = create_benchmark_fixture(args.spec, args.destination, force=args.force)
            elif args.benchmark_command == "plan":
                data = create_benchmark_plan(
                    settings,
                    spec=args.spec,
                    executor=args.executor,
                    repo=args.repo,
                    base_ref=args.base_ref,
                    run_id=args.run_id,
                    repetitions=args.repetitions,
                    worktree_root=args.worktree_root,
                    allow_dirty=args.allow_dirty,
                    assistance_cohort=args.assistance_cohort,
                    policy=args.policy,
                    runtime_lock=args.runtime_lock,
                )
            elif args.benchmark_command == "run":
                data = run_benchmark(settings, args.run)
            elif args.benchmark_command == "resume":
                data = resume_benchmark(settings, args.run)
            elif args.benchmark_command == "status":
                data = status_benchmark(settings, args.run)
            elif args.benchmark_command == "visual-capture":
                data = visual_capture_benchmark(settings, args.run)
            elif args.benchmark_command == "score":
                data = score_benchmark(settings, args.run)
            elif args.benchmark_command == "consolidate":
                data = consolidate_benchmark(settings, args.run)
            elif args.benchmark_command == "review":
                data = benchmark_review(
                    settings,
                    args.run,
                    reviewer=args.reviewer,
                    input_path=args.input,
                )
            elif args.benchmark_command == "report":
                data = render_comparative_benchmark_report(settings, args.run)
            elif args.benchmark_command == "verify":
                data = verify_benchmark(settings, args.run)
            else:
                data = cleanup_benchmark(settings, args.run)
        elif args.command == "pack":
            data, exit_code = handle_pack_command(settings, args)
            if exit_code is not None:
                return exit_code
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
        if bool(getattr(args, "json", False)):
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
