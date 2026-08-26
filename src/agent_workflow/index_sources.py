"""Safe source discovery and stable evidence reads for the SQLite projection."""

from __future__ import annotations

import fcntl
import hashlib
import os
import stat
from pathlib import Path

from .config import Settings
from .errors import WorkflowError
from .state import runs_root
from .util import validate_id

MAX_INDEXED_FILE_BYTES = 64 * 1024 * 1024
JSON_ARTIFACT_SUFFIXES = {".json", ".jsonl"}
TEXT_METADATA_SUFFIXES: set[str] = set()
IGNORED_FILENAMES = {"workflow.lock", "supervisor.lock", "index.lock"}


def read_stable_bytes(path: Path, *, shared_lock: bool = False) -> bytes:
    """Read one no-follow regular file from a stable descriptor."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WorkflowError(f"cannot open indexed artifact {path}: {exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError(f"indexed artifact must be a regular file: {path}")
        if info.st_size > MAX_INDEXED_FILE_BYTES:
            raise WorkflowError(f"artifact exceeds index safety limit: {path}")
        if shared_lock:
            fcntl.flock(descriptor, fcntl.LOCK_SH)
        try:
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            if shared_lock:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def sha256_file(path: Path) -> str:
    """Hash the exact stable bytes used by the projection."""
    data = read_stable_bytes(path, shared_lock=path.suffix.lower() == ".jsonl")
    return hashlib.sha256(data).hexdigest()


def run_roots(settings: Settings, *, include_archived: bool) -> list[tuple[str, Path]]:
    """Return authoritative active and optional archive source roots."""
    roots = [("active", runs_root(settings))]
    if include_archived:
        archive = settings.state_root / "archive"
        if archive.exists() or archive.is_symlink():
            if archive.is_symlink() or not archive.is_dir():
                raise WorkflowError(f"archive root is unsafe: {archive}")
            roots.append(("archive", archive))
    return roots


def discover_runs(
    settings: Settings,
    *,
    include_archived: bool,
    agent_run_id: str | None,
) -> list[tuple[str, str, Path]]:
    """Discover valid run directories with active state winning duplicates."""
    if agent_run_id is not None:
        validate_id(agent_run_id, "agent run ID")
    discovered: dict[str, tuple[str, str, Path]] = {}
    for storage_class, root in run_roots(settings, include_archived=include_archived):
        for path in sorted(root.iterdir() if root.is_dir() else []):
            if agent_run_id is not None and path.name != agent_run_id:
                continue
            if path.is_symlink() or not path.is_dir():
                continue
            validate_id(path.name, "agent run ID")
            candidate = (path.name, storage_class, path)
            if path.name not in discovered or storage_class == "active":
                discovered[path.name] = candidate
    return [discovered[key] for key in sorted(discovered)]


def artifact_paths(run_dir: Path) -> list[Path]:
    """Enumerate regular indexable artifacts below one run directory."""
    paths: list[Path] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_symlink() or not path.is_file() or path.name in IGNORED_FILENAMES:
            continue
        if path.suffix.lower() in JSON_ARTIFACT_SUFFIXES | TEXT_METADATA_SUFFIXES:
            paths.append(path)
    return paths


def unsafe_artifact_paths(run_dir: Path) -> list[Path]:
    """Return indexable symlinks without following their targets."""
    return [
        path
        for path in sorted(run_dir.rglob("*"))
        if path.is_symlink()
        and path.name not in IGNORED_FILENAMES
        and path.suffix.lower() in JSON_ARTIFACT_SUFFIXES | TEXT_METADATA_SUFFIXES
    ]


def source_fingerprint(run_dir: Path) -> str:
    """Fingerprint source identity and metadata without trusting path names alone."""
    digest = hashlib.sha256()
    for path in sorted(artifact_paths(run_dir) + unsafe_artifact_paths(run_dir)):
        info = path.lstat()
        relative = path.relative_to(run_dir).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(info.st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(info.st_mtime_ns).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(info.st_ctime_ns).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(info.st_dev).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(info.st_ino).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(stat.S_IMODE(info.st_mode)).encode("ascii"))
        if stat.S_ISLNK(info.st_mode):
            digest.update(b"\0symlink\0")
            digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
        digest.update(b"\n")
    return digest.hexdigest()
