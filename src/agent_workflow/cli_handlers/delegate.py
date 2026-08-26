"""Dispatch for the deterministic delegation fast path."""

from __future__ import annotations

import argparse
from typing import Any

from ..config import Settings
from ..delegation import delegate


def handle_delegate_command(settings: Settings, args: argparse.Namespace) -> Any:
    return delegate(
        settings,
        agent_run_id=args.agent_run_id,
        prompt_path=args.prompt,
        repo=args.repo,
        workdir=args.workdir,
        ticket_id=args.ticket,
        base_ref=args.base_ref,
        destination=args.dest,
        branch=args.branch,
        role=args.role,
        executor=args.executor,
        agent_name=args.agent_name,
        agent_class=args.agent_class,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        allow_no_go_model=args.allow_no_go_model,
        pack_id=args.pack,
        job_path=args.job,
        prerequisites=args.prerequisites,
        evaluation_path=args.evaluation,
        tier=args.tier,
        structured=args.structured,
        interactive=args.interactive,
        allow_dirty=args.allow_dirty,
        worker_mode=args.worker_mode,
    )
