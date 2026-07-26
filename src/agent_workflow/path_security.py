"""Component-wise no-follow filesystem helpers for bounded readers."""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path

from .errors import WorkflowError


def _absolute_lexical(path: Path) -> Path:
    expanded = Path(os.path.expanduser(os.fspath(path)))
    if ".." in expanded.parts:
        raise WorkflowError("path contains forbidden traversal")
    value = Path(os.path.abspath(os.fspath(expanded)))
    if not value.is_absolute() or any(part == ".." for part in value.parts):
        raise WorkflowError("path contains forbidden traversal")
    return value


def _relative_parts(value: str | os.PathLike[str]) -> tuple[str, ...]:
    path = Path(value)
    if path.is_absolute():
        raise WorkflowError("relative path required")
    parts = path.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise WorkflowError("path contains forbidden traversal")
    return parts


def _open_directory(path: Path) -> int:
    """Open every component of an absolute path without following symlinks."""
    absolute = _absolute_lexical(path)
    descriptor = os.open(os.sep, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        for component in absolute.parts[1:]:
            next_descriptor = os.open(
                component,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        info = os.fstat(descriptor)
        if not stat.S_ISDIR(info.st_mode):
            raise WorkflowError("configured root must be a directory")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def open_relative(parent_fd: int, relative: str | os.PathLike[str], *, flags: int) -> int:
    """Open a relative path below an already opened directory descriptor."""
    parts = _relative_parts(relative)
    current = os.dup(parent_fd)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        for component in parts[:-1]:
            next_descriptor = os.open(component, directory_flags, dir_fd=current)
            os.close(current)
            current = next_descriptor
        return os.open(
            parts[-1],
            flags | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=current,
        )
    finally:
        os.close(current)


def open_beneath(root: Path, relative: str | os.PathLike[str], *, flags: int) -> int:
    """Open a path beneath *root* with no symlink-following components."""
    root_fd = _open_directory(root)
    try:
        return open_relative(root_fd, relative, flags=flags)
    finally:
        os.close(root_fd)


def validate_directory(path: Path, *, label: str) -> Path:
    """Validate and return an absolute lexical directory path."""
    absolute = _absolute_lexical(path)
    descriptor = _open_directory(absolute)
    os.close(descriptor)
    return absolute


def validate_contained(root: Path, value: str | os.PathLike[str], *, label: str) -> Path:
    """Validate a path beneath *root* without resolving or following components."""
    root_absolute = validate_directory(root, label="configured root")
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        candidate_absolute = _absolute_lexical(candidate)
    else:
        candidate_absolute = _absolute_lexical(root_absolute / candidate)
    try:
        relative = candidate_absolute.relative_to(root_absolute)
    except ValueError as exc:
        raise WorkflowError(f"{label} escapes configured root") from exc
    if not relative.parts:
        return root_absolute
    root_fd = _open_directory(root_absolute)
    try:
        try:
            descriptor = open_relative(
                root_fd,
                relative,
                flags=os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                raise WorkflowError(f"{label} does not exist") from exc
            raise WorkflowError(f"{label} is unsafe") from exc
        os.close(descriptor)
    finally:
        os.close(root_fd)
    return candidate_absolute
