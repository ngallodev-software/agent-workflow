from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable

from .errors import WorkflowError


def require_command(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise WorkflowError(f"required command not found on PATH: {name}")
    return path


def run(
    args: Iterable[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [str(item) for item in args]
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise WorkflowError(f"failed to run {command[0]!r}: {exc}") from exc
    if check and result.returncode:
        detail = (result.stderr or result.stdout or "").strip()
        raise WorkflowError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{detail}"
        )
    return result


def run_bytes(
    args: Iterable[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    command = [str(item) for item in args]
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise WorkflowError(f"failed to run {command[0]!r}: {exc}") from exc
    if check and result.returncode:
        detail = (result.stderr or result.stdout or b"").decode(
            "utf-8", errors="replace"
        ).strip()
        raise WorkflowError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{detail}"
        )
    return result
