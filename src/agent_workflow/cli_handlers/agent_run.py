"""Dispatch for Agent Run lifecycle and durable-control commands."""

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
from ..errors import WorkflowError
from ..finalization import finalize_run
from ..lifecycle import record as record_lifecycle
from ..agent_runs import acknowledge as acknowledge_message
from ..agent_runs import interrupt as interrupt_agent_run
from ..agent_runs import prepare as prepare_agent_run
from ..agent_runs import start as start_agent_run
from ..agent_runs import observe
from ..agent_runs import progress as record_progress
from ..agent_runs import restart as restart_agent_run
from ..agent_runs import steer as steer_agent_run
from ..agent_runs import terminate as terminate_agent_run
from ..agent_runs import wait_for_message
from ..state import list_statuses, read_status, repair_status




def _prepare(settings: Settings, args: argparse.Namespace) -> Any:
    return prepare_agent_run(
        settings,
        agent_run_id=args.agent_run_id,
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
        structured=args.structured,
        interactive=args.interactive,
        prerequisite_ids=args.prerequisites,
        evaluation_path=args.evaluation,
        worker_mode=args.worker_mode,
    )


def _list_agent_runs(settings: Settings, args: argparse.Namespace) -> None:
    rows: list[dict[str, Any]] = []
    for item in list_statuses(settings):
        agent_run_id = str(item.get("agent_run_id", ""))
        try:
            rows.append(observe(settings, agent_run_id))
        except WorkflowError:
            rows.append(item)
    if args.json:
        print_json(rows)
    else:
        print_table(
            rows,
            [
                ("agent_run_id", "AGENT RUN"),
                ("ticket_id", "TICKET"),
                ("status", "DURABLE"),
                ("observed_state", "OBSERVED"),
                ("branch", "BRANCH"),
            ],
        )


def handle_agent_run_command(
    settings: Settings,
    args: argparse.Namespace,
    *,
    argv: Sequence[str] | None = None,
) -> tuple[Any, bool]:
    """Return ``(data, output_complete)`` for one Agent Run domain command."""
    command = args.agent_run_command
    if command == "prepare":
        return _prepare(settings, args), False
    if command == "start":
        return start_agent_run(settings, args.agent_run_id), False
    if command == "list":
        _list_agent_runs(settings, args)
        return None, True
    if command == "archive":
        return (
            archive_runs(
                settings,
                args.agent_run_ids,
                all_verified=args.all_verified,
                confirmed=args.verified,
                dry_run=args.dry_run,
                reason=args.reason,
            ),
            False,
        )
    if command == "status":
        return observe(settings, args.agent_run_id), False
    if command == "repair":
        return repair_status(settings, args.agent_run_id), False
    if command == "finalize":
        observation = observe(settings, args.agent_run_id)
        return finalize_run(settings, args.agent_run_id, observation=observation), False
    if command == "tail":
        status_data = read_status(settings, args.agent_run_id)
        log = Path(str(status_data["log_path"]))
        os.execvp("tail", ["tail", "-n", str(args.lines), "-f", str(log)])
        raise AssertionError("os.execvp returned unexpectedly")
    if command == "steer":
        return (
            steer_agent_run(
                settings,
                args.agent_run_id,
                actor=args.actor,
                content=args.content,
            ),
            False,
        )
    if command == "progress":
        return (
            record_progress(
                settings,
                args.agent_run_id,
                actor=args.actor,
                content=args.content,
            ),
            False,
        )
    if command == "ack":
        return (
            acknowledge_message(
                settings,
                args.agent_run_id,
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
                args.agent_run_id,
                after_sequence=args.after,
                timeout_seconds=args.timeout,
            ),
            False,
        )
    if command == "interrupt":
        return interrupt_agent_run(settings, args.agent_run_id), False
    if command == "terminate":
        return terminate_agent_run(settings, args.agent_run_id, args.grace_seconds), False
    if command == "restart":
        return restart_agent_run(settings, args.agent_run_id, args.new_agent_run_id), False
    if command in {"review", "accept", "reject"}:
        action = (
            "reviewed"
            if command == "review"
            else ("accepted" if command == "accept" else "rejected")
        )
        return (
            record_lifecycle(
                settings,
                args.agent_run_id,
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
                args.agent_run_id,
                actor=args.actor,
                reason=args.reason,
                acknowledgement=args.acknowledge,
                command=invocation,
            ),
            False,
        )
    raise WorkflowError(f"unhandled Agent Run command: {command}")
