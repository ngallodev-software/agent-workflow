from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .config import Settings


def _executor_capability(name: str, command: list[str]) -> dict[str, Any]:
    binary = shutil.which(command[0]) if command else None
    value: dict[str, Any] = {
        "configured_argv": command,
        "binary": binary,
        "installed": bool(binary),
        "version": None,
        "structured_output": False,
        "probe_error": None,
    }
    if not binary:
        return value
    version = subprocess.run(
        [binary, "--version"], capture_output=True, text=True, check=False
    )
    if version.returncode == 0:
        value["version"] = (version.stdout or version.stderr).strip()
    else:
        value["probe_error"] = (version.stderr or version.stdout).strip()
    help_argv = [binary, "exec", "--help"] if name == "codex" else [binary, "--help"]
    help_result = subprocess.run(
        help_argv, capture_output=True, text=True, check=False
    )
    help_text = help_result.stdout + help_result.stderr
    expected = "--json" if name == "codex" else "--output-format"
    value["structured_output"] = help_result.returncode == 0 and expected in help_text
    return value


def _archive_commands_supported(commands: dict[str, str | None]) -> bool:
    tar = commands.get("tar")
    if not tar or not commands.get("zstd"):
        return False
    result = subprocess.run(
        [tar, "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    help_text = result.stdout + result.stderr
    return result.returncode == 0 and all(
        option in help_text
        for option in ("--sort", "--mtime", "--owner", "--group", "--numeric-owner")
    )


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
        "version": "0.1.6",
        "config_path": str(settings.config_path),
        "commands": commands,
        "executors": {
            name: _executor_capability(name, command)
            for name, command in sorted(settings.executors.items())
        },
        "checks": checks,
        "archive_ready": _archive_commands_supported(commands),
        "state_root": str(settings.state_root),
        "worktree_root": str(settings.worktree_root),
    }
