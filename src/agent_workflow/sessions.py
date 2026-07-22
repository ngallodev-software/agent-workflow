from __future__ import annotations

import json
import platform
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import tmux
from .assets import asset_path
from .config import Settings
from .errors import WorkflowError
from .eval.commands import collect_commands, specs_from_data
from .eval.scope import ScopePolicy, collect_scope
from .evaluation import validate_evaluation
from .executors import ExecutorPlan, executor_version, prepare_executor
from .git import snapshot
from .process import run
from .receipts import initial_completion, initial_provenance, update_provenance
from .state import (
    TERMINAL_STATUSES,
    list_statuses,
    read_status,
    run_dir,
    update_status,
    write_status,
)
from .util import (
    atomic_write_json,
    expand_path,
    sha256_file,
    utc_now,
    validate_id,
)

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
    session_id: str = "unknown-session",
    prompt_source: Path | None = None,
    prompt_pack_root: Path | None = None,
    handoff_dir: Path | None = None,
    stream_format: str = "text",
) -> Path:
    prompt = state_dir / "prompt.md"
    launch_prompt = state_dir / "launch-prompt.md"
    if not launch_prompt.exists() and prompt.exists():
        shutil.copy2(prompt, launch_prompt)
    prompt_source = prompt_source or prompt
    runner = state_dir / "run.sh"
    command_text = shlex.join(command)
    source_root = Path(__file__).resolve().parents[1]
    runner.write_text(
        "#!/usr/bin/env bash\n"
        "set -Eeuo pipefail\n"
        f"readonly AGENT_WORKFLOW_SESSION_ID={shlex.quote(session_id)}\n"
        f"readonly AGENT_WORKFLOW_PROMPT_SOURCE={shlex.quote(str(prompt_source))}\n"
        f"readonly AGENT_WORKFLOW_HANDOFF_DIR={shlex.quote(str(handoff_dir or ''))}\n"
        f"readonly AGENT_WORKFLOW_PROMPT_PACK_ROOT={shlex.quote(str(prompt_pack_root or ''))}\n"
        "export AGENT_WORKFLOW_SESSION_ID AGENT_WORKFLOW_PROMPT_SOURCE "
        "AGENT_WORKFLOW_HANDOFF_DIR AGENT_WORKFLOW_PROMPT_PACK_ROOT\n"
        f"export PYTHONPATH={shlex.quote(str(source_root))}${{PYTHONPATH:+:$PYTHONPATH}}\n"
        "exec python3 -m agent_workflow.runner "
        f"--run-dir {shlex.quote(str(state_dir))} "
        f"--workdir {shlex.quote(str(workdir))} "
        f"--stream-format {shlex.quote(stream_format)} -- {command_text}\n",
        encoding="utf-8",
    )
    runner.chmod(0o755)
    syntax = subprocess.run(
        ["bash", "-n", str(runner)],
        capture_output=True,
        text=True,
        check=False,
    )
    if syntax.returncode:
        raise WorkflowError(
            f"generated runner failed syntax check: {syntax.stderr.strip()}"
        )
    return runner


def _discover_prompt_pack_root(prompt_source: Path) -> Path | None:
    for candidate in prompt_source.parents:
        if (candidate / "pack.yaml").is_file():
            return candidate
    return None


def _write_launch_prompt(
    state_dir: Path,
    *,
    session_id: str,
    prompt_source: Path,
    prompt_pack_root: Path | None,
    handoff_dir: Path,
) -> Path:
    context = [
        "# Agent-workflow launch context",
        "The complete ticket is included below. Do not reread prompt_source unless the ticket explicitly requests it.",
        "Use these durable paths only when the ticket references pack files or its completion report.",
        f"- session_id: `{session_id}`",
        f"- prompt_source: `{prompt_source}`",
    ]
    if prompt_pack_root is not None:
        context.append(f"- prompt_pack_root: `{prompt_pack_root}`")
    context.extend(
        [
            f"- completion_handoff_dir: `{handoff_dir}`",
            "- Write completion JSON only to `AGENT_WORKFLOW_HANDOFF_DIR/completion.json` using schema `agent-workflow/completion/v1`.",
            "- Write it atomically; optional `completion.md` and `evidence.json` sidecars may use the same handoff directory.",
            "- Canonical runtime completion paths are collector-owned; do not write to them.",
            "- Matching environment variables use the `AGENT_WORKFLOW_` prefix.",
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


def launch(
    settings: Settings,
    *,
    session_id: str,
    workdir: Path,
    prompt_path: Path,
    executor: str | None = None,
    explicit_command: list[str] | None = None,
    ticket_id: str | None = None,
    pack_id: str | None = None,
    retry_of: str | None = None,
    allow_dirty: bool = False,
    structured: bool = False,
    saved_stream_format: str | None = None,
    saved_executor: str | None = None,
    prompt_source_override: Path | None = None,
    prompt_pack_root_override: Path | None = None,
    evaluation_path: Path | None = None,
    tier: str | None = None,
) -> dict[str, Any]:
    validate_id(session_id, "session ID")
    if ticket_id:
        validate_id(ticket_id, "ticket ID")
    if pack_id:
        validate_id(pack_id, "pack ID")
    workdir = expand_path(workdir)
    prompt_path = expand_path(prompt_path)
    if not workdir.is_dir():
        raise WorkflowError(f"workdir not found: {workdir}")
    if not prompt_path.is_file():
        raise WorkflowError(f"prompt not found: {prompt_path}")
    if settings.terminal_backend != "tmux":
        raise WorkflowError(
            f"unsupported terminal backend {settings.terminal_backend!r}; v0.1 supports tmux"
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

    executor_plan = prepare_executor(
        settings, executor, explicit_command, structured=structured
    )
    if saved_stream_format is not None:
        executor_plan = ExecutorPlan(
            saved_executor,
            executor_plan.argv,
            saved_stream_format,
        )
    command = list(executor_plan.argv)
    if not shutil.which(command[0]):
        raise WorkflowError(f"executor command not found on PATH: {command[0]}")

    prompt_copy = state_dir / "prompt.md"
    shutil.copy2(prompt_path, prompt_copy)
    prompt_source = prompt_source_override or prompt_path
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
            "argv": command,
            "shell": shlex.join(command),
            "executor": executor_plan.name,
            "stream_format": executor_plan.stream_format,
        },
    )
    (state_dir / "completion.md").write_bytes(
        asset_path("prompt-pack-root/templates/TICKET_COMPLETION.md").read_bytes()
    )
    handoff_dir = _create_handoff_dir(workdir, session_id)
    launch_prompt = _write_launch_prompt(
        state_dir,
        session_id=session_id,
        prompt_source=prompt_source,
        prompt_pack_root=prompt_pack_root,
        handoff_dir=handoff_dir,
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
            argv=command,
            stream_format=executor_plan.stream_format,
            executor_version=(
                executor_version(executor_plan)
                if executor_plan.name is not None
                else None
            ),
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
            },
        ),
    )
    if evaluation_path is not None:
        evaluation = validate_evaluation(
            expand_path(evaluation_path),
            pack_root=prompt_pack_root,
        )
        if ticket_id and ticket_id not in evaluation.task_ids:
            raise WorkflowError(
                f"evaluation plan does not include launched ticket: {ticket_id}"
            )
        commands = evaluation.data.get("acceptance_commands", [])
        scope_data = evaluation.data.get("scope", {})
        runtime = {
            "schema": "agent-workflow/evaluation-runtime/v1",
            "evaluation_path": str(evaluation.path),
            "evaluation_sha256": evaluation.sha256,
            "timeout_seconds": evaluation.data["timeout_seconds"],
            "acceptance_commands": commands,
            "scope": scope_data,
            "scorers": evaluation.data["scorers"],
            "oracle_refs": evaluation.data.get("oracle_refs", {}),
            "statistics_policy": evaluation.data.get(
                "statistics_policy", "agent-workflow/statistics/v1"
            ),
            "ticket_id": ticket_id,
        }
        update_provenance(
            state_dir,
            budgets=evaluation.data.get("budgets", {}),
            evaluation_sha256=evaluation.sha256,
        )
        atomic_write_json(state_dir / "evaluation-runtime.json", runtime)
        if commands:
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

    now = utc_now()
    status: dict[str, Any] = {
        "schema": "agent-workflow/session-status/v2",
        "session_id": session_id,
        "ticket_id": ticket_id,
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
        "prompt_sha256": sha256_file(prompt_copy),
        "prompt_pack_root": str(prompt_pack_root) if prompt_pack_root else None,
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
        "tmux_session": session_id,
        **git_info,
    }
    write_status(settings, session_id, status)
    _link_worktree_state(workdir, session_id, state_dir)
    runner = _write_runner(
        state_dir,
        workdir,
        command,
        session_id=session_id,
        prompt_source=prompt_source,
        prompt_pack_root=prompt_pack_root,
        handoff_dir=handoff_dir,
        stream_format=executor_plan.stream_format,
    )
    update_status(
        settings,
        session_id,
        status="launched",
        launched_at=utc_now(),
        runner_path=str(runner),
    )
    try:
        tmux.create_session(session_id, str(workdir), str(runner))
    except Exception:
        update_status(
            settings,
            session_id,
            status="failed",
            finished_at=utc_now(),
            launch_error=True,
        )
        raise
    pane = tmux.pane_info(session_id)
    return update_status(
        settings,
        session_id,
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
    try:
        alive: bool | None = tmux.session_exists(session_id)
        pane = tmux.pane_info(session_id) if alive else None
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

    durable = str(data.get("status", "unknown"))
    active = {"prepared", "launched", "running", "interruption_requested"}
    if alive is None:
        observed = "terminal_unavailable"
    elif alive and durable in active:
        threshold = settings.stall_minutes * 60
        log_stale = (
            seconds_since_log_growth is None
            or seconds_since_log_growth >= threshold
        )
        heartbeat_stale = (
            seconds_since_heartbeat is None
            or seconds_since_heartbeat >= threshold
        )
        if log_stale and heartbeat_stale:
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
        else "stalled"
        if observed == "possibly_stalled"
        else "terminal_unavailable"
        if observed == "terminal_unavailable"
        else data.get("failure_category")
    )
    safe_actions = [f"agent-workflow status {session_id} --json"]
    if observed in {"orphaned", "failed", "interrupted", "killed"}:
        safe_actions.append(f"agent-workflow restart {session_id}")
    elif observed == "possibly_stalled":
        safe_actions.append(f"agent-workflow interrupt {session_id}")
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
        "signals": {
            "tmux_alive": alive,
            "pane_dead": pane.dead if pane else None,
            "log_exists": log_path.is_file(),
            "heartbeat_exists": heartbeat_path.is_file(),
        },
        "last_event": last_event,
        "paths": {
            "status": str(state_dir / "status.json"),
            "log": str(log_path),
            "heartbeat": str(heartbeat_path),
            "events": str(events_path),
        },
        "safe_actions": safe_actions,
        "next_action": safe_actions[-1],
    }
    if capture_lines and alive:
        result["capture"] = tmux.capture(session_id, capture_lines)
    return result


def interrupt(settings: Settings, session_id: str) -> dict[str, Any]:
    prior = read_status(settings, session_id)
    if not tmux.session_exists(session_id):
        raise WorkflowError(f"session is not running: {session_id}")
    tmux.interrupt(session_id)
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
    read_status(settings, session_id)
    if tmux.session_exists(session_id):
        tmux.interrupt(session_id)
        deadline = time.time() + max(0, grace_seconds)
        while time.time() < deadline and tmux.session_exists(session_id):
            time.sleep(0.25)
        if tmux.session_exists(session_id):
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
    read_status(settings, session_id)
    if tmux.session_exists(session_id):
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
    old = read_status(settings, session_id)
    command_data = json.loads(
        Path(str(old["command_path"])).read_text(encoding="utf-8")
    )
    command = command_data.get("argv")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(item, str) for item in command)
    ):
        raise WorkflowError(f"invalid saved command for session {session_id}")
    new_id = new_session or next_retry_id(settings, session_id)
    return launch(
        settings,
        session_id=new_id,
        workdir=Path(str(old["workdir"])),
        prompt_path=Path(str(old["prompt_path"])),
        explicit_command=command,
        ticket_id=old.get("ticket_id"),
        pack_id=old.get("pack_id"),
        retry_of=session_id,
        allow_dirty=True,
        saved_stream_format=str(command_data.get("stream_format", "text")),
        saved_executor=command_data.get("executor"),
        prompt_source_override=Path(str(old.get("prompt_source", old["prompt_path"]))),
        prompt_pack_root_override=(
            Path(str(old["prompt_pack_root"]))
            if old.get("prompt_pack_root")
            else None
        ),
        evaluation_path=(
            Path(str(old["evaluation_path"]))
            if old.get("evaluation_path")
            else None
        ),
        tier=old.get("tier"),
    )
