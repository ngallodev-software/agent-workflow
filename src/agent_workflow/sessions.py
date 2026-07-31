from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import platform
import shlex
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from . import tmux
from .agent_context import acknowledge_reuse, idle_interactive_sessions
from .agent_context import initialize as initialize_agent_context
from .assets import asset_path
from .config import Settings
from .config import enforce_trust
from .compatibility import probe_executor
from .command_catalog import role_for_agent_class, write_launch_command_artifacts
from .contracts import read_contract, read_launch_contract, schema_descriptor
from .errors import InteractiveCapacityError, WorkflowError
from .events import reconstruct_lifecycle
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
from .messages import (
    append_message,
    bridge_available,
    bridge_required,
    replay_messages,
    wait_for_messages,
    write_control_intent,
)
from .preflight import preflight_error, preflight_run_record, resolve_prerequisites
from .manifests import task_result_contract
from .process import redact_argv, require_command, run, secret_values_from_argv
from .receipts import completion_template, initial_completion, initial_provenance, update_provenance
from .steering import current_delivery, queue_request, record_acknowledgement
from .state import (
    TERMINAL_STATUSES,
    list_statuses,
    read_status,
    run_dir,
    update_status,
    write_status,
)
from .util import (
    atomic_write_bytes,
    atomic_write_json,
    expand_path,
    sha256_file,
    utc_now,
    validate_id,
)
from .path import absolute_path, read_regular_file, require_directory


def _ignore_delegations(workdir: Path) -> None:
    _add_git_exclude(workdir, ".delegations/")


def _add_git_exclude(workdir: Path, entry: str) -> None:
    try:
        result = run(
            ["git", "-C", str(workdir), "rev-parse", "--git-path", "info/exclude"]
        )
    except WorkflowError:
        return
    exclude = Path(result.stdout.strip())
    if not exclude.is_absolute():
        exclude = workdir / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if entry not in {line.strip() for line in existing.splitlines()}:
        with exclude.open("a", encoding="utf-8") as stream:
            if existing and not existing.endswith("\n"):
                stream.write("\n")
            stream.write(entry + "\n")


def _create_handoff_dir(workdir: Path, session_id: str) -> Path:
    """Create the executor-writable completion boundary in the worktree."""
    _add_git_exclude(workdir, ".agent-workflow-handoff/")
    handoff = workdir / ".agent-workflow-handoff" / session_id
    if handoff.exists() or handoff.is_symlink():
        raise WorkflowError(f"completion handoff already exists: {handoff}")
    handoff.mkdir(parents=True, mode=0o700)
    return handoff.resolve()


def _link_worktree_state(
    workdir: Path,
    session_id: str,
    state_dir: Path,
) -> None:
    _ignore_delegations(workdir)
    delegations = workdir / ".delegations"
    delegations.mkdir(parents=True, exist_ok=True)
    link = delegations / session_id
    if link.exists() or link.is_symlink():
        try:
            if link.resolve() == state_dir.resolve():
                return
        except OSError:
            pass
        raise WorkflowError(f"delegation link already exists: {link}")
    link.symlink_to(state_dir, target_is_directory=True)


def _write_runner(
    state_dir: Path,
    workdir: Path,
    command: list[str],
    *,
    python_executable: str,
    session_id: str = "unknown-session",
    prompt_source: Path | None = None,
    prompt_pack_root: Path | None = None,
    handoff_dir: Path | None = None,
    completion_template_path: Path | None = None,
    command_artifacts: dict[str, Any] | None = None,
    stream_format: str = "text",
    interactive: bool = False,
    close_tmux_on_exit: bool = False,
) -> Path:
    prompt = state_dir / "prompt.md"
    launch_prompt = state_dir / "launch-prompt.md"
    if not launch_prompt.exists() and prompt.exists():
        shutil.copy2(prompt, launch_prompt)
    prompt_source = prompt_source or prompt
    runner = state_dir / "run.sh"
    source_root = Path(__file__).resolve().parents[1]
    command_blob = base64.b64encode(
        json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    runner_invocation = (
        f"{shlex.quote(python_executable)} -m agent_workflow.runner "
        f"--run-dir {shlex.quote(str(state_dir))} "
        f"--command-b64 {shlex.quote(command_blob)} "
        f"{'--interactive ' if interactive else ''}"
    )
    if interactive and not close_tmux_on_exit:
        runner_command = (
            "if [[ -t 0 ]]; then\n"
            f"    exec {runner_invocation}\n"
            "else\n"
            f"    exec {runner_invocation.replace('--interactive ', '', 1)}\n"
            "fi"
        )
    elif close_tmux_on_exit:
        fallback_invocation = runner_invocation.replace("--interactive ", "", 1)
        runner_command = (
            "if [[ -t 0 ]]; then\n"
            "    set +e\n"
            f"    {runner_invocation}\n"
            "    runner_status=$?\n"
            "    set -e\n"
            "    if [[ -n \"${AGENT_WORKFLOW_TMUX_SESSION:-}\" ]]; then\n"
            "        tmux kill-session -t \"$AGENT_WORKFLOW_TMUX_SESSION\" >/dev/null 2>&1 || true\n"
            "    fi\n"
            "    exit \"$runner_status\"\n"
            "else\n"
            f"    exec {fallback_invocation}\n"
            "fi\n"
        )
    else:
        runner_command = f"exec {runner_invocation}"
    runner_text = (
        "#!/usr/bin/env bash\n"
        "set -Eeuo pipefail\n"
        f"readonly AGENT_WORKFLOW_SESSION_ID={shlex.quote(session_id)}\n"
        f"readonly AGENT_WORKFLOW_PROMPT_SOURCE={shlex.quote(str(prompt_source))}\n"
        f"readonly AGENT_WORKFLOW_HANDOFF_DIR={shlex.quote(str(handoff_dir or ''))}\n"
        f"readonly AGENT_WORKFLOW_CONTROL_BRIDGE={shlex.quote(str((handoff_dir / 'control-intents') if handoff_dir else ''))}\n"
        f"readonly AGENT_WORKFLOW_COMPLETION_TEMPLATE={shlex.quote(str(completion_template_path or ''))}\n"
        f"readonly AGENT_WORKFLOW_PROMPT_PACK_ROOT={shlex.quote(str(prompt_pack_root or ''))}\n"
        f"readonly AGENT_WORKFLOW_COMMAND_CATALOG={shlex.quote(str(state_dir / str((command_artifacts or {}).get('catalog_path', 'command-catalog.json'))))}\n"
        f"readonly AGENT_WORKFLOW_COMMAND_CARD={shlex.quote(str(state_dir / str((command_artifacts or {}).get('card_path', 'command-card.md'))))}\n"
        f"readonly AGENT_WORKFLOW_CLI={shlex.quote(str(((command_artifacts or {}).get('cli_invocation') or ['agent-workflow'])[0]))}\n"
    )
    if close_tmux_on_exit:
        runner_text += (
            f"readonly AGENT_WORKFLOW_TMUX_SESSION={shlex.quote(session_id)}\n"
        )
    runner_text += (
        "export AGENT_WORKFLOW_SESSION_ID AGENT_WORKFLOW_PROMPT_SOURCE "
        "AGENT_WORKFLOW_HANDOFF_DIR AGENT_WORKFLOW_PROMPT_PACK_ROOT "
        "AGENT_WORKFLOW_CONTROL_BRIDGE "
        "AGENT_WORKFLOW_COMPLETION_TEMPLATE AGENT_WORKFLOW_COMMAND_CATALOG "
        "AGENT_WORKFLOW_COMMAND_CARD AGENT_WORKFLOW_CLI"
        + (" AGENT_WORKFLOW_TMUX_SESSION\n" if close_tmux_on_exit else "\n")
        + f"export PYTHONPATH={shlex.quote(str(source_root))}${{PYTHONPATH:+:$PYTHONPATH}}\n"
        + runner_command
        + "\n"
    )
    runner.write_text(runner_text, encoding="utf-8")
    runner.chmod(0o755)
    syntax = run(
        ["bash", "-n", str(runner)],
        check=False,
        timeout_seconds=10,
        max_stdout_bytes=64 * 1024,
        max_stderr_bytes=64 * 1024,
    )
    if syntax.returncode:
        raise WorkflowError(
            f"generated runner failed syntax check: {syntax.stderr.strip()}"
        )
    return runner


def _discover_prompt_pack_root(prompt_source: Path) -> Path | None:
    for candidate in prompt_source.parents:
        try:
            read_regular_file(candidate / "pack.yaml")
        except WorkflowError:
            continue
        else:
            return candidate
    return None


def _pack_id(pack_root: Path) -> str:
    """Read the deliberately small, stable identity field from pack.yaml."""
    pack_file = pack_root / "pack.yaml"
    try:
        for line in read_regular_file(pack_file).data.decode("utf-8").splitlines():
            key, separator, value = line.partition(":")
            if key.strip() == "pack_id" and separator and value.strip():
                return value.strip().strip("\"'")
    except OSError as exc:
        raise WorkflowError(f"cannot read selected pack: {pack_file}: {exc}") from exc
    raise WorkflowError(f"selected pack has no pack_id: {pack_file}")


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


def _write_job_binding(state_dir: Path, job: ValidatedNativeJob, *, session_id: str, workdir: Path) -> dict[str, Any]:
    """Snapshot the validated source bytes and write the immutable binding receipt."""
    stored = state_dir / "jobs" / "native-job.json"
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
        "session_id": session_id,
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
    receipt_path = state_dir / "job-binding.json"
    atomic_write_json(receipt_path, receipt, mode=0o444)
    return receipt


def _write_launch_prompt(
    state_dir: Path,
    *,
    session_id: str,
    agent_name: str | None,
    agent_class: str | None,
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
) -> Path:
    context = [
        "# Agent-workflow launch context",
        "The complete ticket is included below. Do not reread prompt_source unless the ticket explicitly requests it.",
        "Use these durable paths only when the ticket references pack files or its completion report.",
        f"- session_id: `{session_id}`",
        f"- prompt_source: `{prompt_source}`",
        f"- command_catalog_role: `{command_artifacts['role']}`",
        "- The exact installed CLI contract is available at `AGENT_WORKFLOW_COMMAND_CATALOG`.",
        "- A role-scoped command card is available at `AGENT_WORKFLOW_COMMAND_CARD`.",
        "- Invoke commands through `AGENT_WORKFLOW_CLI` using the catalog signatures directly.",
        "- Do not run `--help` for commands represented in the catalog. Use help only after a catalog/version mismatch, an argument error, or when a required command is absent.",
    ]
    if prompt_pack_root is not None:
        context.append(f"- prompt_pack_root: `{prompt_pack_root}`")
    if result_contract is not None:
        context.extend(
            [
                f"- task_result_schema: `{result_contract['schema']}`",
                "- Write task result JSON atomically to `AGENT_WORKFLOW_HANDOFF_DIR/result.json`.",
                "- The result must satisfy the declared JSON Schema; downstream work may depend on its structured outputs.",
            ]
        )
    if interactive:
        context.extend(
            [
                "- This interactive agent remains open after its assignment.",
                '- Before becoming reusable, emit structured completion with `"$AGENT_WORKFLOW_CLI" agent task-complete "$AGENT_WORKFLOW_SESSION_ID" --actor <agent-name> --summary <summary>`.',
                "- For a reused assignment, acknowledge its correlated steer message before starting work.",
                "- Write and validate the completion handoff before task-complete; task-complete is interactive-only.",
            ]
        )
    elif detached_interactive:
        context.extend(
            [
                "- This task is non-interactive from the orchestrator's perspective and runs in a private tmux session.",
                "- Do not wait for user input or expect a user to resume this run.",
                "- On completion, notify the calling agent through the durable completion handoff and a concise progress update.",
                "- Exit cleanly when finished; the private tmux session will be closed automatically when possible.",
                "- Do not invoke `agent task-complete`; that command is interactive-only.",
            ]
        )
    else:
        context.append(
            "- This is a structured non-interactive run. Do not invoke `agent task-complete`; the runner collects completion on process exit."
        )
    context.extend(
        [
            f"- completion_handoff_dir: `{handoff_dir}`",
            f"- completion_template: `{handoff_dir / 'completion-template.json'}` (read-only starting point; copy it to `completion.json` and edit the evidence)",
            "- Write completion JSON only to `AGENT_WORKFLOW_HANDOFF_DIR/completion.json` using schema `agent-workflow/completion/v1`.",
            "- Write it atomically; optional `completion.md` and `evidence.json` sidecars may use the same handoff directory.",
            "- `result: completed` requires an empty `unresolved` list. Host-owned merge, review, acceptance, release, and pane closure are normal next steps, not unresolved defects.",
            "- Canonical runtime completion paths are collector-owned; do not write to them.",
            "- Matching environment variables use the `AGENT_WORKFLOW_` prefix.",
            "- At meaningful checkpoints you may emit a concise durable progress update with `\"$AGENT_WORKFLOW_CLI\" progress "
            + shlex.quote(session_id)
            + " 'message' --actor child`. Do not expose secrets in updates.",
            "- A parent steer request is only applied after you explicitly acknowledge its message ID with `\"$AGENT_WORKFLOW_CLI\" ack`.",
            "",
            "---",
            "",
        ]
    )
    launch_prompt = state_dir / "launch-prompt.md"
    launch_prompt.write_text(
        "\n".join(context)
        + (state_dir / "prompt.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return launch_prompt


def _write_launch_contract(
    state_dir: Path,
    *,
    session_id: str,
    agent_name: str | None,
    agent_class: str | None,
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
    redacted_command: list[str],
    executor: str | None,
    model: str | None,
    reasoning_effort: str | None,
    stream_format: str,
    interactive: bool,
    executor_interactive: bool,
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
        "schema": "agent-workflow/launch-contract/v2",
        "version": 2,
        "session": {
            "id": session_id,
            "agent_name": agent_name,
            "agent_class": agent_class,
            "tier": tier,
            "retry_of": retry_of,
            "created_at": created_at,
        },
        "ticket": ticket_id,
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
        "command_plan": {
            "argv": list(redacted_command),
            "command_sha256": hashlib.sha256(
                json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "stream_format": stream_format,
            "interactive": interactive,
            "executor_interactive": executor_interactive,
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
            "launch": schema_descriptor("agent-workflow/launch-contract/v2"),
            "command_catalog": schema_descriptor("agent-workflow/command-catalog/v1"),
            "completion": schema_descriptor("agent-workflow/completion/v1"),
            "provenance": schema_descriptor("agent-workflow/run-provenance/v1"),
            "status": schema_descriptor("agent-workflow/session-status/v2"),
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
    path = state_dir / "launch-contract.json"
    atomic_write_json(path, contract, mode=0o444)
    return path


def _status_agent_active(item: dict[str, Any]) -> bool:
    if str(item.get("status")) in TERMINAL_STATUSES:
        return False
    target = item.get("tmux_pane_id") or item.get("tmux_target")
    if not isinstance(target, str) or not target:
        return True
    try:
        pane = tmux.resolve_status_pane(item)
    except WorkflowError:
        return True
    return pane is not None and not pane.dead


def _resolve_agent_identity(
    settings: Settings,
    *,
    requested_name: str | None,
    requested_class: str | None,
    executor: str | None,
    model: str | None,
    allow_no_go_model: bool,
    explicit_command: list[str] | None,
    interactive: bool | None,
    allow_active_name: bool = False,
) -> tuple[str, str, str | None, str | None, bool, bool]:
    interactive_explicit = interactive is not None
    active_names = {
        str(item["agent_name"])
        for item in list_statuses(settings)
        if item.get("agent_name") and _status_agent_active(item)
    }
    if requested_name is not None:
        validate_id(requested_name, "agent name")
        generated_name = requested_name.startswith(f"{settings.generated_agent_prefix}-")
        if requested_name not in settings.preferred_agent_names and not generated_name:
            raise WorkflowError(
                f"agent name {requested_name!r} is not listed in [agents].preferred_names"
            )
        if requested_name in active_names and not allow_active_name:
            raise WorkflowError(f"agent name is already active: {requested_name}")
        agent_name = requested_name
    else:
        agent_name = next(
            (name for name in settings.preferred_agent_names if name not in active_names),
            "",
        )
        if not agent_name:
            index = 1
            while f"{settings.generated_agent_prefix}-{index:02d}" in active_names:
                index += 1
            agent_name = f"{settings.generated_agent_prefix}-{index:02d}"
    profile = settings.agent_profiles.get(agent_name)
    agent_class = requested_class or settings.default_agent_class
    if profile is not None:
        if explicit_command is not None and not allow_active_name:
            raise WorkflowError(f"agent profile {agent_name!r} cannot use an explicit command")
        if profile.agent_class is not None:
            if requested_class is not None and requested_class != profile.agent_class:
                raise WorkflowError(f"agent {agent_name!r} requires class {profile.agent_class!r}")
            agent_class = profile.agent_class
        if executor is not None and executor != profile.executor:
            raise WorkflowError(f"agent {agent_name!r} requires executor {profile.executor!r}")
        if model is not None and model != profile.model:
            raise WorkflowError(f"agent {agent_name!r} requires model {profile.model!r}")
        executor = profile.executor or executor
        model = profile.model or model
        allow_no_go_model = profile.allow_no_go_model
        if interactive is None and profile.interactive is not None:
            interactive = profile.interactive
    if agent_class not in settings.agent_classes:
        raise WorkflowError(f"agent class is not configured: {agent_class}")
    class_policy = settings.agent_classes[agent_class]
    if executor is None and explicit_command is None:
        executor = class_policy.default_executor or settings.default_agent_executor
    if model is None and executor is not None:
        if executor == class_policy.default_executor:
            model = class_policy.default_model
        else:
            allowed_for_executor = class_policy.allowed_models.get(executor, ())
            model = allowed_for_executor[0] if allowed_for_executor else None
    if executor is not None and model is not None:
        allowed_models = class_policy.allowed_models.get(executor, ())
        if model not in allowed_models:
            raise WorkflowError(
                f"agent class {agent_class!r} does not allow {executor}/{model}"
            )
    if interactive is None:
        interactive = class_policy.interactive
    if executor == "claude" and not interactive_explicit:
        interactive = True
    return agent_name, agent_class, executor, model, allow_no_go_model, interactive


def _claim_agent_name(
    settings: Settings,
    *,
    agent_name: str,
    session_id: str,
    interactive: bool,
) -> None:
    """Atomically reserve one name across interactive and detached runs."""
    lease_root = settings.state_root / "agent-name-leases"
    lease_root.mkdir(parents=True, exist_ok=True)
    lock_path = lease_root / ".lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        active_names = {
            str(item["agent_name"])
            for item in list_statuses(settings)
            if item.get("agent_name")
            and item.get("session_id") != session_id
            and _status_agent_active(item)
        }
        lease_path = lease_root / f"{agent_name}.json"
        if lease_path.is_file():
            try:
                lease = json.loads(lease_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                lease = {}
            leased_session = lease.get("session_id")
            if leased_session and leased_session != session_id:
                try:
                    leased_status = read_status(settings, str(leased_session))
                except WorkflowError:
                    leased_status = None
                if leased_status is not None:
                    if _status_agent_active(leased_status):
                        active_names.add(agent_name)
                elif lease.get("pid") == os.getpid():
                    active_names.add(agent_name)
        if agent_name in active_names:
            raise WorkflowError(f"agent name is already active: {agent_name}")
        atomic_write_json(
            lease_path,
            {
                "schema": "agent-workflow/agent-name-lease/v1",
                "agent_name": agent_name,
                "session_id": session_id,
                "interactive": interactive,
                "pid": os.getpid(),
                "claimed_at": utc_now(),
            },
        )
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def launch(
    settings: Settings,
    *,
    session_id: str,
    workdir: Path,
    prompt_path: Path,
    executor: str | None = None,
    agent_name: str | None = None,
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
) -> dict[str, Any]:
    validate_id(session_id, "session ID")
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
        state_dir = run_dir(settings, session_id)
        if state_dir.exists() and any(state_dir.iterdir()):
            raise preflight_error(preflight)
        state_dir.mkdir(parents=True, exist_ok=True)
        created_at = utc_now()
        atomic_write_json(state_dir / "preflight.json", preflight, mode=0o444)
        (state_dir / "output.log").touch()
        write_status(
            settings,
            session_id,
            preflight_run_record(
                session_id=session_id,
                ticket_id=ticket_id,
                pack_id=pack_id,
                workdir=workdir,
                prompt_path=prompt_source,
                log_path=state_dir / "output.log",
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
    if settings.terminal_backend != "tmux":
        raise WorkflowError(
            f"unsupported terminal backend {settings.terminal_backend!r}; v0.1 supports tmux"
        )
    # Claude's native command is interactive by default.  The explicit
    # --structured/--no-interactive paths remain opt-outs for automation.
    if structured and interactive is None:
        interactive = False
    agent_name, agent_class, executor, model, allow_no_go_model, interactive = _resolve_agent_identity(
        settings,
        requested_name=agent_name,
        requested_class=agent_class,
        executor=executor,
        model=model,
        allow_no_go_model=allow_no_go_model,
        explicit_command=explicit_command,
        interactive=interactive,
        allow_active_name=allow_active_agent_name,
    )
    # `interactive` describes user-visible/reusable assignment semantics.
    # Structured and non-interactive runs always use the deterministic executor
    # command. Only interactive implementation agents retain a steerable
    # interactive provider process.
    executor_interactive = not structured and bool(interactive)
    interactive_parent_target = tmux.current_window_target() if interactive else None
    parent_target = (
        interactive_parent_target
        if interactive
        else tmux.current_window_target()
        if settings.non_interactive_tmux == "shared_window"
        else None
    )
    if parent_target is not None:
        pane_count = tmux.interactive_pane_count(parent_target)
        if pane_count >= settings.max_interactive_agent_panes:
            raise InteractiveCapacityError(
                count=pane_count,
                maximum=settings.max_interactive_agent_panes,
                idle_sessions=idle_interactive_sessions(
                    settings, window_target=parent_target
                ),
            )
    if tmux.session_exists(session_id):
        raise WorkflowError(f"tmux session already exists: {session_id}")

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

    state_dir = run_dir(settings, session_id)
    if state_dir.exists():
        if any(state_dir.iterdir()):
            raise WorkflowError(
                f"run state already exists: {state_dir}; use a new session ID"
            )
    else:
        state_dir.mkdir(parents=True)

    job_binding = (
        _write_job_binding(state_dir, native_job, session_id=session_id, workdir=workdir)
        if native_job is not None
        else None
    )
    handoff_dir = _create_handoff_dir(workdir, session_id)
    (handoff_dir / "control-intents").mkdir(mode=0o700)
    (handoff_dir / "steering-inbox").mkdir(mode=0o700)
    executor_plan = prepare_executor(
        settings, executor, explicit_command, structured=structured,
        interactive=executor_interactive,
        model=model,
        reasoning_effort=reasoning_effort,
        allow_no_go_model=allow_no_go_model,
    )
    if saved_stream_format is not None:
        executor_plan = ExecutorPlan(
            saved_executor,
            executor_plan.argv,
            saved_stream_format,
            executor_plan.model,
            executor_plan.no_go_authorized,
            executor_plan.reasoning_effort,
        )
    command = list(executor_plan.argv)
    # Persist the resolved executable path in the runner command.  Dedicated
    # tmux sessions may inherit an older server PATH than the launching shell;
    # resolving here keeps the sealed run tied to the exact executable that was
    # preflighted and prevents a false not-found/orphan result.
    command[0] = require_command(command[0])
    if executor_plan.name == "codex" and "--add-dir" not in command:
        # The durable handoff is executor-written but collector-owned.  Make
        # this exact run-local directory an explicit Codex writable root so a
        # child never needs a broad sandbox escalation just to publish its
        # completion/control sidecars.
        command.extend(["--add-dir", str(handoff_dir)])
    executor_plan = ExecutorPlan(
        executor_plan.name,
        tuple(command),
        executor_plan.stream_format,
        executor_plan.model,
        executor_plan.no_go_authorized,
        executor_plan.reasoning_effort,
    )
    compatibility = probe_executor(
        executor_plan.name,
        command,
        digest=settings.security.executable_digest,
    )
    if (
        executor_plan.name is not None
        and settings.security.mode in {"governed", "release"}
        and compatibility.get("decision") != "supported"
    ):
        raise WorkflowError(
            "executor compatibility rejected: "
            f"{compatibility.get('explanation_code', 'COMPAT-UNKNOWN')}; "
            "governed launches do not silently downgrade to unclassified execution"
        )

    secret_values = secret_values_from_argv(command)
    redacted_command = redact_argv(command, secret_values=secret_values)
    executor_policy = settings.executor_policies.get(executor_plan.name)
    environment_allowlist = list(executor_policy.environment_allowlist) if executor_policy else []
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

    prompt_copy = state_dir / "prompt.md"
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
    (state_dir / "output.log").touch()
    atomic_write_json(
        state_dir / "command.json",
        {
            "schema": "agent-workflow/command/v1",
            "argv": redacted_command,
            "shell": shlex.join(redacted_command),
            "executor": executor_plan.name,
            "classification": "named" if executor_plan.name else "unclassified",
            "stream_format": executor_plan.stream_format,
            "interactive": interactive,
            "executor_interactive": executor_interactive,
            "model": executor_plan.model,
            "no_go_authorized": executor_plan.no_go_authorized,
            "agent_name": agent_name,
            "agent_class": agent_class,
            "environment_allowlist": environment_allowlist,
        },
        mode=0o444,
    )
    (state_dir / "completion.md").write_bytes(
        asset_path("prompt-pack-root/templates/TICKET_COMPLETION.md").read_bytes()
    )
    result_contract = (
        task_result_contract(prompt_pack_root, ticket_id)
        if prompt_pack_root is not None
        else None
    )
    created_at = utc_now()
    command_artifacts = write_launch_command_artifacts(
        state_dir, role=role_for_agent_class(agent_class)
    )
    launch_prompt = _write_launch_prompt(
        state_dir,
        session_id=session_id,
        agent_name=agent_name,
        agent_class=agent_class,
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
    )

    git_info: dict[str, Any]
    baseline_components: dict[str, Any]
    try:
        snap = preflight_snapshot or snapshot(workdir)
        git_info = {
            "repository_root": str(snap.root),
            "source_revision": snap.head,
            "branch": snap.branch,
            "dirty_at_launch": snap.dirty,
        }
        baseline_components = {
            "primary": {
                "path": str(snap.root),
                "head": snap.head,
                "branch": snap.branch,
                "dirty": snap.dirty,
            }
        }
    except WorkflowError:
        git_info = {
            "repository_root": None,
            "source_revision": None,
            "branch": None,
            "dirty_at_launch": None,
        }
        baseline_components = {
            "primary": {
                "path": str(workdir),
                "head": "",
                "branch": "",
                "dirty": False,
            }
        }
    baseline_path = state_dir / "source-baseline.json"
    atomic_write_json(
        baseline_path,
        {
            "schema": "agent-workflow/source-baseline/v1",
            "generated_at": utc_now(),
            "components": baseline_components,
        },
    )

    completion_path = state_dir / "completion.json"
    completion_template_path = handoff_dir / "completion-template.json"
    atomic_write_json(
        completion_template_path,
        completion_template(
            session_id=session_id,
            ticket_id=ticket_id,
            pack_id=pack_id,
            base_revision=git_info["source_revision"],
        ),
        mode=0o444,
    )
    atomic_write_json(
        completion_path,
        initial_completion(
            session_id=session_id,
            ticket_id=ticket_id,
            pack_id=pack_id,
            base_revision=git_info["source_revision"],
        ),
    )
    events_path = state_dir / "executor-events.jsonl"
    stderr_path = state_dir / "executor-stderr.log"
    events_path.touch()
    stderr_path.touch()
    config_sha256 = (
        sha256_file(settings.config_path)
        if settings.config_path and settings.config_path.is_file()
        else None
    )
    pack_manifest = prompt_pack_root / "MANIFEST.sha256" if prompt_pack_root else None
    provenance_path = state_dir / "run-provenance.json"
    atomic_write_json(
        provenance_path,
        initial_provenance(
            session_id=session_id,
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
            retry_of_run_id=retry_of,
            job_binding=(
                {
                    "path": str(state_dir / "job-binding.json"),
                    "sha256": sha256_file(state_dir / "job-binding.json"),
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
        workflow_inputs_path = state_dir / "workflow-inputs.json"
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
        # A bound native job is an execution policy, not advisory metadata.  Its
        # validated command vectors and allowed paths therefore override any
        # evaluation-plan collector settings for this run.
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
                # These runner-owned worktree directories are established before
                # baseline collection and receive completion/state writes after it.
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
                sha256_file(state_dir / "job-binding.json")
                if native_job is not None
                else None
            ),
        }
        if evaluation is not None:
            update_provenance(
                state_dir,
                budgets=evaluation_data.get("budgets", {}),
                evaluation_sha256=evaluation.sha256,
            )
        atomic_write_json(state_dir / "evaluation-runtime.json", runtime)
        runtime_policy = {
            "timeout_seconds": runtime.get("timeout_seconds"),
            "budgets": evaluation_data.get("budgets", {}),
            "environment_allowlist": environment_allowlist,
            "steering": {
                "adapter": (executor_policy.steering_adapter if executor_policy else "unsupported"),
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
        # Native jobs require receipts even for an empty declared command list:
        # the empty set is itself evidence that the binding was enforced.
        if commands or native_job is not None:
            collect_commands(
                workdir,
                specs_from_data(commands),
                phase="baseline",
                receipt_dir=state_dir / "collections",
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
            receipt_dir=state_dir / "scope",
        )

    launch_contract = _write_launch_contract(
        state_dir,
        session_id=session_id,
        agent_name=agent_name,
        agent_class=agent_class,
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
        redacted_command=redacted_command,
        executor=executor_plan.name,
        model=executor_plan.model,
        reasoning_effort=executor_plan.reasoning_effort,
        stream_format=executor_plan.stream_format,
        interactive=bool(interactive),
        executor_interactive=executor_interactive,
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

    now = created_at
    status: dict[str, Any] = {
        "schema": "agent-workflow/session-status/v2",
        "session_id": session_id,
        "ticket_id": ticket_id,
        "agent_name": agent_name,
        "agent_class": agent_class,
        "tier": tier,
        "pack_id": pack_id,
        "retry_of": retry_of,
        "status": "prepared",
        "disposition": None,
        "created_at": now,
        "updated_at": now,
        "workdir": str(workdir),
        "prompt_path": str(prompt_copy),
        "prompt_source": str(prompt_source),
        "executor": executor_plan.name,
        "model": executor_plan.model,
        "interactive": interactive,
        "executor_interactive": executor_interactive,
        "agent_context_path": str(state_dir / "agent-context.json"),
        "prompt_sha256": sha256_file(prompt_copy),
        "prompt_pack_root": str(prompt_pack_root) if prompt_pack_root else None,
        "result_contract": result_contract,
        "launch_prompt_path": str(launch_prompt),
        "launch_prompt_sha256": sha256_file(launch_prompt),
        "log_path": str(state_dir / "output.log"),
        "command_path": str(state_dir / "command.json"),
        "completion_path": str(state_dir / "completion.md"),
        "completion_json_path": str(completion_path),
        "handoff_dir": str(handoff_dir),
        "completion_collection_path": str(state_dir / "collections" / "completion.json"),
        "completion_validation_status": None,
        "provenance_path": str(provenance_path),
        "events_path": str(events_path),
        "stderr_path": str(stderr_path),
        "final_receipt_path": None,
        "evaluation_path": (
            str(expand_path(evaluation_path)) if evaluation_path else None
        ),
        "source_baseline_path": str(baseline_path),
        "launch_contract_path": str(launch_contract),
        "job_binding_path": str(state_dir / "job-binding.json") if job_binding else None,
        "job_binding_sha256": sha256_file(state_dir / "job-binding.json") if job_binding else None,
        "job_id": native_job.job_id if native_job else None,
        "tmux_session": session_id,
        "tmux_target": session_id,
        "tmux_pane_id": None,
        "tmux_window_target": None,
        "tmux_mode": "dedicated_session",
        **git_info,
    }
    _claim_agent_name(
        settings,
        agent_name=agent_name,
        session_id=session_id,
        interactive=interactive,
    )
    write_status(settings, session_id, status)
    agent_context = initialize_agent_context(
        state_dir,
        session_id=session_id,
        status=status,
        command=json.loads((state_dir / "command.json").read_text(encoding="utf-8")),
    )
    _link_worktree_state(workdir, session_id, state_dir)
    runner = _write_runner(
        state_dir,
        workdir,
        command,
        python_executable=sys.executable,
        session_id=session_id,
        prompt_source=prompt_source,
        prompt_pack_root=prompt_pack_root,
        handoff_dir=handoff_dir,
        completion_template_path=completion_template_path,
        command_artifacts=command_artifacts,
        stream_format=executor_plan.stream_format,
        interactive=executor_interactive,
        close_tmux_on_exit=(not interactive and executor_interactive and parent_target is None),
    )
    update_status(
        settings,
        session_id,
        status="launched",
        launched_at=utc_now(),
        runner_path=str(runner),
    )
    try:
        if parent_target is not None:
            tmux.configure_server(mouse=settings.mouse)
            tmux_target = tmux.split_window(
                parent_target,
                str(workdir),
                str(runner),
                orchestrator_side=settings.orchestrator_side,
                pane_name=agent_name,
                max_interactive_agent_panes=settings.max_interactive_agent_panes,
                max_interactive_agent_width=settings.max_interactive_agent_width,
                max_interactive_agent_vertical=settings.max_interactive_agent_vertical,
            )
            tmux.set_pane_binding(
                tmux_target,
                run_id=session_id,
                assignment_id=(agent_context.get("current_assignment") or {}).get(
                    "assignment_id"
                ),
            )
            tmux_session = parent_target.split(":", 1)[0]
            tmux_window_target = parent_target
            tmux_mode = "shared_window"
        else:
            tmux.configure_server(mouse=settings.mouse)
            tmux.create_session(session_id, str(workdir), str(runner), agent_name)
            tmux_target = session_id
            tmux_session = session_id
            tmux_window_target = None
            tmux_mode = "dedicated_session"
    except Exception:
        update_status(
            settings,
            session_id,
            status="failed",
            finished_at=utc_now(),
            launch_error=True,
        )
        raise
    pane = tmux.pane_info(tmux_target)
    if pane is not None and pane.dead:
        update_status(
            settings,
            session_id,
            status="failed",
            finished_at=utc_now(),
            failure_category="executor_exited_during_launch",
        )
        raise WorkflowError(f"agent pane exited during launch: {tmux_target}")
    return update_status(
        settings,
        session_id,
        tmux_session=tmux_session,
        tmux_target=tmux_target,
        tmux_mode=tmux_mode,
        tmux_pane_id=pane.pane_id if pane else tmux_target if tmux_target.startswith("%") else None,
        tmux_window_target=tmux_window_target,
        pane_pid=pane.pid if pane else None,
        pane_command=pane.command if pane else None,
    )


def observe(
    settings: Settings,
    session_id: str,
    capture_lines: int = 0,
) -> dict[str, Any]:
    data = read_status(settings, session_id)
    terminal_error = None
    host_session = str(data.get("tmux_session", session_id))
    try:
        alive: bool | None = tmux.session_exists(host_session)
        pane = tmux.resolve_status_pane(data) if alive else None
        if data.get("tmux_mode") == "shared_window":
            alive = pane is not None and not pane.dead
        elif pane is not None and pane.dead:
            alive = False
    except WorkflowError as exc:
        alive = None
        pane = None
        terminal_error = str(exc)

    log_path = Path(str(data.get("log_path", "")))
    state_dir = log_path.parent
    seconds_since_log_growth: float | None = None
    if log_path.exists():
        seconds_since_log_growth = max(0.0, time.time() - log_path.stat().st_mtime)
    heartbeat_path = state_dir / "heartbeat.json"
    seconds_since_heartbeat: float | None = None
    if heartbeat_path.is_file():
        seconds_since_heartbeat = max(
            0.0, time.time() - heartbeat_path.stat().st_mtime
        )
    executor_events_path = state_dir / "executor-events.jsonl"
    seconds_since_executor_event_growth: float | None = None
    if executor_events_path.is_file():
        seconds_since_executor_event_growth = max(
            0.0, time.time() - executor_events_path.stat().st_mtime
        )
    terminal_events_path = state_dir / "terminal-events.jsonl"
    seconds_since_terminal_event_growth: float | None = None
    if terminal_events_path.is_file():
        seconds_since_terminal_event_growth = max(
            0.0, time.time() - terminal_events_path.stat().st_mtime
        )
    progress = semantic_progress(state_dir)
    seconds_since_semantic_progress = progress["seconds_since_semantic_progress"]
    if seconds_since_semantic_progress is None:
        baseline = data.get("started_at") or data.get("created_at")
        if isinstance(baseline, str) and baseline:
            try:
                seconds_since_semantic_progress = max(
                    0.0, time.time() - datetime.fromisoformat(baseline).timestamp()
                )
            except ValueError:
                pass
    latest_health = last_health_event(state_dir / "run-health-samples.jsonl") or {}
    latest_permission = last_health_event(state_dir / "permission-events.jsonl")
    permission_state = (
        str(latest_permission.get("state"))
        if isinstance(latest_permission, dict) and latest_permission.get("state")
        else None
    )
    process_result_path = state_dir / "process-result.json"
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
    active = {"prepared", "launched", "running", "interruption_requested"}
    if alive is None:
        observed = "terminal_unavailable"
    elif alive and durable in active:
        threshold = settings.stall_minutes * 60
        executor_alive = (
            latest_health.get("executor", {}).get("alive")
            if isinstance(latest_health.get("executor"), dict)
            else None
        )
        if executor_alive is False:
            observed = "orphaned"
        elif permission_state == "pending":
            observed = "blocked_permission"
        elif (
            seconds_since_semantic_progress is None
            or seconds_since_semantic_progress >= threshold
        ):
            observed = "possibly_stalled"
        else:
            observed = "running"
    elif not alive and durable in active:
        observed = "orphaned"
    else:
        observed = durable

    events_path = state_dir / "events.jsonl"
    last_event = None
    if events_path.is_file():
        lines = [line for line in events_path.read_text(encoding="utf-8").splitlines() if line]
        if lines:
            try:
                last_event = json.loads(lines[-1])
            except json.JSONDecodeError:
                last_event = {"error": "invalid final lifecycle event"}
    failure_category = (
        "orphaned"
        if observed == "orphaned"
        else "permission_wait"
        if observed == "blocked_permission"
        else "stalled"
        if observed == "possibly_stalled"
        else "terminal_unavailable"
        if observed == "terminal_unavailable"
        else data.get("failure_category")
    )
    safe_actions = [f"agent-workflow status {session_id} --json"]
    if (
        observed in {"orphaned", "failed", "interrupted", "killed"}
        and bool(data.get("interactive", False))
    ):
        safe_actions.append(f"agent-workflow restart {session_id}")
    elif observed == "possibly_stalled":
        safe_actions.append(f"agent-workflow interrupt {session_id}")
    elif observed == "blocked_permission":
        safe_actions.append(f"agent-workflow attach {session_id}")
    result = {
        **data,
        "tmux_alive": alive,
        "terminal_error": terminal_error,
        "observed_state": observed,
        "failure_category": failure_category,
        "pane_pid": pane.pid if pane else data.get("pane_pid"),
        "pane_command": pane.command if pane else data.get("pane_command"),
        "seconds_since_log_growth": (
            round(seconds_since_log_growth, 1)
            if seconds_since_log_growth is not None
            else None
        ),
        "seconds_since_heartbeat": (
            round(seconds_since_heartbeat, 1)
            if seconds_since_heartbeat is not None
            else None
        ),
        "seconds_since_executor_event_growth": (
            round(seconds_since_executor_event_growth, 1)
            if seconds_since_executor_event_growth is not None
            else None
        ),
        "seconds_since_terminal_event_growth": (
            round(seconds_since_terminal_event_growth, 1)
            if seconds_since_terminal_event_growth is not None
            else None
        ),
        "seconds_since_semantic_progress": (
            round(float(seconds_since_semantic_progress), 1)
            if seconds_since_semantic_progress is not None
            else None
        ),
        "last_semantic_progress_at": progress["last_semantic_progress_at"],
        "last_semantic_progress_source": progress["last_semantic_progress_source"],
        "latest_health": latest_health,
        "permission_state": permission_state,
        "latest_permission_event": latest_permission,
        "output_capture_exhausted": output_capture_exhausted,
        "signals": {
            "tmux_alive": alive,
            "pane_dead": pane.dead if pane else None,
            "log_exists": log_path.is_file(),
            "heartbeat_exists": heartbeat_path.is_file(),
            "executor_events_exist": executor_events_path.is_file(),
            "terminal_events_exist": terminal_events_path.is_file(),
            "health_samples_exist": (state_dir / "run-health-samples.jsonl").is_file(),
            "permission_events_exist": (state_dir / "permission-events.jsonl").is_file(),
        },
        "last_event": last_event,
        "paths": {
            "status": str(state_dir / "status.json"),
            "log": str(log_path),
            "heartbeat": str(heartbeat_path),
            "executor_events": str(executor_events_path),
            "terminal_events": str(terminal_events_path),
            "health_samples": str(state_dir / "run-health-samples.jsonl"),
            "permission_events": str(state_dir / "permission-events.jsonl"),
            "incident_events": str(state_dir / "incident-events.jsonl"),
            "remediation_events": str(state_dir / "remediation-events.jsonl"),
            "process_result": str(process_result_path),
            "events": str(events_path),
        },
        "safe_actions": safe_actions,
        "next_action": safe_actions[-1],
    }
    if capture_lines and alive:
        capture_target = pane.pane_id if pane and pane.pane_id else str(
            data.get("tmux_target", session_id)
        )
        result["capture"] = tmux.capture(capture_target, capture_lines)
    return result


def _active_run(settings: Settings, session_id: str) -> dict[str, Any]:
    status = read_status(settings, session_id)
    if str(status.get("status")) in TERMINAL_STATUSES:
        raise WorkflowError("cannot send a control message to a terminal session")
    return status


def _child_lifecycle_control(session_id: str) -> dict[str, Any] | None:
    """Keep sandboxed children from mutating host-owned lifecycle state.

    The runner owns tmux and the canonical state root.  A child completes by
    writing its handoff and exiting; the host collects and seals that exit.
    """
    if bridge_available(session_id) or bridge_required(session_id):
        return {
            "outcome": "unavailable",
            "reason": "lifecycle controls are host-owned; exit the child normally",
        }
    return None


def _append_control_message(
    settings: Settings,
    session_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Persist first, then issue a best-effort tmux wake hint."""
    state_dir = run_dir(settings, session_id)
    channel = tmux.wakeup_channel(state_dir)
    return append_message(
        state_dir,
        session_id=session_id,
        after_commit=lambda _message: tmux.signal_waiters(channel),
        **kwargs,
    )


def steer(
    settings: Settings,
    session_id: str,
    *,
    actor: str,
    content: str,
) -> dict[str, Any]:
    """Persist a parent steering request and queue bounded adapter delivery."""
    _active_run(settings, session_id)
    message = _append_control_message(
        settings,
        session_id,
        direction="parent_to_child",
        kind="steer",
        actor=actor,
        content=content,
    )
    delivery = queue_request(run_dir(settings, session_id), message)
    return {**message, "delivery_outcome": delivery["outcome"], "delivery_event_id": delivery["event_id"]}


def progress(
    settings: Settings,
    session_id: str,
    *,
    actor: str,
    content: str,
) -> dict[str, Any]:
    """Persist an explicit child progress update for its parent."""
    if bridge_available(session_id):
        return write_control_intent(
            session_id=session_id, kind="progress", actor=actor, content=content
        )
    if bridge_required(session_id):
        return {"outcome": "unavailable", "reason": "control bridge unavailable"}
    _active_run(settings, session_id)
    return _append_control_message(
        settings,
        session_id,
        direction="child_to_parent",
        kind="progress",
        actor=actor,
        content=content,
    )


def acknowledge(
    settings: Settings,
    session_id: str,
    *,
    actor: str,
    content: str,
    correlation_id: str,
    outcome: str = "applied",
) -> dict[str, Any]:
    """Record a correlated applied or rejected steering acknowledgement."""
    if outcome not in {"applied", "rejected"}:
        raise WorkflowError("acknowledgement outcome must be applied or rejected")
    if bridge_available(session_id):
        return write_control_intent(
            session_id=session_id, kind="ack", actor=actor, content=content,
            correlation_id=correlation_id, outcome=outcome,
        )
    if bridge_required(session_id):
        return {"outcome": "unavailable", "reason": "control bridge unavailable"}
    _active_run(settings, session_id)
    state_dir = run_dir(settings, session_id)
    existing_delivery = current_delivery(state_dir, correlation_id)
    if existing_delivery is not None and existing_delivery["outcome"] in {
        "applied", "rejected", "expired",
    }:
        prior = str(existing_delivery["outcome"])
        if prior == "expired":
            raise WorkflowError("steering request already expired")
        if prior != outcome:
            raise WorkflowError(
                f"steering request already has terminal outcome {prior}"
            )
        existing_ack = next(
            (
                item for item in reversed(replay_messages(state_dir))
                if item.get("kind") == "ack"
                and item.get("correlation_id") == correlation_id
            ),
            None,
        )
        if existing_ack is None:
            raise WorkflowError(
                "terminal steering evidence has no correlated acknowledgement"
            )
        return {
            **existing_ack,
            "delivery_outcome": prior,
            "duplicate": True,
        }
    message = _append_control_message(
        settings,
        session_id,
        direction="child_to_parent",
        kind="ack",
        actor=actor,
        content=content,
        correlation_id=correlation_id,
    )
    record_acknowledgement(
        state_dir,
        correlation_id=correlation_id,
        outcome=outcome,
        reason=content,
    )
    acknowledge_reuse(settings, session_id, correlation_id, actor)
    return {**message, "delivery_outcome": outcome}


def messages(settings: Settings, session_id: str, *, after_sequence: int = 0) -> list[dict[str, Any]]:
    read_status(settings, session_id)
    return replay_messages(run_dir(settings, session_id), after_sequence=after_sequence)


def wait_for_message(
    settings: Settings,
    session_id: str,
    *,
    after_sequence: int = 0,
    timeout_seconds: float | None = None,
) -> list[dict[str, Any]]:
    read_status(settings, session_id)
    state_dir = run_dir(settings, session_id)
    return wait_for_messages(
        state_dir,
        after_sequence=after_sequence,
        timeout_seconds=timeout_seconds,
        wakeup_channel=tmux.wakeup_channel(state_dir),
        wait_for_wakeup=tmux.wait_for_wakeup,
    )


def interrupt(settings: Settings, session_id: str) -> dict[str, Any]:
    child_control = _child_lifecycle_control(session_id)
    if child_control is not None:
        return child_control
    prior = read_status(settings, session_id)
    host_session = str(prior.get("tmux_session", session_id))
    if not tmux.session_exists(host_session):
        raise WorkflowError(f"session is not running: {session_id}")
    pane = tmux.resolve_status_pane(prior)
    if pane is None or pane.pane_id is None:
        raise WorkflowError(f"agent pane is unavailable or not bound to session: {session_id}")
    tmux.interrupt(pane.pane_id)
    return update_status(
        settings,
        session_id,
        status="interruption_requested",
        prior_status=prior.get("status"),
        interruption_requested_at=utc_now(),
    )


def terminate(
    settings: Settings,
    session_id: str,
    grace_seconds: int,
) -> dict[str, Any]:
    child_control = _child_lifecycle_control(session_id)
    if child_control is not None:
        return child_control
    prior = read_status(settings, session_id)
    host_session = str(prior.get("tmux_session", session_id))
    if tmux.session_exists(host_session):
        pane = tmux.resolve_status_pane(prior)
        if pane is not None and pane.pane_id is not None:
            tmux.interrupt(pane.pane_id)
        deadline = time.time() + max(0, grace_seconds)
        while time.time() < deadline and tmux.resolve_status_pane(prior) is not None:
            time.sleep(0.25)
        if tmux.resolve_status_pane(prior) is not None:
            if prior.get("tmux_mode") == "shared_window":
                pane = tmux.resolve_status_pane(prior)
                if pane is not None and pane.pane_id is not None:
                    tmux.kill_pane(pane.pane_id)
            else:
                tmux.kill(session_id)
    current = read_status(settings, session_id)
    if str(current.get("status")) not in TERMINAL_STATUSES:
        current = update_status(
            settings,
            session_id,
            status="interrupted",
            finished_at=utc_now(),
            terminated_by_operator=True,
        )
    return current


def kill(settings: Settings, session_id: str) -> dict[str, Any]:
    child_control = _child_lifecycle_control(session_id)
    if child_control is not None:
        return child_control
    prior = read_status(settings, session_id)
    host_session = str(prior.get("tmux_session", session_id))
    if tmux.session_exists(host_session):
        if prior.get("tmux_mode") == "shared_window":
            pane = tmux.resolve_status_pane(prior)
            if pane is not None and pane.pane_id is not None:
                tmux.kill_pane(pane.pane_id)
        else:
            tmux.kill(session_id)
    current = read_status(settings, session_id)
    if str(current.get("status")) in TERMINAL_STATUSES:
        return current
    return update_status(
        settings,
        session_id,
        status="killed",
        finished_at=utc_now(),
        killed_by_operator=True,
    )


def next_retry_id(settings: Settings, original: str) -> str:
    existing = {str(item.get("session_id")) for item in list_statuses(settings)}
    index = 1
    while True:
        candidate = f"{original}-retry{index}"
        terminal_exists = False
        try:
            terminal_exists = tmux.session_exists(candidate)
        except WorkflowError:
            pass
        if candidate not in existing and not terminal_exists:
            return candidate
        index += 1


def restart(
    settings: Settings,
    session_id: str,
    new_session: str | None = None,
) -> dict[str, Any]:
    child_control = _child_lifecycle_control(session_id)
    if child_control is not None:
        return child_control
    state_dir = run_dir(settings, session_id)
    contract = read_launch_contract(state_dir / "launch-contract.json")
    lifecycle = reconstruct_lifecycle(state_dir / "events.jsonl")
    execution_status = lifecycle.get("state", {}).get("execution")
    command_data = read_contract(state_dir / "command.json", "agent-workflow/command/v1")
    command_plan = contract["command_plan"]
    command = command_data.get("argv")
    if command != command_plan.get("argv"):
        raise WorkflowError("cannot restart: saved command differs from launch contract")
    for field in (
        "executor",
        "model",
        "stream_format",
        "interactive",
        "executor_interactive",
        "environment_allowlist",
    ):
        if command_data.get(field) != command_plan.get(field):
            raise WorkflowError(f"cannot restart: command {field} differs from launch contract")
    if not isinstance(command, list) or not command or not all(
        isinstance(item, str) for item in command
    ):
        raise WorkflowError(f"invalid saved command for session {session_id}")
    encoded = json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() != command_plan.get("command_sha256"):
        raise WorkflowError(
            "cannot restart: the immutable contract cannot reconstruct the original command"
        )
    if (
        not bool(command_plan.get("interactive", False))
        and execution_status not in TERMINAL_STATUSES
    ):
        raise WorkflowError(
            "non-interactive tasks cannot be restarted while active; launch a new "
            "task or have the calling agent delegate the work again"
        )
    new_id = new_session or next_retry_id(settings, session_id)
    session = contract["session"]
    pack = contract["pack"]
    worktree = contract["worktree"]
    prompt = contract["prompt"]
    # Agent-name reuse is a mutable lease/projection concern. Allocate a fresh
    # identity for the retry so a tampered status cannot reserve or redirect it.
    restart_agent_name = None
    prompt_source = Path(str(prompt["source"]))
    prompt_read = read_regular_file(prompt_source)
    if prompt_read.sha256 != prompt["sha256"]:
        raise WorkflowError("cannot restart: launch prompt source changed")
    interactive = bool(command_plan.get("interactive", False))
    no_go_authorized = bool(contract["runtime_policy"].get("no_go_authorized", False))
    if bool(command_data.get("no_go_authorized", False)) != no_go_authorized:
        raise WorkflowError("cannot restart: model authorization differs from launch contract")
    job_path = None
    binding_path = state_dir / "job-binding.json"
    if binding_path.is_file():
        binding = read_contract(binding_path, "agent-workflow/job-binding/v1")
        source = Path(str(binding["job_source_path"]))
        expected = str(binding["job_source_sha256"])
        if not source.is_file() or sha256_file(source) != expected:
            raise WorkflowError(
                "cannot restart: native job binding source is missing or changed"
            )
        job_path = source
    return launch(
        settings,
        session_id=new_id,
        workdir=Path(str(worktree["path"])),
        prompt_path=prompt_source,
        explicit_command=command,
        agent_name=restart_agent_name,
        agent_class=session.get("agent_class"),
        model=command_data.get("model"),
        reasoning_effort=contract["runtime_policy"].get("codex_reasoning_effort"),
        allow_no_go_model=no_go_authorized,
        ticket_id=contract.get("ticket"),
        pack_id=pack.get("id"),
        retry_of=session_id,
        allow_dirty=True,
        saved_stream_format=str(command_data.get("stream_format", "text")),
        saved_executor=command_data.get("executor"),
        interactive=interactive,
        prompt_source_override=prompt_source,
        prompt_pack_root_override=(
            Path(str(pack["root"]))
            if pack.get("root")
            else None
        ),
        evaluation_path=(
            Path(str(contract["evaluation_policy"]["path"]))
            if contract["evaluation_policy"].get("path")
            else None
        ),
        tier=session.get("tier"),
        job_path=job_path,
        allow_active_agent_name=False,
    )
