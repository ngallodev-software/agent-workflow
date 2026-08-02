"""Dispatch for the ``agent-workflow worktree`` command domain."""

from __future__ import annotations

import argparse
from typing import Any

from ..config import Settings
from ..worktrees import create as create_worktree
from ..worktrees import list_worktrees
from ..worktrees import remove as remove_worktree


def handle_worktree_command(
    settings: Settings,
    args: argparse.Namespace,
) -> Any:
    """Execute one parsed worktree command and return its structured result."""
    if args.worktree_command == "create":
        return create_worktree(
            settings,
            repo=args.repo,
            ticket_id=args.ticket_id,
            base_ref=args.base_ref,
            destination=args.dest,
            branch=args.branch,
            allow_dirty=args.allow_dirty,
        )
    if args.worktree_command == "remove":
        return remove_worktree(
            args.repo,
            args.worktree,
            force=args.force,
            delete_branch=args.delete_branch,
        )
    return list_worktrees(args.repo)
