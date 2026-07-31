from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

from .config import Settings
from .compatibility import probe_executor
from .process import redact_argv, run, secret_values_from_argv
from .config import trust_report


def _executor_capability(name: str, command: list[str]) -> dict[str, Any]:
    binary = shutil.which(command[0]) if command else None
    value: dict[str, Any] = {
        "configured_argv": list(
            redact_argv(command, secret_values=secret_values_from_argv(command))
        ),
        "binary": binary,
        "installed": bool(binary),
        "version": None,
        "structured_output": False,
        "probe_error": None,
    }
    if not binary:
        return value
    compatibility = probe_executor(
        name,
        [binary, *command[1:]],
        digest=True,
    )
    identity = compatibility.get("executable") or {}
    value["binary"] = identity.get("resolved_path", binary)
    value["version"] = identity.get("version")
    value["sha256"] = identity.get("sha256")
    value["structured_output"] = "structured_output" in compatibility.get("capabilities", [])
    value["adapter_version"] = compatibility.get("adapter_version")
    value["compatibility"] = compatibility
    if compatibility.get("decision") != "supported":
        value["probe_error"] = compatibility.get("explanation_code")
    return value


def _archive_commands_supported(commands: dict[str, str | None]) -> bool:
    tar = commands.get("tar")
    if not tar or not commands.get("zstd"):
        return False
    result = run(
        [tar, "--help"],
        check=False,
        timeout_seconds=10,
        max_stdout_bytes=256 * 1024,
        max_stderr_bytes=256 * 1024,
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
    security = trust_report(settings)
    executors = {
        name: _executor_capability(name, command)
        for name, command in sorted(settings.executors.items())
    }
    compatibility_ok = settings.security.mode == "local" or all(
        item.get("installed") is True
        and item.get("compatibility", {}).get("decision") == "supported"
        for item in executors.values()
    )
    checks = {
        "python_3_11_or_newer": sys.version_info >= (3, 11),
        "terminal_backend_supported": settings.terminal_backend == "tmux",
        "state_parent_writable": _parent_writable(settings.state_root),
        "worktree_parent_writable": _parent_writable(settings.worktree_root),
        "required_commands_present": all(
            commands[name] for name in ("git", "tmux", "bash", "python3")
        ),
        "trusted_policy_inputs": security["ok"],
        "executor_compatibility": compatibility_ok,
    }
    return {
        "ok": all(checks.values()),
        "version": "0.7.0",
        "config_path": str(settings.config_path),
        "commands": commands,
        "executors": executors,
        "checks": checks,
        "security": security,
        "archive_ready": _archive_commands_supported(commands),
        "state_root": str(settings.state_root),
        "worktree_root": str(settings.worktree_root),
    }
