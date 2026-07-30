from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .errors import WorkflowError
from .process import EnvironmentPolicy, require_command, run
from .util import expand_path


@dataclass(frozen=True)
class GitSnapshot:
    root: Path
    head: str
    branch: str
    dirty: bool


def snapshot(path: Path) -> GitSnapshot:
    require_command("git")
    path = expand_path(path)
    root = Path(
        run(["git", "-C", str(path), "rev-parse", "--show-toplevel"]).stdout.strip()
    ).resolve()
    head = run(["git", "-C", str(root), "rev-parse", "HEAD"]).stdout.strip()
    branch = (
        run(["git", "-C", str(root), "branch", "--show-current"]).stdout.strip()
        or "(detached)"
    )
    # Match the operator's normal Git cleanliness view, including their
    # configured excludes file.  A controlled Git environment treats harmless
    # editor state (for example .claude/) as untracked source changes.
    dirty = bool(
        run(
            ["git", "-C", str(root), "status", "--porcelain"],
            environment=EnvironmentPolicy(unsafe_inherit=True),
        ).stdout.strip()
    )
    return GitSnapshot(root, head, branch, dirty)


def assert_clean(repo: Path) -> GitSnapshot:
    snap = snapshot(repo)
    if snap.dirty:
        raise WorkflowError(
            f"source repository is dirty: {snap.root}; commit/stash or use --allow-dirty"
        )
    return snap


def branch_exists(repo: Path, branch: str) -> bool:
    return (
        run(
            [
                "git",
                "-C",
                str(repo),
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}",
            ],
            check=False,
        ).returncode
        == 0
    )
