from __future__ import annotations
import os
import hashlib
import subprocess
from dataclasses import dataclass
from .errors import WorkflowError
from .process import require_command, run


@dataclass(frozen=True)
class PaneInfo:
    pid: int | None
    dead: bool
    command: str | None


def ensure_tmux():
    require_command("tmux")


def wakeup_channel(run_dir: Path) -> str:
    """Return a stable, non-sensitive wait-for channel for one run directory."""
    resolved = str(run_dir.resolve()).encode("utf-8")
    digest = hashlib.sha256(resolved).hexdigest()
    return f"agent-workflow/v1/{digest}"


def signal_waiters(channel: str) -> None:
    """Best-effort wake hint; durable message replay remains authoritative."""
    try:
        run(["tmux", "wait-for", "-S", channel], check=False)
    except WorkflowError:
        pass


def wait_for_wakeup(channel: str, timeout_seconds: float) -> bool:
    """Wait at most *timeout_seconds* for a tmux wake hint.

    tmux availability, a missing server, and a timeout are ordinary fallback
    conditions.  Callers must replay their durable log after this returns.
    """
    if timeout_seconds <= 0:
        return False
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            ["tmux", "wait-for", channel],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            return process.wait(timeout=timeout_seconds) == 0
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            return False
    except OSError:
        return False
    except KeyboardInterrupt:
        if process is not None:
            process.kill()
            process.wait()
        raise


def current_window_target() -> str | None:
    """Return the invoking tmux session/window target, if there is one."""
    if not os.environ.get("TMUX"):
        return None
    try:
        result = run(
            ["tmux", "display-message", "-p", "-F", "#{session_name}:#{window_index}"],
            check=False,
        )
    except WorkflowError:
        return None
    target = result.stdout.strip()
    return target if result.returncode == 0 and target else None


def split_window(target: str, workdir: str, runner: str) -> str:
    """Create a detached runner pane in an existing, caller-owned window."""
    result = run(
        [
            "tmux", "split-window", "-d", "-P", "-F",
            "#{session_name}:#{window_index}.#{pane_index}",
            "-t", target, "-c", workdir, runner,
        ],
        check=False,
    )
    pane_target = result.stdout.strip()
    if result.returncode or not pane_target:
        detail = (result.stderr or result.stdout or "").strip()
        raise WorkflowError(f"failed to create tmux runner pane: {detail}")
    return pane_target


def session_exists(session_id: str) -> bool:
    ensure_tmux()
    return run(["tmux", "has-session", "-t", session_id], check=False).returncode == 0


def create_session(session_id: str, workdir: str, runner: str):
    ensure_tmux()
    run(["tmux", "new-session", "-d", "-s", session_id, "-c", workdir, runner])


def pane_info(session_id: str):
    if not session_exists(session_id):
        return None
    line = (
        run(
            [
                "tmux",
                "list-panes",
                "-t",
                session_id,
                "-F",
                "#{pane_pid}	#{pane_dead}	#{pane_current_command}",
            ]
        ).stdout.splitlines()
        or [""]
    )[0]
    parts = line.split("	", 2)
    if len(parts) != 3:
        return PaneInfo(None, False, None)
    try:
        pid = int(parts[0])
    except ValueError:
        pid = None
    return PaneInfo(pid, parts[1] == "1", parts[2] or None)


def capture(session_id: str, lines: int) -> str:
    return run(
        ["tmux", "capture-pane", "-p", "-t", session_id, "-S", f"-{lines}"]
    ).stdout


def attach(session_id: str):
    ensure_tmux()
    os.execvp("tmux", ["tmux", "attach-session", "-t", session_id])


def interrupt(session_id: str):
    run(["tmux", "send-keys", "-t", session_id, "C-c"])


def kill(session_id: str):
    result = run(["tmux", "kill-session", "-t", session_id], check=False)
    if result.returncode and session_exists(session_id):
        detail = (result.stderr or result.stdout or "").strip()
        raise WorkflowError(f"failed to kill tmux session {session_id}: {detail}")


def kill_pane(target: str):
    result = run(["tmux", "kill-pane", "-t", target], check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip()
        raise WorkflowError(f"failed to kill tmux pane {target}: {detail}")
