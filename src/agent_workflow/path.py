"""Descriptor-safe, no-follow filesystem primitives for trusted inputs."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .errors import WorkflowError

MAX_VALIDATED_FILE_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class RegularFile:
    path: Path
    data: bytes
    size: int
    mode: int
    device: int
    inode: int
    sha256: str


@dataclass(frozen=True)
class TreeEntry:
    path: str
    kind: str
    size: int
    mode: int
    device: int
    inode: int
    sha256: str | None = None


def absolute_path(path: Path) -> Path:
    """Return a lexical absolute path without resolving any component."""
    return path.expanduser() if path.is_absolute() else Path.cwd() / path.expanduser()


def _parts(path: Path) -> tuple[str, ...]:
    path = absolute_path(path)
    parts = tuple(part for part in path.parts if part not in (path.anchor, ""))
    if any(part == ".." for part in parts):
        raise WorkflowError(f"path contains unresolved '..' component: {path}")
    return parts


def _open_directory(path: Path) -> tuple[int, Path]:
    path = absolute_path(path)
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path.anchor or "/", flags)
    try:
        for part in _parts(path):
            next_fd = os.open(
                part,
                flags | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=fd,
            )
            os.close(fd)
            fd = next_fd
    except OSError:
        os.close(fd)
        raise
    return fd, path


def require_directory(path: Path, *, label: str = "directory") -> Path:
    lexical = absolute_path(path)
    try:
        fd, _ = _open_directory(lexical)
    except OSError as exc:
        raise WorkflowError(f"{label} is not a regular directory: {lexical}") from exc
    os.close(fd)
    return lexical


def _read_fd(fd: int, path: Path, *, max_bytes: int) -> RegularFile:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode):
        raise WorkflowError(f"rejected non-regular file: {path}")
    if before.st_nlink != 1:
        raise WorkflowError(f"rejected hard-linked file: {path}")
    if before.st_size > max_bytes:
        raise WorkflowError(f"file exceeds validation limit: {path}")
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, min(1024 * 1024, max_bytes - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise WorkflowError(f"file exceeds validation limit: {path}")
        chunks.append(chunk)
        digest.update(chunk)
    after = os.fstat(fd)
    identity = (before.st_dev, before.st_ino, before.st_mode, before.st_size)
    final_identity = (after.st_dev, after.st_ino, after.st_mode, after.st_size)
    if identity != final_identity or total != after.st_size:
        raise WorkflowError(f"file changed during validation: {path}")
    return RegularFile(
        path=path,
        data=b"".join(chunks),
        size=after.st_size,
        mode=stat.S_IMODE(after.st_mode),
        device=after.st_dev,
        inode=after.st_ino,
        sha256=digest.hexdigest(),
    )


def read_regular_file(path: Path, *, max_bytes: int = MAX_VALIDATED_FILE_BYTES) -> RegularFile:
    """Read one regular file with no-follow traversal for every component."""
    lexical = absolute_path(path)
    parts = _parts(lexical)
    if not parts:
        raise WorkflowError(f"expected regular file, got directory: {lexical}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    directory_fd, _ = _open_directory(lexical.parent)
    try:
        try:
            fd = os.open(parts[-1], flags, dir_fd=directory_fd)
        except OSError as exc:
            raise WorkflowError(f"cannot open regular file without following links: {lexical}") from exc
        try:
            return _read_fd(fd, lexical, max_bytes=max_bytes)
        finally:
            os.close(fd)
    finally:
        os.close(directory_fd)


def _entry_from_stat(path: str, info: os.stat_result, *, digest: str | None = None) -> TreeEntry:
    mode = info.st_mode
    if stat.S_ISREG(mode):
        if info.st_nlink != 1:
            raise WorkflowError(f"rejected hard-linked file: {path}")
        return TreeEntry(path, "file", info.st_size, stat.S_IMODE(mode), info.st_dev, info.st_ino, digest)
    if stat.S_ISDIR(mode):
        return TreeEntry(path, "directory", 0, stat.S_IMODE(mode), info.st_dev, info.st_ino)
    if stat.S_ISLNK(mode):
        raise WorkflowError(f"rejected symlink entry: {path}")
    raise WorkflowError(f"rejected special file entry: {path}")


def inventory_tree(root: Path) -> tuple[TreeEntry, ...]:
    """Inventory a tree while rejecting links, special files, and races."""
    root = require_directory(root, label="tree root")
    entries: list[TreeEntry] = []

    def visit(directory_fd: int, relative: str) -> None:
        try:
            names = sorted(os.listdir(directory_fd))
        except OSError as exc:
            raise WorkflowError(f"cannot enumerate tree entry: {relative or '.'}") from exc
        for name in names:
            child_relative = f"{relative}/{name}" if relative else name
            try:
                info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError as exc:
                raise WorkflowError(f"cannot inspect tree entry: {child_relative}") from exc
            entry = _entry_from_stat(child_relative, info)
            if entry.kind == "directory":
                flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
                try:
                    child_fd = os.open(name, flags, dir_fd=directory_fd)
                    opened = os.fstat(child_fd)
                except OSError as exc:
                    raise WorkflowError(f"directory changed during validation: {child_relative}") from exc
                try:
                    if (opened.st_dev, opened.st_ino, opened.st_mode) != (info.st_dev, info.st_ino, info.st_mode):
                        raise WorkflowError(f"entry changed during validation: {child_relative}")
                    entries.append(entry)
                    visit(child_fd, child_relative)
                finally:
                    os.close(child_fd)
            else:
                flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
                try:
                    fd = os.open(name, flags, dir_fd=directory_fd)
                except OSError as exc:
                    raise WorkflowError(f"entry changed during validation: {child_relative}") from exc
                try:
                    read = _read_fd(fd, Path(child_relative), max_bytes=MAX_VALIDATED_FILE_BYTES)
                    if (read.device, read.inode, read.size, read.mode) != (entry.device, entry.inode, entry.size, entry.mode):
                        raise WorkflowError(f"entry changed during validation: {child_relative}")
                    entries.append(TreeEntry(child_relative, "file", read.size, read.mode, read.device, read.inode, read.sha256))
                finally:
                    os.close(fd)

    root_fd, _ = _open_directory(root)
    try:
        visit(root_fd, "")
    finally:
        os.close(root_fd)
    return tuple(entries)


def read_inventory_file(root: Path, entry: TreeEntry) -> RegularFile:
    """Read an inventoried file and require its identity and digest to match."""
    if entry.kind != "file":
        raise WorkflowError(f"archive inventory entry is not a file: {entry.path}")
    read = read_regular_file(absolute_path(root) / entry.path)
    if (read.device, read.inode, read.size, read.mode, read.sha256) != (
        entry.device, entry.inode, entry.size, entry.mode, entry.sha256
    ):
        raise WorkflowError(f"entry changed after validation: {entry.path}")
    return read
