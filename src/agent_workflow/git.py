from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .process import EnvironmentPolicy, ProcessResult, require_command, run
from .util import expand_path


@dataclass(frozen=True)
class GitSnapshot:
    root: Path
    head: str
    branch: str
    dirty: bool
    cleanliness: dict[str, Any] = field(default_factory=dict)

    def cleanliness_evidence(self) -> dict[str, Any]:
        return dict(self.cleanliness)


def _digest_output(value: str | bytes) -> str:
    data = value.encode("utf-8", errors="surrogatepass") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def _cleanliness_evidence(result: ProcessResult) -> dict[str, Any]:
    return {
        "schema": "agent-workflow/git-cleanliness-evidence/v1",
        "argv": list(result.argv),
        "resolved_executable": result.resolved_executable,
        "returncode": result.returncode,
        "stdout_sha256": _digest_output(result.stdout),
        "stdout_bytes": result.stdout_bytes,
        "stderr_sha256": _digest_output(result.stderr),
        "stderr_bytes": result.stderr_bytes,
        "environment_policy": result.environment_policy,
        "duration_seconds": result.duration_seconds,
    }


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
    # Cleanliness is a fresh exact-root command and intentionally matches the
    # operator's normal Git view, including configured global excludes. The
    # command itself remains bounded and non-interactive, and its provenance is
    # retained without persisting potentially sensitive status output.
    status = run(
        ["git", "-C", str(root), "status", "--porcelain"],
        environment=EnvironmentPolicy(
            unsafe_inherit=True,
            git_config_policy="operator",
        ),
    )
    dirty = bool(status.stdout.strip())
    return GitSnapshot(root, head, branch, dirty, _cleanliness_evidence(status))


def administrative_dir(path: Path) -> Path:
    """Return the resolved Git administrative directory for ``path``."""
    path = expand_path(path)
    result = run(["git", "-C", str(path), "rev-parse", "--absolute-git-dir"])
    return Path(result.stdout.strip()).resolve()


def assert_clean(repo: Path) -> GitSnapshot:
    snap = snapshot(repo)
    if snap.dirty:
        command = " ".join(str(value) for value in snap.cleanliness.get("argv", []))
        raise WorkflowError(
            f"source repository is dirty: {snap.root}; verified by {command}; "
            "commit/stash, or use --allow-dirty to create the requested clean "
            "worktree from the immutable base revision"
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
