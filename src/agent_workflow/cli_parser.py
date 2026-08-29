"""Construction of the public argparse command contract.

This module owns parser shape only. Command dispatch remains in ``agent_workflow.cli``
so parser-derived catalogs, completions, plugin command registration, and installed
help continue to share one authoritative command tree.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from . import __version__
from .cli_contract import (
    AUTHORIZED_WORKFLOW_TEMPLATES,
    COMMAND_PROFILES,
    EVALUATION_TEMPLATE_KINDS,
)
from .errors import WorkflowError

if TYPE_CHECKING:
    from .plugins import PluginRegistry


class _ParserSink:
    """No-op argparse construction sink for top-level branches outside a scoped build.

    The source parser definition remains authoritative; scoped construction simply avoids
    allocating argparse objects for unrelated command branches.
    """

    choices: dict[str, argparse.ArgumentParser] = {}

    def add_parser(self, *args, **kwargs):
        return self

    def add_subparsers(self, *args, **kwargs):
        return self

    def add_argument(self, *args, **kwargs):
        return self

    def add_mutually_exclusive_group(self, *args, **kwargs):
        return self

    def set_defaults(self, *args, **kwargs):
        return self


class _ScopedSubparsers:
    def __init__(
        self,
        action: argparse._SubParsersAction,
        command_scopes: frozenset[str] | None,
    ):
        self._action = action
        self._command_scopes = command_scopes
        self._sink = _ParserSink()

    @property
    def choices(self):
        return self._action.choices

    def add_parser(self, name: str, *args, **kwargs):
        if self._command_scopes is not None and name not in self._command_scopes:
            return self._sink
        return self._action.add_parser(name, *args, **kwargs)


def build_parser(
    plugin_registry: "PluginRegistry | None" = None,
    *,
    command_scope: str | None = None,
    command_scopes: Iterable[str] | None = None,
) -> argparse.ArgumentParser:
    if command_scope is not None and command_scopes is not None:
        raise ValueError("command_scope and command_scopes are mutually exclusive")
    selected_scopes = (
        frozenset({command_scope})
        if command_scope is not None
        else (frozenset(command_scopes) if command_scopes is not None else None)
    )
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
    command_action = parser.add_subparsers(dest="command", required=True)
    commands = _ScopedSubparsers(command_action, selected_scopes)

    commands.add_parser("doctor", help="check environment and configuration")
    catalog = commands.add_parser(
        "commands", help="print the parser-derived command contract"
    )
    catalog.add_argument("--format", choices=("json", "markdown"), default=None)
    catalog.add_argument("--role", choices=("all", *COMMAND_PROFILES), default="all")
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
    wf_seal = workflow_commands.add_parser("seal", help="seal workflow evidence")
    wf_seal.add_argument("run_dir", type=Path)
    wf_seal.add_argument("snapshot", type=Path)
    wf_verify = workflow_commands.add_parser("verify", help="verify a workflow receipt")
    wf_verify.add_argument("run_dir", type=Path)
    wf_verify.add_argument("snapshot", type=Path)
    wf_template = workflow_commands.add_parser("template", help="expand an authorized workflow template")
    wf_template.add_argument("template", choices=AUTHORIZED_WORKFLOW_TEMPLATES)
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
    registry_register = registry_commands.add_parser("register", help="register a launch-verified child Agent Run")
    registry_register.add_argument("orchestrator_id")
    registry_register.add_argument("agent_run_id")
    registry_unregister = registry_commands.add_parser("unregister", help="mark a child completed or abandoned")
    registry_unregister.add_argument("orchestrator_id")
    registry_unregister.add_argument("agent_run_id")
    registry_unregister.add_argument("--state", choices=("completed", "abandoned"), required=True)

    inbox = orchestrator_commands.add_parser("inbox", help="aggregate orchestrator inbox")
    inbox_commands = inbox.add_subparsers(dest="inbox_command", required=True)
    inbox_import = inbox_commands.add_parser("import", help="import verified child journal events")
    inbox_import.add_argument("orchestrator_id")
    inbox_import.add_argument("--agent-run-id", dest="agent_run_id")
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

    delegate = commands.add_parser(
        "delegate", help="create/select a worktree and prepare/start one Agent Run"
    )
    delegate.add_argument("agent_run_id")
    delegate.add_argument("prompt", type=Path)
    source = delegate.add_mutually_exclusive_group(required=True)
    source.add_argument("--repo", type=Path, help="repository from which to create a delegated worktree")
    source.add_argument("--workdir", type=Path, help="existing worktree/workdir to use without creating one")
    delegate.add_argument("--ticket", help="ticket ID; defaults to agent_run_id")
    delegate.add_argument("--base-ref", default="HEAD")
    delegate.add_argument("--dest", type=Path, help="destination for a newly created worktree")
    delegate.add_argument("--branch", help="branch for a newly created worktree")
    delegate.add_argument("--role", default="implementation", help="logical role; defaults to implementation")
    delegate.add_argument("--pack")
    delegate.add_argument("--job", type=Path)
    delegate.add_argument("--prerequisite", action="append", dest="prerequisites")
    delegate.add_argument("--evaluation", type=Path)
    delegate.add_argument("--tier", choices=("low", "medium", "high", "critical"))
    delegate.add_argument("--structured", action="store_true")
    delegate.add_argument(
        "--interactive", action=argparse.BooleanOptionalAction, default=None,
        help="prepare an interactive provider command for an external worker",
    )
    delegate.add_argument("--allow-dirty", action="store_true")
    delegate.add_argument(
        "--worker-mode", choices=("headless", "external"), default="headless",
        help="headless starts immediately; external prepares only",
    )
    # Operator/debug compatibility controls. Normal agent-facing use should select --role only.
    delegate.add_argument("--executor", help=argparse.SUPPRESS)
    delegate.add_argument("--agent-name", help=argparse.SUPPRESS)
    delegate.add_argument("--agent-class", help=argparse.SUPPRESS)
    delegate.add_argument("--model", help=argparse.SUPPRESS)
    delegate.add_argument("--reasoning-effort", choices=("low", "medium", "high"), help=argparse.SUPPRESS)
    delegate.add_argument("--allow-no-go-model", action="store_true", help=argparse.SUPPRESS)

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

    closeout = worktree_commands.add_parser(
        "closeout", help="write an immutable repository integration receipt"
    )
    closeout.add_argument("repo", type=Path)
    closeout.add_argument("--output", type=Path, required=True)
    closeout.add_argument("--baseline-revision")
    closeout.add_argument("--remote", default="origin")
    closeout.add_argument("--fetch", action="store_true", help="refresh and verify remote state")
    closeout.add_argument("--push", action="store_true", help="push HEAD to the resolved remote branch")
    closeout.add_argument("--push-branch")
    closeout.add_argument("--set-upstream", action="store_true")
    closeout.add_argument("--integration-branch")
    closeout.add_argument("--operational-tree", action="append", default=[])
    closeout.add_argument("--disposable-tree", action="append", default=[])

    closeout_verify = worktree_commands.add_parser(
        "closeout-verify", help="verify a repository closeout receipt"
    )
    closeout_verify.add_argument("receipt", type=Path)

    agent_run = commands.add_parser("agent-run", help="Agent Run lifecycle and durable-control commands")
    agent_run_commands = agent_run.add_subparsers(dest="agent_run_command", required=True)

    launch = agent_run_commands.add_parser(
        "prepare", help="prepare an Agent Run without requiring a terminal host"
    )
    launch.add_argument("agent_run_id")
    launch.add_argument("workdir", type=Path)
    launch.add_argument("prompt", type=Path)
    launch.add_argument("--ticket")
    launch.add_argument("--tier", choices=("low", "medium", "high", "critical"))
    launch.add_argument("--pack")
    launch.add_argument("--job", type=Path, help="validated native JSON job in the prompt pack")
    launch.add_argument("--prerequisite", action="append", dest="prerequisites", help="required prerequisite agent run ID; repeatable")
    launch.add_argument("--role", help="logical agent role; runtime/provider resolution remains private")
    launch.add_argument("--executor", help="operator compatibility override; prefer --role")
    launch.add_argument("--agent-name", help="preferred configured agent name")
    launch.add_argument("--agent-class", help="operator compatibility classification; prefer --role")
    launch.add_argument("--model", help="operator compatibility model override; prefer --role")
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
        help="prepare an interactive provider command for an external worker",
    )
    launch.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow launching from a Git worktree with uncommitted changes",
    )
    launch.add_argument(
        "--worker-mode",
        choices=("headless", "external"),
        default="headless",
        help="headless workers are AW-owned; external workers are prepared only",
    )

    start = agent_run_commands.add_parser("start", help="start a prepared headless Agent Run")
    start.add_argument("agent_run_id")

    agent_run_commands.add_parser("list", help="list Agent Runs")

    archive = agent_run_commands.add_parser(
        "archive",
        help="archive verified completed runs from the active list",
    )
    archive.add_argument("agent_run_ids", nargs="*", help="run IDs to archive")
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

    status = agent_run_commands.add_parser("status", help="inspect a delegation")
    status.add_argument("agent_run_id")

    public_messages = agent_run_commands.add_parser(
        "message-state", help="show bounded durable message and acknowledgement state"
    )
    public_messages.add_argument("agent_run_id")

    public_summary = agent_run_commands.add_parser(
        "summary", help="show completion, evaluation, review, and acceptance summary"
    )
    public_summary.add_argument("agent_run_id")

    public_provenance = agent_run_commands.add_parser(
        "provenance", help="show restricted operator worktree/source/runtime provenance"
    )
    public_provenance.add_argument("agent_run_id")

    external_binding = agent_run_commands.add_parser(
        "external-binding", help="show the rebuildable external Worker binding projection"
    )
    external_binding.add_argument("agent_run_id")

    bind_external = agent_run_commands.add_parser(
        "bind-external", help="idempotently bind or rebind an externally hosted Worker"
    )
    bind_external.add_argument("agent_run_id")
    bind_external.add_argument("external_runtime_type")
    bind_external.add_argument("external_worker_id")

    start_external = agent_run_commands.add_parser(
        "start-external", help="record the start of a bound external Worker"
    )
    start_external.add_argument("agent_run_id")
    start_external.add_argument("external_runtime_type")
    start_external.add_argument("external_worker_id")
    start_external.add_argument("--generation", type=int, required=True)

    observe_external = agent_run_commands.add_parser(
        "observe-external", help="record an observation of the current external Worker binding"
    )
    observe_external.add_argument("agent_run_id")

    unbind_external = agent_run_commands.add_parser(
        "unbind-external", help="idempotently remove the current external Worker binding"
    )
    unbind_external.add_argument("agent_run_id")

    pending_external = agent_run_commands.add_parser(
        "pending-external-delivery",
        help="fetch durable messages awaiting delivery by the active external Worker",
    )
    pending_external.add_argument("agent_run_id")
    pending_external.add_argument("--generation", type=int, required=True)

    report_external = agent_run_commands.add_parser(
        "report-external-delivery",
        help="record an external host delivery attempt without acknowledging the message",
    )
    report_external.add_argument("agent_run_id")
    report_external.add_argument("correlation_id")
    report_external.add_argument("--generation", type=int, required=True)
    report_external.add_argument("--attempt", type=int, required=True)
    report_external.add_argument("--outcome", choices=("delivered", "failed"), required=True)
    report_external.add_argument("--reason", required=True)

    repair = agent_run_commands.add_parser(
        "repair", help="rebuild a mutable status projection from run authority"
    )
    repair.add_argument("agent_run_id")

    finalize = agent_run_commands.add_parser(
        "finalize", help="idempotently finalize an unsealed Agent Run"
    )
    finalize.add_argument("agent_run_id")

    supervisor = commands.add_parser(
        "supervisor",
        help="collect health evidence and apply bounded remediation policy",
    )
    supervisor_commands = supervisor.add_subparsers(
        dest="supervisor_command", required=True
    )

    def add_supervisor_options(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--agent-run",
            dest="agent_runs",
            action="append",
            default=[],
            help="limit supervision to an Agent Run ID; repeatable",
        )
        command.add_argument(
            "--probe-stalled",
            action=argparse.BooleanOptionalAction,
            default=None,
        )
        command.add_argument(
            "--interrupt-stalled",
            action=argparse.BooleanOptionalAction,
            default=None,
            help="opt in to bounded process interruption after the progress-probe allowance is exhausted",
        )
        command.add_argument(
            "--restart-orphaned",
            action=argparse.BooleanOptionalAction,
            default=None,
            help="opt in to lineage-preserving restart of orphaned headless Agent Runs",
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
        index_write.add_argument("--run", dest="agent_run_id", help="limit indexing to one run ID")
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
        "--review", dest="review_agent_run_id",
        help="verify one sealed, reviewed run and its direct gate evidence",
    )
    index_integrity = index_commands.add_parser(
        "integrity", help="explicitly append integrity authority records"
    )
    index_integrity_commands = index_integrity.add_subparsers(dest="integrity_command", required=True)
    index_integrity_record = index_integrity_commands.add_parser("record")
    index_integrity_record.add_argument("agent_run_id")
    index_integrity_record.add_argument("artifact_path")
    index_integrity_record.add_argument("error_id", type=int)
    index_integrity_record.add_argument("error_category")
    index_integrity_record.add_argument("error_detail")
    index_query = index_commands.add_parser(
        "query", help="query curated read-only operational views"
    )
    index_query.add_argument(
        "kind",
        choices=("runs", "incidents", "permissions", "performance", "workflows", "workflow-nodes", "errors"),
    )
    index_query.add_argument("--agent-run", dest="agent_run_id")
    index_query.add_argument("--state")
    index_query.add_argument("--category")
    index_query.add_argument("--executor")
    index_query.add_argument("--model")
    index_query.add_argument("--pack", dest="pack_id")
    index_query.add_argument("--limit", type=int, default=100)

    tail = agent_run_commands.add_parser("tail", help="follow a delegation log")
    tail.add_argument("agent_run_id")
    tail.add_argument("--lines", type=int, default=50)

    steer = agent_run_commands.add_parser(
        "steer", help="persist a parent-to-child steering request"
    )
    steer.add_argument("agent_run_id")
    steer.add_argument("content")
    steer.add_argument("--actor", required=True)

    progress = agent_run_commands.add_parser(
        "progress", help="persist a child-to-parent progress update"
    )
    progress.add_argument("agent_run_id")
    progress.add_argument("content")
    progress.add_argument("--actor", required=True)

    acknowledge = agent_run_commands.add_parser(
        "ack", help="record application of a steering request"
    )
    acknowledge.add_argument("agent_run_id")
    acknowledge.add_argument("correlation_id")
    acknowledge.add_argument("content")
    acknowledge.add_argument("--actor", required=True)
    acknowledge.add_argument(
        "--outcome", choices=("applied", "rejected"), default="applied"
    )

    watch = agent_run_commands.add_parser(
        "watch", help="block until a durable Agent Run message arrives"
    )
    watch.add_argument("agent_run_id")
    watch.add_argument("--after", type=int, default=0)
    watch.add_argument("--timeout", type=float)

    interrupt = agent_run_commands.add_parser(
        "interrupt", help="request interruption of an Agent Run worker"
    )
    interrupt.add_argument("agent_run_id")

    terminate = agent_run_commands.add_parser(
        "terminate", help="terminate an Agent Run worker while preserving evidence"
    )
    terminate.add_argument("agent_run_id")
    terminate.add_argument("--grace-seconds", type=int, default=8)

    restart = agent_run_commands.add_parser(
        "restart", help="create a new Agent Run from a completed prior run"
    )
    restart.add_argument("agent_run_id")
    restart.add_argument("--new-agent-run-id")

    agent = commands.add_parser("agent", help="Agent Run worker context and completion")
    agent_commands = agent.add_subparsers(dest="agent_command", required=True)
    agent_context = agent_commands.add_parser("context", help="show durable agent context")
    agent_context.add_argument("agent_run_id")
    agent_roles = agent_commands.add_parser("roles", help="show public logical agent roles")
    agent_roles.add_argument("role_id", nargs="?", help="optional logical role ID")
    agent_complete = agent_commands.add_parser(
        "task-complete", help="publish structured completion for the current Agent Run"
    )
    agent_complete.add_argument("agent_run_id")
    agent_complete.add_argument("--actor", required=True)
    agent_complete.add_argument("--summary", required=True)
    agent_complete.add_argument("--tag", action="append", default=[])
    agent_complete.add_argument("--file", action="append", default=[])
    agent_validate = agent_commands.add_parser(
        "completion-validate", help="validate the current completion handoff before exit"
    )
    agent_validate.add_argument("agent_run_id")

    for name in ("review", "accept", "reject"):
        lifecycle = agent_run_commands.add_parser(name, help=f"record {name} disposition")
        lifecycle.add_argument("agent_run_id")
        lifecycle.add_argument("--actor", required=True)
        lifecycle.add_argument("--reason", required=True)
        if name == "accept":
            lifecycle.add_argument("--revision", required=True)

    force = agent_run_commands.add_parser(
        "force-accept", help="record an explicit local operator acceptance override"
    )
    force.add_argument("agent_run_id")
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
    eval_template.add_argument("kind", choices=EVALUATION_TEMPLATE_KINDS)
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
        ("status", "show benchmark state, evidence, and live review URLs"),
        ("live-start", "start or restore preserved live applications for human review"),
        ("live-stop", "stop preserved live applications without deleting evidence"),
        ("visual-capture", "capture pinned visual evidence for all arms"),
        ("score", "run deterministic machine scorers"),
        ("consolidate", "copy and digest-verify arm evidence into the coordinator"),
        ("report", "render JSON and Markdown comparative reports"),
        ("verify", "verify the consolidated evidence manifest and receipt"),
        ("cleanup", "retain benchmark arms by default; optionally remove verified arm worktrees"),
    ):
        command = benchmark_commands.add_parser(name, help=help_text)
        command.add_argument("run")
        if name == "cleanup":
            command.add_argument("--remove-worktrees", action="store_true")
            command.add_argument("--stop-live-apps", action="store_true")
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

    plugin_commands = () if plugin_registry is None else plugin_registry.commands
    for loaded_plugin, plugin_command in plugin_commands:
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
