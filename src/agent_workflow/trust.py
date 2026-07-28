"""Filesystem trust checks for executable policy inputs."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .errors import WorkflowError
from .path import absolute_path


@dataclass(frozen=True)
class PathTrust:
    label: str
    path: Path
    exists: bool
    checked_path: Path
    owner_ok: bool | None
    group_world_writable: bool | None
    no_follow: bool
    mode: str | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return bool(
            self.error is None
            and self.no_follow
            and (self.owner_ok is not False)
            and (self.group_world_writable is not True)
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "path": str(self.path),
            "exists": self.exists,
            "checked_path": str(self.checked_path),
            "owner_ok": self.owner_ok,
            "group_world_writable": self.group_world_writable,
            "no_follow": self.no_follow,
            "mode": self.mode,
            "error": self.error,
            "ok": self.ok,
        }


def inspect_path(path: Path, *, label: str, allow_missing: bool = True) -> PathTrust:
    """Inspect one path with lstat, checking the nearest creator for missing dirs."""
    lexical = absolute_path(path)
    candidate = lexical
    try:
        info = candidate.lstat()
        checked = candidate
        exists = True
    except FileNotFoundError:
        if not allow_missing:
            return PathTrust(label, lexical, False, lexical, None, None, False, None, "missing")
        while True:
            try:
                info = candidate.lstat()
                checked = candidate
                exists = False
                break
            except FileNotFoundError:
                if candidate.parent == candidate:
                    return PathTrust(label, lexical, False, candidate, None, None, False, None, "missing")
                candidate = candidate.parent
    except OSError as exc:
        return PathTrust(label, lexical, False, lexical, None, None, False, None, str(exc))

    mode = stat.S_IMODE(info.st_mode)
    no_follow = not stat.S_ISLNK(info.st_mode)
    owner_ok = info.st_uid == os.getuid() if hasattr(os, "getuid") else True
    writable = bool(mode & 0o022)
    error = None
    if stat.S_ISLNK(info.st_mode):
        error = "symlink"
    elif not stat.S_ISDIR(info.st_mode) and not stat.S_ISREG(info.st_mode):
        error = "not a regular file or directory"
    return PathTrust(
        label,
        lexical,
        exists,
        checked,
        owner_ok,
        writable,
        no_follow,
        f"{mode:04o}",
        error,
    )


def require_trusted(
    report: PathTrust,
    *,
    mode: str,
    missing_is_error: bool = False,
) -> None:
    """Raise one stable remediation error for governed/release policy inputs."""
    if mode == "local":
        return
    problems: list[str] = []
    if report.error and (report.exists or missing_is_error):
        problems.append(report.error)
    if report.owner_ok is False:
        problems.append("owner")
    if report.group_world_writable is True:
        problems.append("group/world-writable")
    if not problems:
        return
    raise WorkflowError(
        f"untrusted {report.label}: {report.path} ({', '.join(problems)}); "
        "remediation: make the path user-owned, remove group/world write bits, "
        "and replace symlinks with regular trusted paths"
    )
