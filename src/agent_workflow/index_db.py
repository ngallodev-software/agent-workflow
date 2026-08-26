"""SQLite index storage boundary.

Owns the disposable projection database location, safe connection policy, and
single-writer lock.  Projection ingestion/query semantics remain in
``index_store``; schema DDL remains in ``index_schema``.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import sqlite3
import stat
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

from .config import Settings, enforce_trust
from .errors import WorkflowError
from .path import require_directory
from .state import runs_root


def index_root(settings: Settings) -> Path:
    enforce_trust(settings)
    runs_root(settings)
    root = settings.state_root / "index"
    if root.exists() or root.is_symlink():
        if root.is_symlink() or not root.is_dir():
            raise WorkflowError(f"index root is unsafe: {root}")
    else:
        root.mkdir(mode=0o700)
    require_directory(root, label="index root")
    return root


def database_path(settings: Settings) -> Path:
    return index_root(settings) / "agent-workflow.sqlite3"


def integrity_authority_path(settings: Settings) -> Path:
    return index_root(settings) / "integrity-authority-v2.jsonl"


@contextlib.contextmanager
def writer_lock(settings: Settings) -> Iterator[None]:
    path = index_root(settings) / "index.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise WorkflowError(f"cannot open index lock {path}: {exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError(f"index lock must be a regular file: {path}")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def connect(settings: Settings, *, readonly: bool = False) -> sqlite3.Connection:
    path = database_path(settings)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise WorkflowError(f"SQLite index path is unsafe: {path}")
    elif readonly:
        raise WorkflowError("SQLite index does not exist; run: agent-workflow index rebuild")
    mode = "ro" if readonly else "rwc"
    uri_path = quote(str(path), safe="/")
    try:
        connection = sqlite3.connect(
            f"file:{uri_path}?mode={mode}&nofollow=1", uri=True, timeout=5.0
        )
    except sqlite3.Error as exc:
        raise WorkflowError(f"cannot open SQLite index {path}: {exc}") from exc
    if not readonly:
        try:
            os.chmod(path, 0o600)
        except OSError:
            connection.close()
            raise
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    if not readonly:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
    return connection
