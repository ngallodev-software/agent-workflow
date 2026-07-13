from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from . import tmux
from .assets import asset_path
from .config import Settings
from .errors import WorkflowError
from .git import snapshot
from .process import run
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

_STATUS_HELPER = r'''#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
status = sys.argv[2]
exit_code = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    data = {}
now = datetime.now(timezone.utc).isoformat()
data["status"] = status
data["updated_at"] = now
if status == "running":
    data.setdefault("started_at", now)
if status in {"completed", "failed", "interrupted", "killed"}:
    data["finished_at"] = now
if exit_code is not None:
    data["exit_code"] = exit_code
fd, tmp = tempfile.mkstemp(prefix=".status.", dir=path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
finally:
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
'''


def _resolve_command(
    settings: Settings,
    executor: str | None,
    explicit: list[str] | None,
) -> list[str]:
    if explicit:
        return explicit
    if not executor:
        raise WorkflowError(
            "provide --executor NAME or an explicit command after --"
        )
    try:
        command = settings.executors[executor]
    except KeyError as exc:
        known = ", ".join(sorted(settings.executors)) or "none"
        raise WorkflowError(
            f"unknown executor {executor!r}; configured executors: {known}"
        ) from exc
    if not command:
        raise WorkflowError(f"executor {executor!r} has an empty command")
    return list(command)


def _ignore_delegations(workdir: Path) -> None:
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
    entry = ".delegations/"
    if entry not in {line.strip() for line in existing.splitlines()}:
        with exclude.open("a", encoding="utf-8") as stream:
            if existing and not existing.endswith("\n"):
                stream.write("\n")
            stream.write(entry + "\n")


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
) -> Path:
    prompt = state_dir / "prompt.md"
    log = state_dir / "output.log"
    status = state_dir / "status.json"
    helper = state_dir / "update_status.py"
    helper.write_text(_STATUS_HELPER, encoding="utf-8")
    helper.chmod(0o755)

    runner = state_dir / "run.sh"
    command_text = shlex.join(command)
    runner.write_text(
        "#!/usr/bin/env bash\n"
        "set -Eeuo pipefail\n"
        f"STATUS_FILE={shlex.quote(str(status))}\n"
        f"STATUS_HELPER={shlex.quote(str(helper))}\n"
        f"PROMPT_FILE={shlex.quote(str(prompt))}\n"
        f"LOG_FILE={shlex.quote(str(log))}\n"
        f"WORKDIR={shlex.quote(str(workdir))}\n"
        "finalize() {\n"
        "  rc=$?\n"
        "  if [[ $rc -eq 0 ]]; then final_status=completed; "
        "elif [[ $rc -eq 130 || $rc -eq 143 ]]; then final_status=interrupted; "
        "else final_status=failed; fi\n"
        "  python3 \"$STATUS_HELPER\" \"$STATUS_FILE\" "
        "\"$final_status\" \"$rc\" || true\n"
        "}\n"
        "trap finalize EXIT\n"
        "python3 \"$STATUS_HELPER\" \"$STATUS_FILE\" running\n"
        "cd \"$WORKDIR\"\n"
        "set +e\n"
        f"cat \"$PROMPT_FILE\" | {command_text} 2>&1 | "
        "tee -a \"$LOG_FILE\"\n"
        "rc=${PIPESTATUS[1]}\n"
        "set -e\n"
        "exit \"$rc\"\n",
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

    command = _resolve_command(settings, executor, explicit_command)
    if not shutil.which(command[0]):
        raise WorkflowError(f"executor command not found on PATH: {command[0]}")

    prompt_copy = state_dir / "prompt.md"
    shutil.copy2(prompt_path, prompt_copy)
    (state_dir / "output.log").touch()
    atomic_write_json(
        state_dir / "command.json",
        {
            "argv": command,
            "shell": shlex.join(command),
            "executor": executor,
        },
    )
    (state_dir / "completion.md").write_bytes(
        asset_path("prompt-pack-root/templates/TICKET_COMPLETION.md").read_bytes()
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

    now = utc_now()
    status: dict[str, Any] = {
        "schema": "agent-workflow/session-status/v1",
        "session_id": session_id,
        "ticket_id": ticket_id,
        "pack_id": pack_id,
        "retry_of": retry_of,
        "status": "prepared",
        "created_at": now,
        "updated_at": now,
        "workdir": str(workdir),
        "prompt_path": str(prompt_copy),
        "prompt_source": str(prompt_path),
        "prompt_sha256": sha256_file(prompt_copy),
        "log_path": str(state_dir / "output.log"),
        "command_path": str(state_dir / "command.json"),
        "completion_path": str(state_dir / "completion.md"),
        "source_baseline_path": str(baseline_path),
        "tmux_session": session_id,
        **git_info,
    }
    write_status(settings, session_id, status)
    _link_worktree_state(workdir, session_id, state_dir)
    runner = _write_runner(state_dir, workdir, command)
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
    seconds_since_log_growth: float | None = None
    if log_path.exists():
        seconds_since_log_growth = max(0.0, time.time() - log_path.stat().st_mtime)

    durable = str(data.get("status", "unknown"))
    active = {"prepared", "launched", "running", "interruption_requested"}
    if alive is None:
        observed = "terminal_unavailable"
    elif alive and durable in active:
        if (
            seconds_since_log_growth is not None
            and seconds_since_log_growth >= settings.stall_minutes * 60
        ):
            observed = "possibly_stalled"
        else:
            observed = "running"
    elif not alive and durable in active:
        observed = "orphaned"
    else:
        observed = durable

    result = {
        **data,
        "tmux_alive": alive,
        "terminal_error": terminal_error,
        "observed_state": observed,
        "pane_pid": pane.pid if pane else data.get("pane_pid"),
        "pane_command": pane.command if pane else data.get("pane_command"),
        "seconds_since_log_growth": (
            round(seconds_since_log_growth, 1)
            if seconds_since_log_growth is not None
            else None
        ),
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
    )
