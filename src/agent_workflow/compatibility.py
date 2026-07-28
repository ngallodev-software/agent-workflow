"""Versioned executor compatibility policy and bounded capability probes."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .process import EnvironmentPolicy, run


COMPATIBILITY_SCHEMA = "agent-workflow/executor-compatibility/v1"


def _policy() -> dict[str, Any]:
    try:
        value = json.loads(
            files("agent_workflow")
            .joinpath("assets", "compatibility", "executors-v1.json")
            .read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError("executor compatibility policy is unavailable") from exc
    if not isinstance(value, dict) or value.get("schema") != COMPATIBILITY_SCHEMA:
        raise WorkflowError("executor compatibility policy has an unsupported schema")
    return value


def compatibility_policy_digest() -> str:
    import hashlib

    data = (
        files("agent_workflow")
        .joinpath("assets", "compatibility", "executors-v1.json")
        .read_bytes()
    )
    return hashlib.sha256(data).hexdigest()


def probe_executor(
    name: str | None,
    command: list[str] | tuple[str, ...],
    *,
    digest: bool = True,
) -> dict[str, Any]:
    """Probe the exact resolved executable used by launch or doctor."""
    if not command:
        return {
            "schema": COMPATIBILITY_SCHEMA,
            "decision": "unsupported",
            "explanation_code": "COMPAT-EMPTY-COMMAND",
        }
    executable = Path(command[0]).name.lower()
    from .process import executable_identity

    identity = executable_identity(command, probe_version=True, digest=digest)
    result: dict[str, Any] = {
        "schema": COMPATIBILITY_SCHEMA,
        "policy_version": _policy().get("version"),
        "policy_sha256": compatibility_policy_digest(),
        "executor": name,
        "executable": identity.as_dict(),
        "capabilities": [],
        "decision": "unclassified",
        "explanation_code": "COMPAT-CUSTOM-EXECUTOR",
    }
    if identity.resolved_path is None:
        result.update(decision="unsupported", explanation_code="COMPAT-EXECUTABLE-NOT-FOUND")
        return result
    entries = _policy().get("executors", {})
    entry = entries.get(executable) if isinstance(entries, dict) else None
    if not isinstance(entry, dict):
        return result
    result["adapter_version"] = entry.get("adapter_version")
    result["expected_capabilities"] = list(entry.get("capabilities", []))
    help_argv = [identity.resolved_path, *entry.get("help_argv", ["--help"])]
    help_result = run(
        help_argv,
        check=False,
        timeout_seconds=10,
        max_stdout_bytes=256 * 1024,
        max_stderr_bytes=256 * 1024,
        environment=EnvironmentPolicy(),
    )
    help_text = str(help_result.stdout) + str(help_result.stderr)
    capabilities = [
        capability
        for capability, marker in entry.get("capability_markers", {}).items()
        if marker in help_text
    ]
    result["capabilities"] = capabilities
    expected = set(entry.get("capabilities", []))
    if identity.version is None:
        result.update(decision="unsupported", explanation_code="COMPAT-VERSION-PROBE-FAILED")
    elif not expected.issubset(capabilities):
        result.update(decision="unsupported", explanation_code="COMPAT-CAPABILITY-MISSING")
    else:
        result.update(decision="supported", explanation_code="COMPAT-SUPPORTED")
    return result
