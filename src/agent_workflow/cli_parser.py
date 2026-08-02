"""Construction of the public argparse command contract.

This module owns parser shape only. Command dispatch remains in ``agent_workflow.cli``
so parser-derived catalogs, completions, plugin command registration, and installed
help continue to share one authoritative command tree.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .command_catalog import COMMAND_ROLES
from .errors import WorkflowError
from .eval.templating import TEMPLATE_KINDS
from .plugins import EMPTY_PLUGIN_REGISTRY, PluginRegistry
from .workflow_templates import AUTHORIZED_TEMPLATES


def build_parser(plugin_registry: PluginRegistry | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-workflow")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", type=Path, help="override config.toml path")
    parser.add_argument(
        "--json",
        action="store_true",
        help="machine-readable output where supported",
    )
    parser.add_argument(
        "--no-plugins",
        action="store_true",
        help="suppress configured plugins for recovery and core-only operation",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor", help="check environment and configuration")
    catalog = commands.add_parser(
        "commands", help="print the parser-derived command contract"
    )
    catalog.add_argument("--format", choices=("json", "markdown"), default=None)
    catalog.add_argument("--role", choices=("all", *COMMAND_ROLES), default="all")
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
    plugins = commands.add_parser("plugins", help="trusted plugin inventory")
    plugin_commands = plugins.add_subparsers(dest="plugins_command", required=True)
    plugin_commands.add_parser("list", help="list discovered and enabled plugins")

    orchestrator = commands.add_parser("orchestrator", help="orchestrator registry and inbox commands")
    orchestrator_commands = orchestrator.add_subparsers(dest="orchestrator_command", required=True)
    registry = orchestrator_commands.add_parser("registry", help="orchestrator identity registry")
    registry_commands = registry.add_subparsers(dest="registry_command", required=True)
    registry_create = registry_commands.add_parser("create", help="create an orchestrator registry")
    registry_create.add_argument("orchestrator_id")
    registry_create.add_argument("--workflow-id")
    registry_inspect = registry_commands.add_parser("inspect", help="inspect an orchestrator registry")
    registry_inspect.add_argument("orchestrator_id")
    registry_register = registry_commands.add_parser("register", help="register a launch-verified child session")
    registry_register.add_argument("orchestrator_id")
    registry_register.add_argument("session_id")
    registry_unregister = registry_commands.add_parser("unregister", help="mark a child completed or abandoned")
    registry_unregister.add_argument("orchestrator_id")
    registry_unregister.add_argument("session_id")
    registry_unregister.add_argument("--state", choices=("completed", "abandoned"), required=True)

    inbox = orchestrator_commands.add_parser("inbox", help="aggregate orchestrator inbox")
    inbox_commands = inbox.add_subparsers(dest="inbox_command", required=True)
    inbox_import = inbox_commands.add_parser("import", help="import verified child journal events")
    inbox_import.add_argument("orchestrator_id")
    inbox_import.add_argument("--session-id")
    inbox_import.add_argument("--max-per-child", type=int, default=100000)
    for name, help_text in (("list", "list bounded inbox metadata"), ("read", "read bounded inbox events")):
        inbox_read = inbox_commands.add_parser(name, help=help_text)
        inbox_read.add_argument("orchestrator_id")
        inbox_read.add_argument("--after", type=int, default=0)
        inbox_read.add_argument("--limit", type=int, default=100)
        inbox_read.add_argument("--event-id")
        inbox_read.add_argument("--include-content", action="store_true")

    watch_parser = orchestrator_commands.add_parser(
        "watch", help="foreground shared-wakeup inbox supervisor"
    )
    watch_parser.add_argument("orchestrator_id")
    watch_parser.add_argument("--interval-seconds", type=float)
    watch_parser.add_argument("--poll-seconds", type=float, default=0.2)
    watch_parser.add_argument("--batch-size", type=int, default=100)
    watch_parser.add_argument("--max-per-child", type=int, default=25)
    watch_parser.add_argument("--max-cycles", type=int)

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
    launch.add_argument("--prerequisite", action="append", dest="prerequisites", help="required prerequisite session ID; repeatable")
    launch.add_argument("--executor")
    launch.add_argument("--agent-name", help="preferred configured agent/pane name")
    launch.add_argument("--agent-class", help="configured agent work classification")
    launch.add_argument("--model", help="configured executor model")
    launch.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high"),
        help="Codex reasoning effort; larger work must be decomposed",
    )
    launch.add_argument(
        "--allow-no-go-model",
        action="store_true",
        help="explicitly authorize a configured no-go model for this run",
    )
    launch.add_argument("--evaluation", type=Path)
    launch.add_argument(
        "--structured",
        action="store_true",
        help="explicitly opt into a non-interactive structured evidence run",
    )
    launch.add_argument(
        "--interactive",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="run implementation work in a visible or dedicated interactive executor",
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

    archive = commands.add_parser(
        "archive",
        aliases=["clear"],
        help="archive verified completed runs from the active list",
    )
    archive.add_argument("session_ids", nargs="*", help="run IDs to archive")
    archive.add_argument(
        "--all-verified",
        action="store_true",
        help="scan and archive every run that passes all evidence gates",
    )
    archive.add_argument(
        "--verified",
        action="store_true",
        help="confirm the recoverable move of verified runs",
    )
    archive.add_argument(
        "--dry-run", action="store_true", help="report eligible runs without moving them"
    )
    archive.add_argument(
        "--reason",
        default="verified completed work no longer needed in the active run list",
    )

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

    supervisor = commands.add_parser(
        "supervisor",
        help="collect health evidence and apply bounded remediation policy",
    )
    supervisor_commands = supervisor.add_subparsers(
        dest="supervisor_command", required=True
    )

    def add_supervisor_options(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--session",
            action="append",
            default=[],
            help="limit supervision to a run ID; repeatable",
        )
        command.add_argument(
            "--capture-interactive",
            action=argparse.BooleanOptionalAction,
            default=None,
        )
        command.add_argument("--capture-lines", type=int)
        command.add_argument(
            "--probe-stalled",
            action=argparse.BooleanOptionalAction,
            default=None,
        )
        command.add_argument(
            "--interrupt-stalled",
            action=argparse.BooleanOptionalAction,
            default=None,
            help="opt in to bounded Ctrl-C after the progress-probe allowance is exhausted",
        )
        command.add_argument(
            "--restart-orphaned",
            action=argparse.BooleanOptionalAction,
            default=None,
            help="opt in to lineage-preserving restart of orphaned interactive runs",
        )
        command.add_argument("--max-remediation-attempts", type=int)
        command.add_argument(
            "--sync-index",
            action=argparse.BooleanOptionalAction,
            default=None,
            help="reconcile the rebuildable SQLite projection after each cycle",
        )

    supervisor_once_parser = supervisor_commands.add_parser(
        "once", help="run one reconciliation and remediation cycle"
    )
    add_supervisor_options(supervisor_once_parser)
    supervisor_run_parser = supervisor_commands.add_parser(
        "run", help="run the foreground supervisor loop"
    )
    add_supervisor_options(supervisor_run_parser)
    supervisor_run_parser.add_argument("--interval-seconds", type=int)
    supervisor_run_parser.add_argument("--max-cycles", type=int)

    index = commands.add_parser(
        "index", help="rebuildable SQLite projection and analytical queries"
    )
    index_commands = index.add_subparsers(dest="index_command", required=True)
    index_commands.add_parser("status", help="show index location, version, and freshness")
    for name, help_text in (
        ("sync", "incrementally reconcile changed run directories"),
        ("rebuild", "recreate the projection from authoritative evidence"),
    ):
        index_write = index_commands.add_parser(name, help=help_text)
        index_write.add_argument("--run", dest="session_id", help="limit indexing to one run ID")
        index_write.add_argument(
            "--active-only", action="store_true", help="exclude archived runs from discovery"
        )
    index_verify = index_commands.add_parser(
        "verify", help="check SQLite integrity and optional source digests"
    )
    index_verify.add_argument(
        "--full", action="store_true", help="rehash every indexed source artifact"
    )
    index_verify.add_argument(
        "--review", dest="review_session_id",
        help="verify one sealed, reviewed run and its direct gate evidence",
    )
    index_integrity = index_commands.add_parser(
        "integrity", help="explicitly append or migrate integrity authority records"
    )
    index_integrity_commands = index_integrity.add_subparsers(dest="integrity_command", required=True)
    index_integrity_record = index_integrity_commands.add_parser("record")
    index_integrity_record.add_argument("session_id")
    index_integrity_record.add_argument("artifact_path")
    index_integrity_record.add_argument("error_id", type=int)
    index_integrity_record.add_argument("error_category")
    index_integrity_record.add_argument("error_detail")
    index_integrity_commands.add_parser("migrate")
    index_query = index_commands.add_parser(
        "query", help="query curated read-only operational views"
    )
    index_query.add_argument(
        "kind",
        choices=("runs", "incidents", "permissions", "performance", "workflows", "workflow-nodes", "errors"),
    )
    index_query.add_argument("--session", dest="session_id")
    index_query.add_argument("--state")
    index_query.add_argument("--category")
    index_query.add_argument("--executor")
    index_query.add_argument("--model")
    index_query.add_argument("--pack", dest="pack_id")
    index_query.add_argument("--limit", type=int, default=100)

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
    acknowledge.add_argument(
        "--outcome", choices=("applied", "rejected"), default="applied"
    )

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
    agent_complete.add_argument(
        "--keep-alive", action="store_true",
        help="keep the interactive executor available for explicit same-worktree reuse",
    )
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

    force = commands.add_parser(
        "force-accept", help="record an explicit local operator acceptance override"
    )
    force.add_argument("session_id")
    force.add_argument("--actor", required=True)
    force.add_argument("--reason", required=True)
    force.add_argument(
        "--acknowledge", required=True, choices=("FORCE-ACCEPT",),
        help="explicitly acknowledge the unauthenticated local override",
    )

    evaluation = commands.add_parser("eval", help="evaluation commands")
    evaluation_commands = evaluation.add_subparsers(dest="eval_command", required=True)
    eval_validate = evaluation_commands.add_parser(
        "validate", help="validate an evaluation plan"
    )
    eval_validate.add_argument("source", type=Path)
    eval_validate.add_argument("--pack", type=Path)
    eval_template = evaluation_commands.add_parser(
        "template", help="write a deterministic evaluation or benchmark template"
    )
    eval_template.add_argument("kind", choices=TEMPLATE_KINDS)
    eval_template.add_argument("--output", type=Path, required=True)
    eval_validate_benchmark = evaluation_commands.add_parser(
        "validate-benchmark", help="validate a benchmark/cohort manifest"
    )
    eval_validate_benchmark.add_argument("source", type=Path)
    eval_validate_benchmark.add_argument("--pack", type=Path)
    eval_benchmark_report = evaluation_commands.add_parser(
        "benchmark-report", help="render a deterministic matched-cohort benchmark report"
    )
    eval_benchmark_report.add_argument("manifest", type=Path)
    eval_benchmark_report.add_argument("baseline", type=Path)
    eval_benchmark_report.add_argument("candidate", type=Path)
    eval_benchmark_report.add_argument("--output", type=Path, required=True)
    eval_benchmark_report.add_argument("--markdown", type=Path)
    eval_ledger_row = evaluation_commands.add_parser(
        "ledger-row", help="render one evidence-first evaluation ledger row"
    )
    eval_ledger_row.add_argument("run", type=Path)
    eval_ledger_row.add_argument("--output", type=Path, required=True)
    eval_archive_plan = evaluation_commands.add_parser(
        "archive-plan", help="render deterministic sealed-run archive and retention inputs"
    )
    eval_archive_plan.add_argument("run", type=Path)
    eval_archive_plan.add_argument("--output", type=Path, required=True)
    eval_archive_plan.add_argument(
        "--retention-class",
        choices=("transient", "standard", "release", "legal-hold"),
        default="standard",
    )
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


    benchmark = commands.add_parser("benchmark", help="paired comparative benchmark commands")
    benchmark_commands = benchmark.add_subparsers(dest="benchmark_command", required=True)
    benchmark_validate = benchmark_commands.add_parser("validate", help="validate a comparative benchmark suite")
    benchmark_validate.add_argument("spec", type=Path)
    benchmark_validate.add_argument("--executor", type=Path)
    benchmark_auth = benchmark_commands.add_parser("auth-check", help="verify a subscription session or optional API credential without exposing secrets")
    benchmark_auth.add_argument("executor", type=Path)
    benchmark_ready = benchmark_commands.add_parser("readiness", help="validate policy, authentication, repetition thresholds, and visual runtime without creating worktrees")
    benchmark_ready.add_argument("spec", type=Path)
    benchmark_ready.add_argument("--executor", type=Path, required=True)
    benchmark_ready.add_argument("--policy", type=Path)
    benchmark_ready.add_argument("--runtime-lock", type=Path)
    benchmark_runtime = benchmark_commands.add_parser("runtime-attest", help="attest browser, Playwright, font, and container runtime identity")
    benchmark_runtime.add_argument("runtime_lock", type=Path)
    benchmark_runtime.add_argument("--claim-level", choices=("development", "internal", "publication"), default="development")
    benchmark_runtime_seal = benchmark_commands.add_parser("runtime-seal", help="seal a publication runtime lock inside a content-addressed browser container")
    benchmark_runtime_seal.add_argument("base_lock", type=Path)
    benchmark_runtime_seal.add_argument("output", type=Path)
    benchmark_runtime_seal.add_argument("--container-image", required=True)
    benchmark_export = benchmark_commands.add_parser("suite-export", help="export a packaged comparative benchmark suite")
    benchmark_export.add_argument("destination", type=Path)
    benchmark_export.add_argument("--benchmark-id", default="priority-picker-v1")
    benchmark_export.add_argument("--force", action="store_true")
    benchmark_fixture = benchmark_commands.add_parser("fixture-create", help="materialize the benchmark starter fixture as a Git repository")
    benchmark_fixture.add_argument("spec", type=Path)
    benchmark_fixture.add_argument("destination", type=Path)
    benchmark_fixture.add_argument("--force", action="store_true")
    benchmark_plan = benchmark_commands.add_parser("plan", help="create coordinator and paired arm worktrees and seal a run plan")
    benchmark_plan.add_argument("spec", type=Path)
    benchmark_plan.add_argument("--executor", type=Path, required=True)
    benchmark_plan.add_argument("--repo", type=Path, required=True)
    benchmark_plan.add_argument("--base-ref", default="HEAD")
    benchmark_plan.add_argument("--run-id")
    benchmark_plan.add_argument("--repetitions", type=int)
    benchmark_plan.add_argument("--worktree-root", type=Path)
    benchmark_plan.add_argument("--allow-dirty", action="store_true")
    benchmark_plan.add_argument("--assistance-cohort", choices=("unassisted", "assisted"))
    benchmark_plan.add_argument("--policy", type=Path)
    benchmark_plan.add_argument("--runtime-lock", type=Path)
    for name, help_text in (
        ("run", "execute, capture, score, consolidate, and report a benchmark run"),
        ("resume", "resume an idempotent benchmark pipeline"),
        ("status", "show benchmark state and evidence availability"),
        ("visual-capture", "capture pinned visual evidence for all arms"),
        ("score", "run deterministic machine scorers"),
        ("consolidate", "copy and digest-verify arm evidence into the coordinator"),
        ("report", "render JSON and Markdown comparative reports"),
        ("verify", "verify the consolidated evidence manifest and receipt"),
        ("cleanup", "remove verified arm worktrees while preserving the coordinator"),
    ):
        command = benchmark_commands.add_parser(name, help=help_text)
        command.add_argument("run")
    benchmark_human = benchmark_commands.add_parser("review", help="create a blinded review assignment or submit a completed review")
    benchmark_human.add_argument("run")
    benchmark_human.add_argument("--reviewer", required=True)
    benchmark_human.add_argument("--input", type=Path)

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

    registry = plugin_registry or EMPTY_PLUGIN_REGISTRY
    for loaded_plugin, plugin_command in registry.commands:
        if plugin_command.name in commands.choices:
            raise WorkflowError(
                f"plugin {loaded_plugin.descriptor.name!r} command {plugin_command.name!r} "
                "conflicts with a core command"
            )
        plugin_parser = commands.add_parser(plugin_command.name, help=plugin_command.summary)
        plugin_command.configure(plugin_parser)
        plugin_parser.set_defaults(
            _plugin_execute=plugin_command.execute,
            _plugin_name=loaded_plugin.descriptor.name,
        )

    return parser
