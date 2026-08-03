"""Dispatch for session lifecycle and operator-control commands."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from ..approval import force_accept
from ..archive import archive_runs
from ..cli_output import print_json, print_table
from ..config import Settings
from ..errors import InteractiveCapacityError, WorkflowError
from ..finalization import finalize_run
from ..lifecycle import record as record_lifecycle
from ..sessions import acknowledge as acknowledge_message
from ..sessions import interrupt as interrupt_session
from ..sessions import kill as kill_session
from ..sessions import launch as launch_session
from ..sessions import observe
from ..sessions import progress as record_progress
from ..sessions import restart as restart_session
from ..sessions import steer as steer_session
from ..sessions import terminate as terminate_session
from ..sessions import wait_for_message
from ..state import list_statuses, read_status, repair_status
from ..tmux import attach as attach_tmux


SESSION_COMMANDS = frozenset(
    {
        "launch",
        "list",
        "archive",
        "clear",
        "status",
        "repair",
        "finalize",
        "attach",
        "tail",
        "steer",
        "progress",
        "ack",
        "watch",
        "interrupt",
        "terminate",
        "kill",
        "restart",
        "review",
        "accept",
        "reject",
        "force-accept",
    }
)


def _launch(settings: Settings, args: argparse.Namespace) -> Any:
    interactive_override = args.interactive
    structured_override = args.structured
    while True:
        try:
            return launch_session(
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
        except InteractiveCapacityError as exc:
            action = args.pane_limit_action
            if action == "prompt":
                if args.json or not sys.stdin.isatty():
                    raise
                idle = ", ".join(
                    f"{item.get('agent_name') or item['session_id']} ({item['state']})"
                    for item in exc.idle_sessions
                ) or "none"
                print(f"Interactive pane limit reached ({exc.count}/{exc.maximum}).")
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
                choice = input(
                    close_label + noninteractive_label + "[q] cancel: "
                ).strip().lower()
                action = {
                    "c": "close-idle",
                    "n": "non-interactive",
                    "q": "cancel",
                }.get(choice, "cancel")
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
                structured_override = True
                continue
            raise WorkflowError("interactive launch cancelled at pane limit")


def _list_sessions(settings: Settings, args: argparse.Namespace) -> None:
    rows: list[dict[str, Any]] = []
    for item in list_statuses(settings):
        session_id = str(item.get("session_id", ""))
        try:
            rows.append(observe(settings, session_id))
        except WorkflowError:
            rows.append(item)
    if args.json:
        print_json(rows)
    else:
        print_table(
            rows,
            [
                ("session_id", "SESSION"),
                ("ticket_id", "TICKET"),
                ("status", "DURABLE"),
                ("observed_state", "OBSERVED"),
                ("branch", "BRANCH"),
            ],
        )


def handle_session_command(
    settings: Settings,
    args: argparse.Namespace,
    *,
    argv: Sequence[str] | None = None,
) -> tuple[Any, bool]:
    """Return ``(data, output_complete)`` for one session-domain command."""
    command = args.command
    if command == "launch":
        return _launch(settings, args), False
    if command == "list":
        _list_sessions(settings, args)
        return None, True
    if command in {"archive", "clear"}:
        return (
            archive_runs(
                settings,
                args.session_ids,
                all_verified=args.all_verified,
                confirmed=args.verified,
                dry_run=args.dry_run,
                reason=args.reason,
            ),
            False,
        )
    if command == "status":
        capture_lines = settings.capture_lines if args.capture == -1 else args.capture
        return observe(settings, args.session_id, capture_lines), False
    if command == "repair":
        return repair_status(settings, args.session_id), False
    if command == "finalize":
        observation = observe(settings, args.session_id)
        return finalize_run(settings, args.session_id, observation=observation), False
    if command == "attach":
        read_status(settings, args.session_id)
        attach_tmux(args.session_id)
        return None, True
    if command == "tail":
        status_data = read_status(settings, args.session_id)
        log = Path(str(status_data["log_path"]))
        os.execvp("tail", ["tail", "-n", str(args.lines), "-f", str(log)])
        raise AssertionError("os.execvp returned unexpectedly")
    if command == "steer":
        return (
            steer_session(
                settings,
                args.session_id,
                actor=args.actor,
                content=args.content,
            ),
            False,
        )
    if command == "progress":
        return (
            record_progress(
                settings,
                args.session_id,
                actor=args.actor,
                content=args.content,
            ),
            False,
        )
    if command == "ack":
        return (
            acknowledge_message(
                settings,
                args.session_id,
                actor=args.actor,
                content=args.content,
                correlation_id=args.correlation_id,
                outcome=args.outcome,
            ),
            False,
        )
    if command == "watch":
        return (
            wait_for_message(
                settings,
                args.session_id,
                after_sequence=args.after,
                timeout_seconds=args.timeout,
            ),
            False,
        )
    if command == "interrupt":
        return interrupt_session(settings, args.session_id), False
    if command == "terminate":
        return terminate_session(settings, args.session_id, args.grace_seconds), False
    if command == "kill":
        return kill_session(settings, args.session_id), False
    if command == "restart":
        return restart_session(settings, args.session_id, args.new_session), False
    if command in {"review", "accept", "reject"}:
        action = (
            "reviewed"
            if command == "review"
            else ("accepted" if command == "accept" else "rejected")
        )
        return (
            record_lifecycle(
                settings,
                args.session_id,
                action=action,
                actor=args.actor,
                reason=args.reason,
                revision=args.revision if command == "accept" else None,
            ),
            False,
        )
    if command == "force-accept":
        invocation = list(sys.argv if argv is None else ["agent-workflow", *argv])
        return (
            force_accept(
                settings,
                args.session_id,
                actor=args.actor,
                reason=args.reason,
                acknowledgement=args.acknowledge,
                command=invocation,
            ),
            False,
        )
    raise WorkflowError(f"unhandled session command: {command}")
