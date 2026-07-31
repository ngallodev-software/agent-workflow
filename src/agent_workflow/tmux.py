from __future__ import annotations
import os
import hashlib
from dataclasses import dataclass
from pathlib import Path
from .errors import WorkflowError
from .process import require_command, run


@dataclass(frozen=True)
class PaneInfo:
    pid: int | None
    dead: bool
    command: str | None
    pane_id: str | None = None
    session_name: str | None = None
    window_index: str | None = None
    run_id: str | None = None
    assignment_id: str | None = None


PANE_FORMAT = (
    "#{pane_id}\t#{pane_pid}\t#{pane_dead}\t#{pane_current_command}\t"
    "#{session_name}\t#{window_index}\t#{@agent-workflow-session-id}\t"
    "#{@agent-workflow-assignment-id}"
)
RUN_METADATA = "@agent-workflow-session-id"
ASSIGNMENT_METADATA = "@agent-workflow-assignment-id"


def ensure_tmux():
    require_command("tmux")


def configure_server(*, mouse: bool) -> None:
    """Best-effort UI defaults for an available tmux server.

    Session creation remains the authoritative availability check; cosmetic
    server options must not make a prepared launch fail or break test seams.
    """
    try:
        ensure_tmux()
        run(["tmux", "set-option", "-g", "mouse", "on" if mouse else "off"])
        run(["tmux", "set-option", "-g", "pane-border-status", "top"])
        run(["tmux", "set-option", "-g", "pane-border-format", " #[bold]#{pane_title} "])
    except WorkflowError:
        return


def set_pane_name(target: str, name: str) -> None:
    run(["tmux", "select-pane", "-t", target, "-T", name])
    run(["tmux", "set-option", "-p", "-t", target, "@agent-workflow-name", name])


def set_pane_binding(
    target: str,
    *,
    run_id: str,
    assignment_id: str | None = None,
) -> None:
    """Bind one pane to an application run, clearing stale assignment data."""
    run(["tmux", "set-option", "-p", "-t", target, RUN_METADATA, run_id])
    run(
        [
            "tmux", "set-option", "-p", "-t", target,
            ASSIGNMENT_METADATA, assignment_id or "",
        ]
    )


def wakeup_channel(run_dir: Path) -> str:
    """Return a stable, non-sensitive wait-for channel for one run directory."""
    resolved = str(run_dir.resolve()).encode("utf-8")
    digest = hashlib.sha256(resolved).hexdigest()
    return f"agent-workflow/v1/{digest}"


def orchestrator_wakeup_channel(orchestrator_id: str) -> str:
    """Return one opaque shared channel for an orchestrator identity."""
    if not isinstance(orchestrator_id, str) or not orchestrator_id:
        raise WorkflowError("orchestrator identity must be non-empty text")
    digest = hashlib.sha256(orchestrator_id.encode("utf-8")).hexdigest()
    return f"agent-workflow/v1/orchestrator/{digest}"


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
    try:
        result = run(
            ["tmux", "wait-for", channel],
            check=False,
            timeout_seconds=timeout_seconds,
            max_stdout_bytes=0,
            max_stderr_bytes=0,
        )
        return result.returncode == 0
    except WorkflowError:
        return False


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


def interactive_pane_count(target: str) -> int:
    """Count live non-orchestrator panes in one window."""
    lines = run(
        [
            "tmux", "list-panes", "-t", target, "-F",
            "#{pane_id}\t#{@agent-workflow-role}\t#{pane_dead}",
        ]
    ).stdout.splitlines()
    invoking = os.environ.get("TMUX_PANE")
    count = 0
    for line in lines:
        parts = line.split("\t")
        if len(parts) != 3 or parts[2] != "0":
            continue
        if parts[0] == invoking or parts[1] == "orchestrator":
            continue
        count += 1
    return count


def ensure_interactive_capacity(target: str, maximum: int) -> int:
    """Reject a pane launch before mutation when the live agent stack is full."""
    count = interactive_pane_count(target)
    if count >= maximum:
        raise WorkflowError(f"interactive agent pane limit reached: {count}/{maximum}")
    return count


def split_window(
    target: str,
    workdir: str,
    runner: str,
    *,
    orchestrator_side: str = "left",
    pane_name: str = "agent",
    max_interactive_agent_panes: int | None = 6,
    max_interactive_agent_width: int | None = 2,
    max_interactive_agent_vertical: int | None = 3,
) -> str:
    """Create agent columns first, then balance vertical panes across them."""
    panes = run(
        [
            "tmux", "list-panes", "-t", target, "-F",
            "#{pane_id}\t#{@agent-workflow-role}\t#{pane_left}\t#{pane_top}\t#{pane_dead}\t#{@agent-workflow-column}",
        ]
    ).stdout.splitlines()
    live_panes: list[dict[str, int | str | None]] = []
    orchestrator_panes: set[str] = set()
    for line in panes:
        parts = line.split("\t")
        if len(parts) == 6 and parts[4] == "0":
            try:
                column = int(parts[5]) if parts[5] else None
                pane: dict[str, int | str | None] = {
                    "id": parts[0],
                    "role": parts[1],
                    "left": int(parts[2]),
                    "top": int(parts[3]),
                    "column": column,
                }
            except ValueError:
                continue
            live_panes.append(pane)
            if parts[1] == "orchestrator":
                orchestrator_panes.add(parts[0])
    invoking_pane = os.environ.get("TMUX_PANE")
    non_orchestrator = [
        pane
        for pane in live_panes
        if pane["id"] != invoking_pane and pane["id"] not in orchestrator_panes
    ]
    if (
        max_interactive_agent_panes is not None
        and len(non_orchestrator) >= max_interactive_agent_panes
    ):
        raise WorkflowError(
            "interactive agent pane limit reached: "
            f"{len(non_orchestrator)}/{max_interactive_agent_panes}"
        )
    layout_limited = (
        max_interactive_agent_width is not None
        and max_interactive_agent_vertical is not None
    )
    width = max_interactive_agent_width or 1
    vertical = max_interactive_agent_vertical or 1
    ordered_left = sorted(
        {int(pane["left"]) for pane in non_orchestrator},
        reverse=orchestrator_side == "right",
    )
    inferred_columns = {left: index + 1 for index, left in enumerate(ordered_left)}
    columns: dict[int, list[dict[str, int | str | None]]] = {}
    for pane in non_orchestrator:
        column = pane["column"] or inferred_columns[int(pane["left"])]
        columns.setdefault(int(column), []).append(pane)

    new_column: int
    if not columns:
        split_target = invoking_pane or target
        split_flag = "-h"
        before = ["-b"] if orchestrator_side == "right" else []
        new_column = 1
        if invoking_pane:
            run(["tmux", "set-option", "-p", "-t", invoking_pane, "@agent-workflow-role", "orchestrator"])
    elif not layout_limited:
        edge_column = max(columns) if orchestrator_side == "left" else min(columns)
        split_target = str(max(columns[edge_column], key=lambda item: int(item["top"]))["id"])
        split_flag = "-v"
        before = []
        new_column = edge_column
    elif len(columns) < width:
        edge_column = max(columns) if orchestrator_side == "left" else min(columns)
        split_target = str(min(columns[edge_column], key=lambda item: int(item["top"]))["id"])
        split_flag = "-h"
        before = ["-b"] if orchestrator_side == "right" else []
        new_column = max(columns) + 1
    else:
        available = [
            (column, panes_in_column)
            for column, panes_in_column in sorted(columns.items())
            if len(panes_in_column) < vertical
        ]
        if not available:
            raise WorkflowError(
                "interactive agent pane grid is full: "
                f"{width} columns x {vertical} vertical panes"
            )
        new_column, selected = min(available, key=lambda item: (len(item[1]), item[0]))
        split_target = str(max(selected, key=lambda item: int(item["top"]))["id"])
        split_flag = "-v"
        before = []
    result = run(
        [
            "tmux", "split-window", split_flag, *before, "-d", "-P", "-F",
            "#{pane_id}",
            "-t", split_target, "-c", workdir, runner,
        ],
        check=False,
    )
    pane_target = result.stdout.strip()
    if result.returncode or not pane_target:
        detail = (result.stderr or result.stdout or "").strip()
        raise WorkflowError(f"failed to create tmux runner pane: {detail}")
    run(["tmux", "set-option", "-p", "-t", pane_target, "remain-on-exit", "on"])
    run(["tmux", "set-option", "-p", "-t", pane_target, "@agent-workflow-role", "agent"])
    run(["tmux", "set-option", "-p", "-t", pane_target, "@agent-workflow-column", str(new_column)])
    set_pane_name(pane_target, pane_name)
    return pane_target


def session_exists(session_id: str) -> bool:
    ensure_tmux()
    return run(["tmux", "has-session", "-t", session_id], check=False).returncode == 0


def create_session(session_id: str, workdir: str, runner: str, pane_name: str = "agent"):
    ensure_tmux()
    run(["tmux", "new-session", "-d", "-s", session_id, "-c", workdir, runner])
    run(["tmux", "set-option", "-p", "-t", session_id, "remain-on-exit", "on"])
    set_pane_name(session_id, pane_name)


def _parse_pane_info(line: str) -> PaneInfo | None:
    parts = line.split("\t", 7)
    if len(parts) != 8:
        return None
    try:
        pid = int(parts[1])
    except ValueError:
        pid = None
    return PaneInfo(
        pid=pid,
        dead=parts[2] == "1",
        command=parts[3] or None,
        pane_id=parts[0] or None,
        session_name=parts[4] or None,
        window_index=parts[5] or None,
        run_id=parts[6] or None,
        assignment_id=parts[7] or None,
    )


def pane_info(target: str) -> PaneInfo | None:
    """Read exactly *target*, including stable ID and run-binding metadata."""
    result = run(
        ["tmux", "display-message", "-p", "-t", target, "-F", PANE_FORMAT],
        check=False,
    )
    if result.returncode:
        return None
    lines = result.stdout.splitlines()
    return _parse_pane_info(lines[0]) if lines else None


def list_panes(target: str) -> list[PaneInfo]:
    """List pane identities in a session/window for legacy recovery."""
    result = run(
        ["tmux", "list-panes", "-t", target, "-F", PANE_FORMAT],
        check=False,
    )
    if result.returncode:
        return []
    return [
        parsed
        for line in result.stdout.splitlines()
        if (parsed := _parse_pane_info(line)) is not None
    ]


def resolve_pane(
    target: str,
    *,
    host_session: str | None = None,
    run_id: str | None = None,
    require_binding: bool = False,
) -> PaneInfo | None:
    """Resolve a pane without trusting a mutable positional target.

    New records use ``%pane_id``. Older shared-window records may use a
    positional target; those are recovered only when exactly one pane in the
    host session carries the expected run binding. A name, PID, or position
    never authorizes recovery.
    """
    if require_binding and not target.startswith("%"):
        if not run_id or not host_session:
            return None
        scan_target = (
            target.rsplit(".", 1)[0]
            if ":" in target and "." in target
            else host_session
        )
        matches = [pane for pane in list_panes(scan_target) if pane.run_id == run_id]
        return matches[0] if len(matches) == 1 else None

    direct = pane_info(target)
    if direct is not None:
        if not run_id:
            return direct
        if direct.run_id == run_id or (not require_binding and target == run_id):
            return direct
        if target.startswith("%"):
            return None
    if not run_id or not host_session or not target or target.startswith("%"):
        return None
    scan_target = (
        target.rsplit(".", 1)[0]
        if ":" in target and "." in target
        else host_session
    )
    matches = [pane for pane in list_panes(scan_target) if pane.run_id == run_id]
    if len(matches) != 1:
        return None
    recovered = matches[0]
    if require_binding and recovered.run_id != run_id:
        return None
    return recovered


def resolve_status_pane(status: dict[str, object]) -> PaneInfo | None:
    """Resolve a persisted run status using its run-bound pane identity."""
    target_value = (
        status.get("tmux_target")
        if status.get("tmux_mode") != "shared_window"
        else status.get("tmux_pane_id") or status.get("tmux_target")
    )
    target = str(target_value or "")
    if not target:
        return None
    run_id = str(status.get("session_id") or "") or None
    return resolve_pane(
        target,
        host_session=str(status.get("tmux_session") or "") or None,
        run_id=run_id,
        require_binding=status.get("tmux_mode") == "shared_window",
    )


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
