from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

from .config import Settings


def _parent_writable(path: Path) -> bool:
    candidate = path
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return (
        candidate.exists()
        and candidate.is_dir()
        and os.access(candidate, os.W_OK | os.X_OK)
    )


def run_doctor(settings: Settings) -> dict[str, Any]:
    commands = {
        name: shutil.which(name)
        for name in ("git", "tmux", "bash", "tar", "zstd", "python3")
    }
    checks = {
        "python_3_11_or_newer": sys.version_info >= (3, 11),
        "terminal_backend_supported": settings.terminal_backend == "tmux",
        "state_parent_writable": _parent_writable(settings.state_root),
        "worktree_parent_writable": _parent_writable(settings.worktree_root),
        "required_commands_present": all(
            commands[name] for name in ("git", "tmux", "bash", "python3")
        ),
    }
    return {
        "ok": all(checks.values()),
        "version": "0.1.0",
        "config_path": str(settings.config_path),
        "commands": commands,
        "checks": checks,
        "archive_ready": bool(commands["tar"] and commands["zstd"]),
        "state_root": str(settings.state_root),
        "worktree_root": str(settings.worktree_root),
    }
