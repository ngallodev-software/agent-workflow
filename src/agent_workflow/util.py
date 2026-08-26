from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import WorkflowError

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_id(value: str, label: str = "identifier") -> str:
    if not SAFE_ID.fullmatch(value):
        raise WorkflowError(
            f"invalid {label}: {value!r}; use letters, digits, '.', '_' or '-'"
        )
    return value


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not result:
        raise WorkflowError(f"cannot derive slug from {value!r}")
    return result[:96]


def expand_path(value: str | Path) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(str(value)))).resolve()


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 hex digest for *data*."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(value: str, *, encoding: str = "utf-8") -> str:
    """Return the SHA-256 digest for text encoded deterministically."""
    return sha256_bytes(value.encode(encoding))


def canonical_json_bytes(
    value: Any,
    *,
    ensure_ascii: bool = True,
    trailing_newline: bool = False,
) -> bytes:
    """Encode a value as compact, key-sorted JSON for hashing/evidence.

    ``ensure_ascii`` is explicit because existing evidence contracts use both
    ASCII-escaped and native UTF-8 canonical forms.  Callers must select the
    form required by their contract rather than reimplementing serialization.
    """
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=ensure_ascii,
    ).encode("utf-8")
    return encoded + (b"\n" if trailing_newline else b"")


def canonical_json_sha256(value: Any, *, ensure_ascii: bool = True) -> str:
    """Return SHA-256 over canonical JSON bytes."""
    return sha256_bytes(canonical_json_bytes(value, ensure_ascii=ensure_ascii))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fsync_directory(path: Path) -> None:
    """Persist directory-entry changes on POSIX filesystems."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_bytes(
    path: Path, data: bytes, *, mode: int | None = None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            if mode is not None:
                os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        fsync_directory(path.parent)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def atomic_write_json(
    path: Path, data: dict[str, Any], *, mode: int | None = None
) -> None:
    encoded = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write_bytes(path, encoded, mode=mode)


def atomic_write_canonical_json(
    path: Path,
    data: Any,
    *,
    mode: int | None = None,
    ensure_ascii: bool = True,
    trailing_newline: bool = True,
) -> None:
    """Atomically persist compact canonical JSON using the shared encoder."""
    atomic_write_bytes(
        path,
        canonical_json_bytes(
            data,
            ensure_ascii=ensure_ascii,
            trailing_newline=trailing_newline,
        ),
        mode=mode,
    )


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"expected JSON object in {path}")
    return value
