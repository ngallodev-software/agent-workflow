"""Dispatch for the ``agent-workflow agent`` command domain."""

from __future__ import annotations

import argparse
from typing import Any

from ..agent_context import auto_reuse as auto_reuse_agent
from ..agent_context import candidates as reuse_candidates
from ..agent_context import complete_task as complete_agent_task
from ..agent_context import read as read_agent_context
from ..agent_context import request_reuse as reuse_agent
from ..config import Settings


def handle_agent_command(settings: Settings, args: argparse.Namespace) -> Any:
    """Execute one parsed reusable-agent context command."""
    if args.agent_command == "context":
        return read_agent_context(settings, args.session_id)
    if args.agent_command == "task-complete":
        return complete_agent_task(
            settings,
            args.session_id,
            actor=args.actor,
            summary=args.summary,
            tags=args.tag,
            files=args.file,
            terminal=not getattr(args, "keep_alive", False),
        )
    if args.agent_command == "candidates":
        return reuse_candidates(
            settings,
            workdir=args.workdir,
            ticket_id=args.ticket,
            pack_id=args.pack,
            retry_of=args.retry_of,
            agent_class=args.agent_class,
            tags=args.tag,
        )
    if args.agent_command == "reuse":
        return reuse_agent(
            settings,
            args.session_id,
            prompt_path=args.prompt,
            actor=args.actor,
            ticket_id=args.ticket,
            pack_id=args.pack,
            retry_of=args.retry_of,
            tags=args.tag,
        )
    return auto_reuse_agent(
        settings,
        workdir=args.workdir,
        prompt_path=args.prompt,
        actor=args.actor,
        ticket_id=args.ticket,
        pack_id=args.pack,
        retry_of=args.retry_of,
        agent_class=args.agent_class,
        tags=args.tag,
    )
