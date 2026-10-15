"""Dispatch for the ``agent-workflow worktree`` command domain."""

from __future__ import annotations

import argparse
from typing import Any

from ..config import Settings
from ..worktrees import create as create_worktree
from ..worktrees import list_worktrees
from ..worktrees import remove as remove_worktree
from ..repository_closeout import create_repository_closeout, verify_repository_closeout
from ..task_integration import integrate as integrate_task_runs, verify_integration


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
    if args.worktree_command == "closeout":
        return create_repository_closeout(
            args.repo,
            output=args.output,
            baseline_revision=args.baseline_revision,
            remote=args.remote,
            fetch=args.fetch,
            push=args.push,
            push_branch=args.push_branch,
            set_upstream=args.set_upstream,
            integration_branch=args.integration_branch,
            operational_trees=args.operational_tree,
            disposable_trees=args.disposable_tree,
        )
    if args.worktree_command == "closeout-verify":
        return verify_repository_closeout(args.receipt)
    if args.worktree_command == "integrate":
        return integrate_task_runs(
            settings, args.repo, run_ids=args.run, commands_file=args.commands,
            dest=args.dest, output=args.output, actor=args.actor, reason=args.reason,
        )
    if args.worktree_command == "integration-verify":
        return verify_integration(args.evidence_dir)
    return list_worktrees(args.repo)
