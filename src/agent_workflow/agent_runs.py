from __future__ import annotations

import hashlib
import json
import os
import platform
import shlex
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .agent_context import initialize as initialize_agent_context
from .agent_run_paths import AgentRunPaths
from .agent_identity import claim_agent_name, release_agent_name, resolve_agent_identity
from .assets import asset_path
from .config import Settings
from .config import enforce_trust
from .compatibility import probe_executor
from .command_catalog import write_launch_command_artifacts
from .contracts import read_contract, read_agent_run_contract, schema_descriptor
from .errors import WorkflowError
from .eval.commands import collect_commands, specs_from_data
from .eval.scope import ScopePolicy, collect_scope
from .evaluation import validate_evaluation
from .executors import (
    ExecutorPlan,
    executor_identity_for_plan,
    prepare_executor,
)
from .git import snapshot
from .health import last_event as last_health_event
from .health import semantic_progress
from .native_jobs import ValidatedNativeJob, validate_native_job
from .preflight import preflight_error, preflight_run_record, resolve_prerequisites
from .manifests import task_result_contract
from .process import ProcessRequest, redact_argv, require_command, run, secret_values_from_argv, spawn_detached
from .receipts import completion_template, initial_completion, initial_provenance, update_provenance
from .agent_run_control import (
    _child_lifecycle_control,
    acknowledge,
    interrupt,
    messages,
    progress,
    steer,
    terminate,
    wait_for_message,
)
from .agent_run_artifacts import (
    _create_handoff_dir,
    _discover_prompt_pack_root,
    _pack_id,
    _write_runner,
)
from .state import (
    TERMINAL_STATUSES,
    list_statuses,
    read_status,
    run_dir,
    update_projection,
)
from .run_lifecycle import authoritative_execution_status, initialize_execution, synchronize_projection, transition_execution
from .util import (
    atomic_write_bytes,
    atomic_write_json,
    expand_path,
    sha256_file,
    utc_now,
    validate_id,
)
from .path import absolute_path, read_regular_file, require_directory
















def _bind_native_job(
    *,
    job_path: Path,
    prompt_path: Path,
    workdir: Path,
    ticket_id: str | None,
    pack_id: str | None,
) -> ValidatedNativeJob:
    """Perform all job checks before any runtime state is created."""
    pack_root = _discover_prompt_pack_root(prompt_path)
    if pack_root is None:
        raise WorkflowError("--job requires a prompt under a selected prompt pack")
    job = validate_native_job(absolute_path(job_path), pack_root=pack_root)
    if job.prompt_path != absolute_path(prompt_path):
        raise WorkflowError(
            "native job prompt_path disagrees with launch prompt: "
            f"{job.prompt_relative_path}"
        )
    expected_workdir = require_directory(pack_root / job.worktree_target, label="native job worktree target")
    if expected_workdir != absolute_path(workdir):
        raise WorkflowError(
            "native job worktree_target disagrees with launch workdir: "
            f"expected {expected_workdir}, got {absolute_path(workdir)}"
        )
    if ticket_id is not None and ticket_id != job.ticket_id:
        raise WorkflowError(
            f"--ticket disagrees with native job: {ticket_id} != {job.ticket_id}"
        )
    selected_pack_id = _pack_id(pack_root)
    if pack_id is not None and pack_id != selected_pack_id:
        raise WorkflowError(
            f"--pack disagrees with selected pack: {pack_id} != {selected_pack_id}"
        )
    return job


def _write_job_binding(state_dir: Path, job: ValidatedNativeJob, *, agent_run_id: str, workdir: Path) -> dict[str, Any]:
    """Snapshot the validated source bytes and write the immutable binding receipt."""
    paths = AgentRunPaths(state_dir)
    stored = paths.native_job
    stored.parent.mkdir(parents=True, exist_ok=True)
    raw = job.job_bytes
    source_sha256 = job.job_sha256
    atomic_write_bytes(stored, raw, mode=0o444)
    stored_sha256 = sha256_file(stored)
    if source_sha256 != stored_sha256:
        raise WorkflowError("native job changed while its binding was being created")
    receipt = {
        "schema": "agent-workflow/job-binding/v1",
        "bound_at": utc_now(),
        "agent_run_id": agent_run_id,
        "run_dir": str(state_dir),
        "job_id": job.job_id,
        "ticket_id": job.ticket_id,
        "pack_root": str(job.pack_root),
        "worktree": str(workdir),
        "worktree_target": job.worktree_target,
        "prompt_source_path": str(job.prompt_path),
        "job_source_path": str(job.job_path),
        "job_source_sha256": source_sha256,
        "job_stored_path": str(stored),
        "job_stored_sha256": stored_sha256,
        "path_policy": {
            "allowed_paths": list(job.path_policy.allowed_paths),
            "forbidden_paths": list(job.path_policy.forbidden_paths),
        },
        "acceptance_commands": [
            {
                "id": command.id,
                "argv": list(command.argv),
                "cwd": command.cwd,
                "timeout_seconds": command.timeout_seconds,
                "result_format": command.result_format,
                "junit_path": command.junit_path,
            }
            for command in job.acceptance_commands
        ],
        "review_requirement": {
            "required": job.review_requirement.required,
            "independent": job.review_requirement.independent,
        },
    }
    receipt_path = paths.job_binding
    atomic_write_json(receipt_path, receipt, mode=0o444)
    return receipt


def _write_launch_prompt(
    state_dir: Path,
    *,
    agent_run_id: str,
    agent_name: str | None,
    agent_class: str | None,
    role_id: str,
    role_digest: str,
    role_instructions: str | None,
    tier: str | None,
    retry_of: str | None,
    created_at: str,
    prompt_source: Path,
    prompt_pack_root: Path | None,
    handoff_dir: Path,
    result_contract: dict[str, Any] | None = None,
    interactive: bool = False,
    detached_interactive: bool = False,
    command_artifacts: dict[str, Any],
    steering_adapter: str = "unsupported",
) -> Path:
    paths = AgentRunPaths(state_dir)
    context = [
        "# Agent-workflow launch context",
        "The complete ticket follows this runtime contract; do not reread prompt_source unless the ticket requires it.",
        f"- run: `{agent_run_id}`; role: `{role_id}`; role_digest: `{role_digest}`",
        f"- prompt_source: `{prompt_source}`",
        f"- command_profile: `{command_artifacts['role']}`",
        "- Use `AGENT_WORKFLOW_CLI` with signatures from `AGENT_WORKFLOW_COMMAND_CARD` / `AGENT_WORKFLOW_COMMAND_CATALOG`; do not browse `--help` unless the scoped contract is missing, mismatched, or rejects an argument.",
        "- Review/accept/reject/force-accept are host-only disposition authority. Child runs report evidence/recommendations and never invoke them.",
    ]
    if role_instructions is not None:
        context.extend(["", "## Role contract", role_instructions.strip(), ""])
    if prompt_pack_root is not None:
        context.append(f"- prompt_pack_root: `{prompt_pack_root}`")
    if result_contract is not None:
        context.append(
            f"- task_result: write atomic `AGENT_WORKFLOW_HANDOFF_DIR/result.json` satisfying `{result_contract['schema']}`."
        )
    if interactive:
        if steering_adapter != "unsupported":
            context.append("- Interactive steering is durable; acknowledge a steer message ID before treating it as applied.")
        else:
            context.append("- No evidence-capable steering adapter is available; never wait for approval/input. Report blocked/partial completion when authorization is required.")
        context.extend(
            [
                "- Before finishing, run `agent completion-validate`; then use `agent task-complete ...`. The host seals/terminates the run.",
            ]
        )
    elif detached_interactive:
        context.append("- Headless worker: never wait for terminal/user input; write the durable completion handoff, emit concise progress when useful, then exit. Do not call `agent task-complete`.")
    else:
        context.append("- Structured non-interactive worker: write the durable completion handoff and exit. Do not call `agent task-complete`.")
    context.extend(
        [
            f"- handoff: `{handoff_dir}`; template: `{handoff_dir / 'completion-template.json'}` (read-only)",
            "- Copy the template to atomic `completion.json` and satisfy `agent-workflow/completion/v1`. Runtime completion paths outside the handoff directory are collector-owned.",
            "- Review runs keep `result` separate from `review_disposition` (`approved|changes_requested|blocked`). Completion is never acceptance.",
            "- `result: completed` normally requires no unresolved items and only final passing verification commands; completed reviews may cite a failed target gate only with `changes_requested`.",
            "- Durable progress/steering uses the scoped `progress`, `steer`, and `ack` commands; acknowledge steering before applying it and never expose secrets.",
            "",
            "---",
            "",
        ]
    )
    launch_prompt = paths.launch_prompt
    launch_prompt.write_text(
        "\n".join(context)
        + (paths.prompt).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return launch_prompt


def _write_agent_run_contract(
    state_dir: Path,
    *,
    agent_run_id: str,
    agent_name: str | None,
    agent_class: str | None,
    role_id: str,
    role_digest: str,
    tier: str | None,
    retry_of: str | None,
    created_at: str,
    ticket_id: str | None,
    pack_id: str | None,
    pack_root: Path | None,
    workdir: Path,
    source_revision: str | None,
    branch: str | None,
    dirty_at_launch: bool | None,
    prompt_source: Path,
    prompt_sha256: str,
    launch_prompt_sha256: str,
    command: list[str],
    noninteractive_command: list[str] | None,
    redacted_command: list[str],
    executor: str | None,
    model: str | None,
    reasoning_effort: str | None,
    stream_format: str,
    interactive: bool,
    executor_interactive: bool,
    worker_mode: str,
    environment_allowlist: list[str],
    handoff_dir: Path,
    result_contract: dict[str, Any] | None,
    runtime_policy: dict[str, Any],
    evaluation_policy: dict[str, Any],
    source_baseline_sha256: str,
    pack_manifest_sha256: str | None,
    command_artifacts: dict[str, Any],
) -> Path:
    """Write the one immutable authority consumed by the runner and collectors."""
    task_result_schema = None
    if result_contract is not None and pack_root is not None:
        schema_rel = result_contract.get("schema")
        if isinstance(schema_rel, str) and schema_rel:
            schema_path = absolute_path(pack_root / schema_rel)
            try:
                schema_read = read_regular_file(schema_path)
            except WorkflowError as exc:
                raise WorkflowError("task result schema is not a safe regular file") from exc
            try:
                schema_value = json.loads(schema_read.data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise WorkflowError("task result schema is not valid JSON") from exc
            schema_id = schema_value.get("$id") if isinstance(schema_value, dict) else None
            if not isinstance(schema_id, str) or not schema_id:
                # A task schema may be deliberately anonymous.  Its safe,
                # immutable identity is the pack-relative path plus digest.
                schema_id = str(schema_rel)
            task_result_schema = {"id": schema_id, "sha256": schema_read.sha256}
    contract = {
        "schema": "agent-workflow/agent-run-contract/v1",
        "version": 1,
        "agent_run": {
            "id": agent_run_id,
            "agent_name": agent_name,
            "agent_class": agent_class,
            "tier": tier,
            "retry_of_agent_run_id": retry_of,
            "created_at": created_at,
        },
        "role": {
            "schema": "agent-workflow/agent-role/v1",
            "id": role_id,
            "digest": role_digest,
        },
        "ticket": ticket_id,
        # Completion identity is explicit in the immutable contract.  Review
        # launches that omit a ticket deliberately require the child to omit
        # it too; this is different from accepting an arbitrary child ticket.
        "ticket_identity": {
            "mode": "explicit" if ticket_id is not None else "omitted",
            "value": ticket_id,
        },
        "pack": {
            "id": pack_id,
            "root": str(pack_root) if pack_root is not None else None,
            "manifest_sha256": pack_manifest_sha256,
        },
        "worktree": {
            "path": str(workdir),
            "source_revision": source_revision,
            "branch": branch,
            "dirty_at_launch": dirty_at_launch,
        },
        "prompt": {
            "source": str(prompt_source),
            "stored": "prompt.md",
            "sha256": prompt_sha256,
            "launch_stored": "launch-prompt.md",
            "launch_sha256": launch_prompt_sha256,
        },
        "worker_plan": {
            "argv": list(redacted_command),
            "command_sha256": hashlib.sha256(
                json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "noninteractive_argv": list(noninteractive_command or command),
            "noninteractive_command_sha256": hashlib.sha256(
                json.dumps(
                    noninteractive_command or command,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "stream_format": stream_format,
            "mode": worker_mode,
            "interactive_stdio": executor_interactive,
            "environment_allowlist": list(environment_allowlist),
            "executor": executor,
            "model": model,
        },
        "paths": {
            "run_dir": ".",
            "workdir": str(workdir),
            "handoff_dir": str(handoff_dir),
            "completion": "completion.json",
            "result": "result.json",
            "result_contract": result_contract,
            "runtime": "evaluation-runtime.json",
            "source_baseline": "source-baseline.json",
        },
        "schemas": {
            "launch": schema_descriptor("agent-workflow/agent-run-contract/v1"),
            "command_catalog": schema_descriptor("agent-workflow/command-catalog/v1"),
            "completion": schema_descriptor("agent-workflow/completion/v1"),
            "provenance": schema_descriptor("agent-workflow/run-provenance/v1"),
            "status": schema_descriptor("agent-workflow/agent-run-status/v1"),
            "source_baseline": schema_descriptor("agent-workflow/source-baseline/v1"),
            "completion_collection": schema_descriptor("agent-workflow/completion-collection/v1"),
            "task_result": task_result_schema,
        },
        "runtime_policy": runtime_policy,
        "evaluation_policy": evaluation_policy,
        "source_baseline": {"path": "source-baseline.json", "sha256": source_baseline_sha256},
        "command_catalog": command_artifacts,
        "expected_outputs": {
            "output_log": "output.log",
            "executor_events": "executor-events.jsonl",
            "executor_stderr": "executor-stderr.log",
            "final_status": "final-status.json",
            "final_receipt": "final-receipt.json",
        },
    }
    path = AgentRunPaths(state_dir).contract
    atomic_write_json(path, contract, mode=0o444)
    return path


@dataclass(frozen=True, slots=True)
class PreparedWorker:
    """Resolved worker command and policy produced during Agent Run preparation."""

    plan: ExecutorPlan
    command: tuple[str, ...]
    noninteractive_command: tuple[str, ...] | None
    redacted_command: tuple[str, ...]
    compatibility: dict[str, Any]
    executor_policy: Any
    environment_allowlist: tuple[str, ...]



@dataclass(frozen=True, slots=True)
class PreparedAgentRun:
    """Prepared run artifacts used to create the initial status projection."""

    paths: AgentRunPaths
    agent_run_id: str
    ticket_id: str | None
    agent_name: str | None
    agent_class: str | None
    role_id: str
    role_digest: str
    tier: str | None
    pack_id: str | None
    retry_of: str | None
    created_at: str
    workdir: Path
    prompt_source: Path
    prompt_pack_root: Path | None
    worker: PreparedWorker
    worker_mode: str
    result_contract: dict[str, Any] | None
    handoff_dir: Path
    launch_prompt: Path
    contract_path: Path
    job_binding: dict[str, Any] | None
    job_id: str | None
    evaluation_path: Path | None
    git_info: dict[str, Any]

    def initial_status(self) -> dict[str, Any]:
        policy = self.worker.executor_policy
        steering_adapter = policy.steering_adapter if policy else "unsupported"
        return {
            "schema": "agent-workflow/agent-run-status/v1",
            "agent_run_id": self.agent_run_id,
            "ticket_id": self.ticket_id,
            "agent_name": self.agent_name,
            "agent_class": self.agent_class,
            "role": self.role_id,
            "role_digest": self.role_digest,
            "tier": self.tier,
            "pack_id": self.pack_id,
            "retry_of_agent_run_id": self.retry_of,
            "status": "prepared",
            "disposition": None,
            "created_at": self.created_at,
            "updated_at": self.created_at,
            "workdir": str(self.workdir),
            "prompt_path": str(self.paths.prompt),
            "prompt_source": str(self.prompt_source),
            "worker_mode": self.worker_mode,
            "worker_id": None,
            "worker_pid": None,
            "worker_process_group_id": None,
            "worker_alive": None,
            "agent_context_path": str(self.paths.agent_context),
            "prompt_sha256": sha256_file(self.paths.prompt),
            "prompt_pack_root": (
                str(self.prompt_pack_root) if self.prompt_pack_root else None
            ),
            "result_contract": self.result_contract,
            "launch_prompt_path": str(self.launch_prompt),
            "launch_prompt_sha256": sha256_file(self.launch_prompt),
            "log_path": str(self.paths.output_log),
            "command_path": str(self.paths.command),
            "completion_path": str(self.paths.completion_markdown),
            "completion_json_path": str(self.paths.completion),
            "handoff_dir": str(self.handoff_dir),
            "completion_collection_path": str(
                self.paths.collection("completion.json")
            ),
            "completion_validation_status": None,
            "steering_adapter": steering_adapter,
            "steering_supported": steering_adapter != "unsupported",
            "steering_reason": (
                "configured evidence-capable adapter"
                if steering_adapter != "unsupported"
                else "executor has no configured evidence-capable late-steering adapter"
            ),
            "provenance_path": str(self.paths.provenance),
            "events_path": str(self.paths.executor_events),
            "stderr_path": str(self.paths.executor_stderr),
            "final_receipt_path": None,
            "evaluation_path": (
                str(expand_path(self.evaluation_path)) if self.evaluation_path else None
            ),
            "source_baseline_path": str(self.paths.source_baseline),
            "agent_run_contract_path": str(self.contract_path),
            "job_binding_path": str(self.paths.job_binding) if self.job_binding else None,
            "job_binding_sha256": (
                sha256_file(self.paths.job_binding) if self.job_binding else None
            ),
            "job_id": self.job_id,
            **self.git_info,
        }

def _prepare_worker(
    settings: Settings,
    *,
    executor: str | None,
    explicit_command: list[str] | None,
    structured: bool,
    executor_interactive: bool,
    model: str | None,
    reasoning_effort: str | None,
    allow_no_go_model: bool,
    saved_stream_format: str | None,
    saved_executor: str | None,
    handoff_dir: Path,
) -> PreparedWorker:
    plan = prepare_executor(
        settings,
        executor,
        explicit_command,
        structured=structured,
        interactive=executor_interactive,
        model=model,
        reasoning_effort=reasoning_effort,
        allow_no_go_model=allow_no_go_model,
    )
    if saved_stream_format is not None:
        plan = ExecutorPlan(
            saved_executor,
            plan.argv,
            saved_stream_format,
            plan.model,
            plan.no_go_authorized,
            plan.reasoning_effort,
        )
    command = list(plan.argv)
    command[0] = require_command(command[0])
    if plan.name == "codex" and "--add-dir" not in command:
        command.extend(["--add-dir", str(handoff_dir)])
    plan = ExecutorPlan(
        plan.name,
        tuple(command),
        plan.stream_format,
        plan.model,
        plan.no_go_authorized,
        plan.reasoning_effort,
    )
    noninteractive_command: tuple[str, ...] | None = None
    if executor_interactive and plan.name in settings.executors:
        noninteractive_plan = prepare_executor(
            settings,
            plan.name,
            None,
            structured=structured,
            interactive=False,
            model=plan.model,
            reasoning_effort=plan.reasoning_effort,
            allow_no_go_model=allow_no_go_model,
        )
        noninteractive = list(noninteractive_plan.argv)
        noninteractive[0] = require_command(noninteractive[0])
        if noninteractive_plan.name == "codex" and "--add-dir" not in noninteractive:
            noninteractive.extend(["--add-dir", str(handoff_dir)])
        noninteractive_command = tuple(noninteractive)
    compatibility = probe_executor(
        plan.name,
        command,
        digest=settings.security.executable_digest,
    )
    if (
        plan.name is not None
        and settings.security.mode in {"governed", "release"}
        and compatibility.get("decision") != "supported"
    ):
        raise WorkflowError(
            "executor compatibility rejected: "
            f"{compatibility.get('explanation_code', 'COMPAT-UNKNOWN')}; "
            "governed launches do not silently downgrade to unclassified execution"
        )
    secret_values = secret_values_from_argv(command)
    redacted = redact_argv(command, secret_values=secret_values)
    policy = settings.executor_policies.get(plan.name)
    allowlist = tuple(policy.environment_allowlist) if policy else ()
    return PreparedWorker(
        plan=plan,
        command=tuple(command),
        noninteractive_command=noninteractive_command,
        redacted_command=tuple(redacted),
        compatibility=compatibility,
        executor_policy=policy,
        environment_allowlist=allowlist,
    )


def _write_source_baseline(
    paths: AgentRunPaths,
    *,
    workdir: Path,
    preflight_snapshot: Any,
) -> dict[str, Any]:
    try:
        snap = preflight_snapshot or snapshot(workdir)
        git_info = {
            "repository_root": str(snap.root),
            "source_revision": snap.head,
            "branch": snap.branch,
            "dirty_at_launch": snap.dirty,
        }
        primary = {
            "path": str(snap.root),
            "head": snap.head,
            "branch": snap.branch,
            "dirty": snap.dirty,
        }
    except WorkflowError:
        git_info = {
            "repository_root": None,
            "source_revision": None,
            "branch": None,
            "dirty_at_launch": None,
        }
        primary = {
            "path": str(workdir),
            "head": "",
            "branch": "",
            "dirty": False,
        }
    atomic_write_json(
        paths.source_baseline,
        {
            "schema": "agent-workflow/source-baseline/v1",
            "generated_at": utc_now(),
            "components": {"primary": primary},
        },
    )
    return git_info


def _prepare_evaluation(
    paths: AgentRunPaths,
    *,
    state_dir: Path,
    workdir: Path,
    prompt_pack_root: Path | None,
    evaluation_path: Path | None,
    ticket_id: str | None,
    native_job: ValidatedNativeJob | None,
    environment_allowlist: list[str],
    steering_adapter: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Materialize baseline evaluation/scope policy for a prepared Agent Run."""
    runtime_policy: dict[str, Any] = {
        "steering": {
            "adapter": steering_adapter,
            "deadline_seconds": 300,
            "max_attempts": 1,
        }
    }
    evaluation_policy: dict[str, Any] = {}
    if evaluation_path is None and native_job is None:
        return runtime_policy, evaluation_policy

    evaluation = None
    evaluation_data: dict[str, Any] = {}
    if evaluation_path is not None:
        evaluation = validate_evaluation(
            expand_path(evaluation_path),
            pack_root=prompt_pack_root,
        )
        if ticket_id and ticket_id not in evaluation.task_ids:
            raise WorkflowError(
                f"evaluation plan does not include launched ticket: {ticket_id}"
            )
        evaluation_data = evaluation.data

    commands = (
        [
            {
                "id": command.id,
                "argv": list(command.argv),
                "cwd": command.cwd,
                "timeout_seconds": command.timeout_seconds,
                "result_format": command.result_format,
                "junit_path": command.junit_path,
            }
            for command in native_job.acceptance_commands
        ]
        if native_job is not None
        else evaluation_data.get("acceptance_commands", [])
    )
    scope_data = (
        {
            "writable_paths": list(native_job.path_policy.allowed_paths),
            "disposable_trees": [".agent-workflow-handoff/", ".delegations/"],
        }
        if native_job is not None
        else evaluation_data.get("scope", {})
    )
    runtime = {
        "schema": "agent-workflow/evaluation-runtime/v1",
        "evaluation_path": str(evaluation.path) if evaluation is not None else None,
        "evaluation_sha256": evaluation.sha256 if evaluation is not None else None,
        "timeout_seconds": evaluation_data.get("timeout_seconds"),
        "acceptance_commands": commands,
        "scope": scope_data,
        "scorers": evaluation_data.get("scorers", []),
        "oracle_refs": evaluation_data.get("oracle_refs", {}),
        "statistics_policy": evaluation_data.get(
            "statistics_policy", "agent-workflow/statistics/v1"
        ),
        "ticket_id": ticket_id,
        "native_job_binding_sha256": (
            sha256_file(paths.job_binding) if native_job is not None else None
        ),
    }
    if evaluation is not None:
        update_provenance(
            state_dir,
            budgets=evaluation_data.get("budgets", {}),
            evaluation_sha256=evaluation.sha256,
        )
    atomic_write_json(paths.evaluation_runtime, runtime)
    runtime_policy = {
        "timeout_seconds": runtime.get("timeout_seconds"),
        "budgets": evaluation_data.get("budgets", {}),
        "environment_allowlist": environment_allowlist,
        "steering": {
            "adapter": steering_adapter,
            "deadline_seconds": 300,
            "max_attempts": 1,
        },
    }
    evaluation_policy = {
        "path": str(evaluation.path) if evaluation is not None else None,
        "sha256": evaluation.sha256 if evaluation is not None else None,
        "ticket_id": ticket_id,
        "acceptance_commands": commands,
        "scope": scope_data,
        "scorers": evaluation_data.get("scorers", []),
        "oracle_refs": evaluation_data.get("oracle_refs", {}),
        "statistics_policy": evaluation_data.get(
            "statistics_policy", "agent-workflow/statistics/v1"
        ),
    }
    if commands or native_job is not None:
        collect_commands(
            workdir,
            specs_from_data(commands),
            phase="baseline",
            receipt_dir=paths.collections,
        )
    policy = ScopePolicy(
        authorized_root=workdir,
        writable_paths=tuple(scope_data.get("writable_paths", ())),
        writable_trees=tuple(scope_data.get("writable_trees", ())),
        disposable_trees=tuple(scope_data.get("disposable_trees", ())),
    )
    collect_scope(
        workdir,
        phase="baseline",
        policy=policy,
        receipt_dir=paths.scope,
    )
    return runtime_policy, evaluation_policy

def prepare(
    settings: Settings,
    *,
    agent_run_id: str,
    workdir: Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """Prepare an Agent Run transactionally, preserving preflight evidence."""
    state_dir = run_dir(settings, agent_run_id)
    handoff_dir = absolute_path(workdir) / ".agent-workflow-handoff" / agent_run_id
    state_existed = state_dir.exists()
    handoff_existed = handoff_dir.exists() or handoff_dir.is_symlink()
    try:
        return _prepare(
            settings,
            agent_run_id=agent_run_id,
            workdir=workdir,
            **kwargs,
        )
    except BaseException:
        # The preflight-failure record is intentional durable evidence.
        preserve_preflight = (state_dir / "preflight.json").is_file()
        if not state_existed and state_dir.exists() and not preserve_preflight:
            if state_dir.is_symlink():
                state_dir.unlink()
            else:
                shutil.rmtree(state_dir)
        if not handoff_existed and handoff_dir.exists():
            if handoff_dir.is_symlink():
                handoff_dir.unlink()
            else:
                shutil.rmtree(handoff_dir)
        release_agent_name(
            settings,
            agent_name=None,
            agent_run_id=agent_run_id,
        )
        raise


def _prepare(
    settings: Settings,
    *,
    agent_run_id: str,
    workdir: Path,
    prompt_path: Path,
    executor: str | None = None,
    agent_name: str | None = None,
    role: str | None = None,
    agent_class: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    allow_no_go_model: bool = False,
    explicit_command: list[str] | None = None,
    ticket_id: str | None = None,
    pack_id: str | None = None,
    retry_of: str | None = None,
    allow_dirty: bool = False,
    structured: bool = False,
    interactive: bool | None = None,
    prerequisite_ids: list[str] | None = None,
    saved_stream_format: str | None = None,
    saved_executor: str | None = None,
    prompt_source_override: Path | None = None,
    prompt_pack_root_override: Path | None = None,
    evaluation_path: Path | None = None,
    tier: str | None = None,
    job_path: Path | None = None,
    allow_active_agent_name: bool = False,
    workflow_context: dict[str, Any] | None = None,
    worker_mode: str = "headless",
) -> dict[str, Any]:
    validate_id(agent_run_id, "agent run ID")
    if ticket_id:
        validate_id(ticket_id, "ticket ID")
    if pack_id:
        validate_id(pack_id, "pack ID")
    workdir = require_directory(absolute_path(workdir), label="workdir")
    enforce_trust(settings, workdir=workdir)
    prompt_path = absolute_path(prompt_path)
    prompt_source = absolute_path(prompt_source_override or prompt_path)
    try:
        prompt_read = read_regular_file(prompt_source)
    except WorkflowError as exc:
        raise WorkflowError(f"prompt is not a regular file: {prompt_source.name}") from exc
    preflight = resolve_prerequisites(settings, prerequisite_ids or [])
    if preflight["status"] != "accepted":
        state_dir = run_dir(settings, agent_run_id)
        if state_dir.exists() and any(state_dir.iterdir()):
            raise preflight_error(preflight)
        state_dir.mkdir(parents=True, exist_ok=True)
        paths = AgentRunPaths(state_dir)
        created_at = utc_now()
        atomic_write_json(paths.preflight, preflight, mode=0o444)
        paths.output_log.touch()
        initialize_execution(
            settings,
            agent_run_id,
            preflight_run_record(
                agent_run_id=agent_run_id,
                ticket_id=ticket_id,
                pack_id=pack_id,
                workdir=workdir,
                prompt_path=prompt_source,
                log_path=paths.output_log,
                preflight=preflight,
                created_at=created_at,
            ),
        )
        raise preflight_error(preflight)
    native_job: ValidatedNativeJob | None = None
    if job_path is not None:
        native_job = _bind_native_job(
            job_path=job_path, prompt_path=prompt_source,
            workdir=workdir, ticket_id=ticket_id, pack_id=pack_id,
        )
    if native_job is not None:
        ticket_id = native_job.ticket_id
        pack_id = _pack_id(native_job.pack_root)
    if worker_mode not in {"headless", "external"}:
        raise WorkflowError("worker_mode must be 'headless' or 'external'")
    # Headless execution is the core default. External workers may request an
    # interactive provider command, but Agent-Workflow never creates or models
    # terminal topology.
    if worker_mode == "headless":
        interactive = False
    elif interactive is None:
        interactive = True
    identity = resolve_agent_identity(
        settings,
        requested_name=agent_name,
        requested_role=role,
        requested_class=agent_class,
        executor=executor,
        model=model,
        allow_no_go_model=allow_no_go_model,
        explicit_command=explicit_command,
        interactive=interactive,
        reasoning_effort=reasoning_effort,
        allow_active_name=allow_active_agent_name,
    )
    agent_name = identity.agent_name
    agent_class = identity.agent_class
    role_id = identity.role_id
    role_digest = identity.role_digest
    role_instructions = identity.role_instructions
    command_profile = identity.command_profile
    runtime_alias = identity.runtime_alias
    executor = identity.executor
    model = identity.model
    reasoning_effort = identity.reasoning_effort
    allow_no_go_model = identity.allow_no_go_model
    interactive = identity.interactive
    # Review runs may be sent through the host acceptance gate.  Bind their
    # risk tier before any mutable child-controlled state exists; accepting a
    # review with a missing tier would otherwise fail only after inspection.
    if agent_class == "review" and tier is None:
        raise WorkflowError(
            "acceptance-capable review requires a recorded launch tier; use --tier"
        )
    if tier is not None and tier not in {"low", "medium", "high", "critical"}:
        raise WorkflowError(f"unsupported launch tier: {tier!r}")
    executor_interactive = worker_mode == "external" and bool(interactive) and not structured

    preflight_snapshot = None
    try:
        preflight_snapshot = snapshot(workdir)
    except WorkflowError:
        # Non-Git workdirs are supported for general terminal delegation.
        pass
    if (
        preflight_snapshot is not None
        and preflight_snapshot.dirty
        and settings.require_clean_source
        and not allow_dirty
    ):
        raise WorkflowError(
            f"worktree is dirty: {preflight_snapshot.root}; "
            "commit/stash changes or pass --allow-dirty"
        )

    state_dir = run_dir(settings, agent_run_id)
    if state_dir.exists():
        if any(state_dir.iterdir()):
            raise WorkflowError(
                f"run state already exists: {state_dir}; use a new agent run ID"
            )
    else:
        state_dir.mkdir(parents=True)

    paths = AgentRunPaths(state_dir)

    job_binding = (
        _write_job_binding(state_dir, native_job, agent_run_id=agent_run_id, workdir=workdir)
        if native_job is not None
        else None
    )
    handoff_dir = _create_handoff_dir(workdir, agent_run_id)
    (handoff_dir / "control-intents").mkdir(mode=0o700)
    (handoff_dir / "steering-inbox").mkdir(mode=0o700)
    prepared_worker = _prepare_worker(
        settings,
        executor=executor,
        explicit_command=explicit_command,
        structured=structured,
        executor_interactive=executor_interactive,
        model=model,
        reasoning_effort=reasoning_effort,
        allow_no_go_model=allow_no_go_model,
        saved_stream_format=saved_stream_format,
        saved_executor=saved_executor,
        handoff_dir=handoff_dir,
    )
    executor_plan = prepared_worker.plan
    command = list(prepared_worker.command)
    redacted_command = list(prepared_worker.redacted_command)
    compatibility = prepared_worker.compatibility
    executor_policy = prepared_worker.executor_policy
    environment_allowlist = list(prepared_worker.environment_allowlist)
    runtime_policy: dict[str, Any] = {
        "no_go_authorized": executor_plan.no_go_authorized,
        "codex_reasoning_effort": executor_plan.reasoning_effort,
        "steering": {
            "adapter": (executor_policy.steering_adapter if executor_policy else "unsupported"),
            "deadline_seconds": 300,
            "max_attempts": 1,
        },
    }
    evaluation_policy: dict[str, Any] = {}

    prompt_copy = paths.prompt
    atomic_write_bytes(
        prompt_copy,
        native_job.prompt_bytes if native_job is not None else prompt_read.data,
        mode=0o444,
    )
    prompt_pack_root = (
        prompt_pack_root_override
        if prompt_pack_root_override is not None
        else _discover_prompt_pack_root(prompt_source)
    )
    (paths.output_log).touch()
    atomic_write_json(
        paths.command,
        {
            "schema": "agent-workflow/command/v1",
            "argv": redacted_command,
            "shell": shlex.join(redacted_command),
            "executor": executor_plan.name,
            "classification": "named" if executor_plan.name else "unclassified",
            "stream_format": executor_plan.stream_format,
            "mode": "external" if interactive else "headless",
            "interactive_stdio": executor_interactive,
            "model": executor_plan.model,
            "no_go_authorized": executor_plan.no_go_authorized,
            "agent_name": agent_name,
            "agent_class": agent_class,
            "role": role_id,
            "role_digest": role_digest,
            "runtime_alias": runtime_alias,
            "environment_allowlist": environment_allowlist,
        },
        mode=0o444,
    )
    (paths.completion_markdown).write_bytes(
        asset_path("prompt-pack-root/templates/TICKET_COMPLETION.md").read_bytes()
    )
    result_contract = (
        task_result_contract(prompt_pack_root, ticket_id)
        if prompt_pack_root is not None
        else None
    )
    created_at = utc_now()
    command_artifacts = write_launch_command_artifacts(
        state_dir,
        role=command_profile,
        settings=settings,
        agent_visible_dir=handoff_dir,
    )
    launch_prompt = _write_launch_prompt(
        state_dir,
        agent_run_id=agent_run_id,
        agent_name=agent_name,
        agent_class=agent_class,
        role_id=role_id,
        role_digest=role_digest,
        role_instructions=role_instructions,
        tier=tier,
        retry_of=retry_of,
        created_at=created_at,
        prompt_source=prompt_source,
        prompt_pack_root=prompt_pack_root,
        handoff_dir=handoff_dir,
        result_contract=result_contract,
        interactive=interactive,
        detached_interactive=not interactive and executor_interactive,
        command_artifacts=command_artifacts,
        steering_adapter=(executor_policy.steering_adapter if executor_policy else "unsupported"),
    )

    git_info = _write_source_baseline(
        paths, workdir=workdir, preflight_snapshot=preflight_snapshot
    )
    baseline_path = paths.source_baseline

    completion_path = paths.completion
    completion_template_path = handoff_dir / "completion-template.json"
    atomic_write_json(
        completion_template_path,
        completion_template(
            agent_run_id=agent_run_id,
            ticket_id=ticket_id,
            pack_id=pack_id,
            base_revision=git_info["source_revision"],
            review=command_profile == "review",
        ),
        mode=0o444,
    )
    atomic_write_json(
        completion_path,
        initial_completion(
            agent_run_id=agent_run_id,
            ticket_id=ticket_id,
            pack_id=pack_id,
            base_revision=git_info["source_revision"],
        ),
    )
    events_path = paths.executor_events
    stderr_path = paths.executor_stderr
    events_path.touch()
    stderr_path.touch()
    config_sha256 = (
        sha256_file(settings.config_path)
        if settings.config_path and settings.config_path.is_file()
        else None
    )
    pack_manifest = prompt_pack_root / "MANIFEST.sha256" if prompt_pack_root else None
    provenance_path = paths.provenance
    atomic_write_json(
        provenance_path,
        initial_provenance(
            agent_run_id=agent_run_id,
            executor=executor_plan.name,
            argv=list(redacted_command),
            stream_format=executor_plan.stream_format,
            executor_version=(
                executor_identity_for_plan(executor_plan).version
                if executor_plan.name is not None
                else None
            ),
            executable=(
                executor_identity_for_plan(executor_plan).as_dict()
                if executor_plan.name is not None
                else None
            ),
            compatibility=compatibility,
            model=executor_plan.model,
            agent_name=agent_name,
            agent_class=agent_class,
            model_policy={
                "no_go_authorized": executor_plan.no_go_authorized,
                "authorization_source": "--allow-no-go-model" if executor_plan.no_go_authorized else None,
            },
            prompt_sha256=sha256_file(prompt_copy),
            launch_prompt_sha256=sha256_file(launch_prompt),
            config_sha256=config_sha256,
            pack_manifest_sha256=(
                sha256_file(pack_manifest)
                if pack_manifest is not None and pack_manifest.is_file()
                else None
            ),
            source_revision=git_info["source_revision"],
            worktree=workdir,
            environment={
                "python": platform.python_version(),
                "platform": platform.platform(),
                "implementation": sys.implementation.name,
                "policy": "controlled",
                "allowlist": environment_allowlist,
            },
            retry_of_agent_run_id=retry_of,
            job_binding=(
                {
                    "path": str(paths.job_binding),
                    "sha256": sha256_file(paths.job_binding),
                    "job_id": native_job.job_id,
                }
                if native_job is not None
                else None
            ),
        ),
    )
    if workflow_context is not None:
        from .contracts import validate_instance
        validate_instance(
            workflow_context,
            "agent-workflow/workflow-input-bindings/v1",
            artifact="workflow launch inputs",
        )
        workflow_inputs_path = paths.workflow_inputs
        atomic_write_json(workflow_inputs_path, workflow_context, mode=0o444)
        update_provenance(
            state_dir,
            workflow={
                "workflow_id": workflow_context["workflow_id"],
                "node_id": workflow_context["node_id"],
                "attempt": workflow_context["attempt"],
                "inputs_path": str(workflow_inputs_path),
                "inputs_sha256": sha256_file(workflow_inputs_path),
                "routing": None,
            },
        )
    if evaluation_path is not None or native_job is not None:
        runtime_policy, evaluation_policy = _prepare_evaluation(
            paths,
            state_dir=state_dir,
            workdir=workdir,
            prompt_pack_root=prompt_pack_root,
            evaluation_path=evaluation_path,
            ticket_id=ticket_id,
            native_job=native_job,
            environment_allowlist=environment_allowlist,
            steering_adapter=(
                executor_policy.steering_adapter if executor_policy else "unsupported"
            ),
        )

    agent_run_contract = _write_agent_run_contract(
        state_dir,
        agent_run_id=agent_run_id,
        agent_name=agent_name,
        agent_class=agent_class,
        role_id=role_id,
        role_digest=role_digest,
        tier=tier,
        retry_of=retry_of,
        created_at=created_at,
        ticket_id=ticket_id,
        pack_id=pack_id,
        pack_root=prompt_pack_root,
        workdir=workdir,
        source_revision=git_info["source_revision"],
        branch=git_info["branch"],
        dirty_at_launch=git_info["dirty_at_launch"],
        prompt_source=prompt_source,
        prompt_sha256=sha256_file(prompt_copy),
        launch_prompt_sha256=sha256_file(launch_prompt),
        command=command,
        noninteractive_command=(
            list(prepared_worker.noninteractive_command)
            if prepared_worker.noninteractive_command
            else None
        ),
        redacted_command=redacted_command,
        executor=executor_plan.name,
        model=executor_plan.model,
        reasoning_effort=executor_plan.reasoning_effort,
        stream_format=executor_plan.stream_format,
        interactive=bool(interactive),
        executor_interactive=executor_interactive,
        worker_mode=worker_mode,
        environment_allowlist=environment_allowlist,
        handoff_dir=handoff_dir,
        result_contract=result_contract,
        runtime_policy=runtime_policy,
        evaluation_policy=evaluation_policy,
        source_baseline_sha256=sha256_file(baseline_path),
        pack_manifest_sha256=(
            sha256_file(pack_manifest)
            if pack_manifest is not None and pack_manifest.is_file()
            else None
        ),
        command_artifacts=command_artifacts,
    )

    prepared = PreparedAgentRun(
        paths=paths,
        agent_run_id=agent_run_id,
        ticket_id=ticket_id,
        agent_name=agent_name,
        agent_class=agent_class,
        role_id=role_id,
        role_digest=role_digest,
        tier=tier,
        pack_id=pack_id,
        retry_of=retry_of,
        created_at=created_at,
        workdir=workdir,
        prompt_source=prompt_source,
        prompt_pack_root=prompt_pack_root,
        worker=prepared_worker,
        worker_mode=worker_mode,
        result_contract=result_contract,
        handoff_dir=handoff_dir,
        launch_prompt=launch_prompt,
        contract_path=agent_run_contract,
        job_binding=job_binding,
        job_id=native_job.job_id if native_job else None,
        evaluation_path=evaluation_path,
        git_info=git_info,
    )
    status = prepared.initial_status()
    claim_agent_name(
        settings,
        agent_name=agent_name,
        agent_run_id=agent_run_id,
        interactive=(worker_mode == "external"),
    )
    initialize_execution(settings, agent_run_id, status)
    initialize_agent_context(
        state_dir,
        agent_run_id=agent_run_id,
        status=status,
    )
    runner = _write_runner(
        state_dir,
        workdir,
        command,
        python_executable=sys.executable,
        agent_run_id=agent_run_id,
        prompt_source=prompt_source,
        prompt_pack_root=prompt_pack_root,
        handoff_dir=handoff_dir,
        completion_template_path=completion_template_path,
        command_artifacts=command_artifacts,
        stream_format=executor_plan.stream_format,
        interactive=executor_interactive,
    )
    return update_projection(
        settings,
        agent_run_id,
        runner_path=str(runner),
        prepared_at=utc_now(),
        projection_source="prepare",
    )


def start(settings: Settings, agent_run_id: str) -> dict[str, Any]:
    """Start a prepared headless Agent Run under AW process ownership."""
    import uuid

    paths = AgentRunPaths(run_dir(settings, agent_run_id))
    status = synchronize_projection(status_path := paths.status, source="start")
    if authoritative_execution_status(status_path.parent) != "prepared":
        raise WorkflowError(
            f"agent run must be prepared before start: {agent_run_id} "
            f"(status={status.get('status')!r})"
        )
    if status.get("worker_mode") != "headless":
        raise WorkflowError("external Agent Runs must be launched by an external host")
    runner_path = status.get("runner_path")
    if not isinstance(runner_path, str) or not runner_path:
        raise WorkflowError("prepared Agent Run has no runner_path")
    workdir = Path(str(status["workdir"]))
    worker = spawn_detached(
        ProcessRequest(
            argv=(runner_path,),
            cwd=workdir,
            timeout_seconds=None,
            create_process_group=True,
        )
    )
    worker_id = f"worker-{uuid.uuid4().hex}"
    return transition_execution(
        settings,
        agent_run_id,
        "running",
        actor="agent-workflow",
        reason="headless worker started",
        projection_source="start",
        worker_id=worker_id,
        worker_pid=worker.pid,
        worker_process_group_id=worker.process_group_id,
        worker_alive=True,
        worker_started_at=utc_now(),
    )


def _pid_alive(pid: object) -> bool | None:
    if not isinstance(pid, int) or pid <= 0:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def observe(
    settings: Settings,
    agent_run_id: str,
) -> dict[str, Any]:
    """Refresh a terminal-neutral projection of Agent Run health."""
    paths = AgentRunPaths(run_dir(settings, agent_run_id))
    data = synchronize_projection(paths.status, source="observe")
    log_path = Path(str(data.get("log_path", paths.output_log)))
    state_dir = paths.root
    worker_mode = str(data.get("worker_mode", "headless"))
    worker_alive = _pid_alive(data.get("worker_pid")) if worker_mode == "headless" else None

    seconds_since_log_growth: float | None = None
    if log_path.exists():
        seconds_since_log_growth = max(0.0, time.time() - log_path.stat().st_mtime)
    heartbeat_path = paths.heartbeat
    seconds_since_heartbeat: float | None = None
    if heartbeat_path.is_file():
        seconds_since_heartbeat = max(0.0, time.time() - heartbeat_path.stat().st_mtime)
    executor_events_path = paths.executor_events
    seconds_since_executor_event_growth: float | None = None
    if executor_events_path.is_file():
        seconds_since_executor_event_growth = max(
            0.0, time.time() - executor_events_path.stat().st_mtime
        )

    progress_state = semantic_progress(state_dir)
    seconds_since_semantic_progress = progress_state["seconds_since_semantic_progress"]
    if seconds_since_semantic_progress is None:
        baseline = data.get("worker_started_at") or data.get("created_at")
        if isinstance(baseline, str) and baseline:
            try:
                seconds_since_semantic_progress = max(
                    0.0, time.time() - datetime.fromisoformat(baseline).timestamp()
                )
            except ValueError:
                pass

    latest_health = last_health_event(paths.health_samples) or {}
    latest_permission = last_health_event(paths.permission_events)
    permission_state = (
        str(latest_permission.get("state"))
        if isinstance(latest_permission, dict) and latest_permission.get("state")
        else None
    )
    process_result_path = paths.process_result
    process_result: dict[str, Any] = {}
    if process_result_path.is_file():
        try:
            value = json.loads(process_result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {}
        if isinstance(value, dict):
            process_result = value
    output_capture_exhausted = bool(
        process_result.get("stdout_truncated") or process_result.get("stderr_truncated")
    )

    durable = str(data.get("status", "unknown"))
    active = {"prepared", "running", "interruption_requested"}
    if durable not in active:
        observed = durable
    elif durable == "prepared":
        observed = "prepared"
    elif permission_state == "pending":
        observed = "blocked_permission"
    elif worker_mode == "headless" and worker_alive is False:
        observed = "orphaned"
    else:
        threshold = settings.stall_minutes * 60
        executor_alive = (
            latest_health.get("executor", {}).get("alive")
            if isinstance(latest_health.get("executor"), dict)
            else None
        )
        if executor_alive is False and worker_mode == "headless":
            observed = "orphaned"
        elif (
            durable == "running"
            and threshold > 0
            and seconds_since_semantic_progress is not None
            and seconds_since_semantic_progress >= threshold
        ):
            observed = "possibly_stalled"
        else:
            observed = "running"

    failure_category = (
        "orphaned"
        if observed == "orphaned"
        else "permission_wait"
        if observed == "blocked_permission"
        else "stalled"
        if observed == "possibly_stalled"
        else data.get("failure_category")
    )
    safe_actions = [f"agent-workflow agent-run status {agent_run_id} --json"]
    if observed in {"orphaned", "failed", "interrupted", "terminated"}:
        safe_actions.append(f"agent-workflow agent-run restart {agent_run_id}")
    elif observed == "possibly_stalled":
        safe_actions.append(f"agent-workflow agent-run interrupt {agent_run_id}")

    projection_fields = {
        "worker_alive": worker_alive,
        "observed_state": observed,
        "observed_failure_category": failure_category,
        "last_semantic_progress_at": progress_state["last_semantic_progress_at"],
        "last_semantic_progress_source": progress_state["last_semantic_progress_source"],
        "latest_health": latest_health,
        "permission_state": permission_state,
        "latest_permission_event": latest_permission,
        "output_capture_exhausted": output_capture_exhausted,
    }
    persisted = update_projection(
        settings,
        agent_run_id,
        **projection_fields,
        projection_source="observe",
        projection_freshness="live",
    )

    events_path = paths.lifecycle_events
    last_event = None
    if events_path.is_file():
        lines = [line for line in events_path.read_text(encoding="utf-8").splitlines() if line]
        if lines:
            try:
                last_event = json.loads(lines[-1])
            except json.JSONDecodeError:
                last_event = {"error": "invalid final lifecycle event"}

    return {
        **persisted,
        "durable_failure_category": data.get("failure_category"),
        "failure_category": failure_category,
        "seconds_since_log_growth": round(seconds_since_log_growth, 1) if seconds_since_log_growth is not None else None,
        "seconds_since_heartbeat": round(seconds_since_heartbeat, 1) if seconds_since_heartbeat is not None else None,
        "seconds_since_executor_event_growth": round(seconds_since_executor_event_growth, 1) if seconds_since_executor_event_growth is not None else None,
        "seconds_since_semantic_progress": round(float(seconds_since_semantic_progress), 1) if seconds_since_semantic_progress is not None else None,
        "signals": {
            "worker_alive": worker_alive,
            "log_exists": log_path.is_file(),
            "heartbeat_exists": heartbeat_path.is_file(),
            "executor_events_exist": executor_events_path.is_file(),
            "health_samples_exist": (paths.health_samples).is_file(),
            "permission_events_exist": (paths.permission_events).is_file(),
        },
        "last_event": last_event,
        "paths": {
            "status": str(paths.status),
            "log": str(log_path),
            "heartbeat": str(heartbeat_path),
            "executor_events": str(executor_events_path),
            "health_samples": str(paths.health_samples),
            "permission_events": str(paths.permission_events),
            "incident_events": str(paths.incident_events),
            "remediation_events": str(paths.remediation_events),
            "process_result": str(process_result_path),
            "events": str(events_path),
        },
        "safe_actions": safe_actions,
        "next_action": safe_actions[-1],
    }


PUBLIC_AGENT_RUN_FIELDS = (
    "schema",
    "agent_run_id",
    "ticket_id",
    "agent_name",
    "role",
    "role_digest",
    "tier",
    "pack_id",
    "retry_of_agent_run_id",
    "status",
    "disposition",
    "created_at",
    "updated_at",
    "started_at",
    "finished_at",
    "worker_mode",
    "worker_alive",
    "observed_state",
    "failure_category",
    "durable_failure_category",
    "observed_failure_category",
    "completion_validation_status",
    "steering_supported",
    "steering_reason",
    "job_id",
    "branch",
    "source_revision",
    "dirty_at_launch",
    "final_receipt_sha256",
    "seconds_since_log_growth",
    "seconds_since_heartbeat",
    "seconds_since_executor_event_growth",
    "seconds_since_semantic_progress",
    "permission_state",
    "output_capture_exhausted",
    "signals",
    "safe_actions",
    "next_action",
)


def public_agent_run_view(value: dict[str, Any]) -> dict[str, Any]:
    """Return the supported agent/orchestrator view of one Agent Run.

    Private execution identity and state-root paths intentionally stay out of
    this view. Operators can inspect provenance/config through explicit
    administrative surfaces; agents reason only about logical roles and
    lifecycle state.
    """
    return {key: value[key] for key in PUBLIC_AGENT_RUN_FIELDS if key in value}


def next_retry_id(settings: Settings, original: str) -> str:
    existing = {str(item.get("agent_run_id")) for item in list_statuses(settings)}
    index = 1
    while True:
        candidate = f"{original}-retry{index}"
        if candidate not in existing:
            return candidate
        index += 1


def restart(
    settings: Settings,
    agent_run_id: str,
    new_agent_run_id: str | None = None,
) -> dict[str, Any]:
    """Create a new Agent Run from the immutable contract of a prior run."""
    child_control = _child_lifecycle_control(agent_run_id)
    if child_control is not None:
        return child_control
    state_dir = run_dir(settings, agent_run_id)
    paths = AgentRunPaths(state_dir)
    contract = read_agent_run_contract(paths.contract)
    execution_status = authoritative_execution_status(state_dir)
    if execution_status not in TERMINAL_STATUSES:
        raise WorkflowError("an active Agent Run cannot be restarted; interrupt or terminate it first")

    command_data = read_contract(paths.command, "agent-workflow/command/v1")
    worker_plan = contract["worker_plan"]
    command = command_data.get("argv")
    if command != worker_plan.get("argv"):
        raise WorkflowError("cannot restart: saved command differs from Agent Run contract")
    if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
        raise WorkflowError(f"invalid saved command for Agent Run {agent_run_id}")
    encoded = json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() != worker_plan.get("command_sha256"):
        raise WorkflowError("cannot restart: command digest differs from Agent Run contract")

    new_id = new_agent_run_id or next_retry_id(settings, agent_run_id)
    agent_run = contract["agent_run"]
    pack = contract["pack"]
    worktree = contract["worktree"]
    prompt = contract["prompt"]
    prompt_source = Path(str(prompt["source"]))
    prompt_read = read_regular_file(prompt_source)
    if prompt_read.sha256 != prompt["sha256"]:
        raise WorkflowError("cannot restart: prompt source changed")
    no_go_authorized = bool(contract["runtime_policy"].get("no_go_authorized", False))

    job_path = None
    binding_path = paths.job_binding
    if binding_path.is_file():
        binding = read_contract(binding_path, "agent-workflow/job-binding/v1")
        source = Path(str(binding["job_source_path"]))
        expected = str(binding["job_source_sha256"])
        if not source.is_file() or sha256_file(source) != expected:
            raise WorkflowError("cannot restart: native job binding source is missing or changed")
        job_path = source

    prepared = prepare(
        settings,
        agent_run_id=new_id,
        workdir=Path(str(worktree["path"])),
        prompt_path=prompt_source,
        explicit_command=command,
        agent_name=agent_run.get("agent_name"),
        agent_class=agent_run.get("agent_class"),
        model=command_data.get("model"),
        reasoning_effort=contract["runtime_policy"].get("codex_reasoning_effort"),
        allow_no_go_model=no_go_authorized,
        ticket_id=contract.get("ticket"),
        pack_id=pack.get("id"),
        retry_of=agent_run_id,
        allow_dirty=True,
        saved_stream_format=str(command_data.get("stream_format", "text")),
        saved_executor=command_data.get("executor"),
        interactive=(worker_plan.get("mode") == "external"),
        prompt_source_override=prompt_source,
        prompt_pack_root_override=Path(str(pack["root"])) if pack.get("root") else None,
        evaluation_path=(
            Path(str(contract["evaluation_policy"]["path"]))
            if contract["evaluation_policy"].get("path")
            else None
        ),
        tier=agent_run.get("tier"),
        job_path=job_path,
        allow_active_agent_name=True,
        worker_mode=str(worker_plan.get("mode", "headless")),
    )
    if prepared.get("worker_mode") == "headless":
        return start(settings, new_id)
    return prepared
