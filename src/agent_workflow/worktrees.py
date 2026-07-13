from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Settings
from .errors import WorkflowError
from .git import assert_clean, branch_exists, snapshot
from .process import require_command, run
from .util import expand_path, slug, validate_id


def create(
    settings: Settings,
    *,
    repo: Path,
    ticket_id: str,
    base_ref: str,
    destination: Path | None = None,
    branch: str | None = None,
    allow_dirty: bool = False,
) -> dict[str, Any]:
    require_command("git")
    validate_id(ticket_id, "ticket ID")
    repo = expand_path(repo)
    snap = (
        snapshot(repo)
        if allow_dirty or not settings.require_clean_source
        else assert_clean(repo)
    )
    destination = expand_path(
        destination
        or settings.worktree_root / slug(snap.root.name) / slug(ticket_id)
    )
    branch = branch or f"{settings.branch_prefix}{slug(ticket_id)}"
    if destination.exists():
        raise WorkflowError(f"worktree destination already exists: {destination}")
    if branch_exists(snap.root, branch):
        raise WorkflowError(f"branch already exists: {branch}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "git",
            "-C",
            str(snap.root),
            "worktree",
            "add",
            "-b",
            branch,
            str(destination),
            base_ref,
        ]
    )
    created = snapshot(destination)
    return {
        "repository": str(snap.root),
        "destination": str(destination),
        "branch": branch,
        "base_ref": base_ref,
        "base_revision": snap.head,
        "worktree_revision": created.head,
    }


def remove(
    repo: Path,
    worktree: Path,
    *,
    force: bool = False,
    delete_branch: bool = False,
) -> dict[str, Any]:
    require_command("git")
    repo = expand_path(repo)
    worktree = expand_path(worktree)
    branch = None
    if worktree.exists():
        try:
            branch = snapshot(worktree).branch
        except WorkflowError:
            branch = None
    args = ["git", "-C", str(repo), "worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(worktree))
    run(args)
    deleted = False
    if delete_branch and branch and branch != "(detached)":
        result = run(
            ["git", "-C", str(repo), "branch", "-d", branch],
            check=False,
        )
        if result.returncode and force:
            run(["git", "-C", str(repo), "branch", "-D", branch])
        elif result.returncode:
            raise WorkflowError(
                result.stderr.strip() or f"could not delete branch {branch}"
            )
        deleted = True
    return {
        "removed": str(worktree),
        "branch": branch,
        "branch_deleted": deleted,
    }


def list_worktrees(repo: Path) -> list[dict[str, str]]:
    require_command("git")
    repo = expand_path(repo)
    result = run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"]
    )
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in result.stdout.splitlines() + [""]:
        if not line:
            if current:
                records.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return records
