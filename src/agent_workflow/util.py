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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


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
