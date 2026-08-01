from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Mapping

from ..errors import WorkflowError
from ..process import EnvironmentPolicy, run
from ..util import utc_now

SUBSCRIPTION_MODE = "subscription-session"
API_KEY_MODE = "api-key"
ACCESS_TOKEN_MODE = "access-token"
SYNTHETIC_MODE = "synthetic-none"


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _classify_status(provider: str, output: str) -> str | None:
    lowered = output.lower()
    if provider == "openai":
        if "chatgpt" in lowered or "oauth" in lowered:
            return SUBSCRIPTION_MODE
        if "api key" in lowered or "api-key" in lowered:
            return API_KEY_MODE
        if "access token" in lowered:
            return ACCESS_TOKEN_MODE
    if provider == "anthropic":
        try:
            value = json.loads(output)
        except json.JSONDecodeError:
            value = None
        flattened = lowered
        if isinstance(value, dict):
            flattened = json.dumps(value, sort_keys=True).lower()
        if "claude.ai" in flattened or re.search(
            r"\b(subscription|oauth|pro|max|team|enterprise)\b", flattened
        ):
            return SUBSCRIPTION_MODE
        if "anthropic_api_key" in flattened or re.search(
            r"\b(api|console|api[-_ ]?key)\b", flattened
        ):
            return API_KEY_MODE
    return None


def validate_authentication_config(executor: Mapping[str, Any]) -> None:
    authentication = executor.get("authentication")
    if not isinstance(authentication, Mapping):
        raise WorkflowError("benchmark executor requires an authentication policy")
    mode = authentication.get("mode")
    if mode not in {SUBSCRIPTION_MODE, API_KEY_MODE, ACCESS_TOKEN_MODE, SYNTHETIC_MODE}:
        raise WorkflowError(f"unsupported benchmark authentication mode: {mode!r}")
    credential_environment = authentication.get("credential_environment", [])
    if not isinstance(credential_environment, list) or not all(
        isinstance(item, str) and item for item in credential_environment
    ):
        raise WorkflowError("authentication credential_environment must be a string list")
    if mode in {API_KEY_MODE, ACCESS_TOKEN_MODE} and not credential_environment:
        raise WorkflowError(f"{mode} authentication requires credential_environment")
    if mode == SUBSCRIPTION_MODE and authentication.get("allow_api_key_fallback") is True:
        raise WorkflowError(
            "subscription-session benchmark profiles may not silently fall back to API-key billing"
        )


def preflight_authentication(executor: Mapping[str, Any]) -> dict[str, Any]:
    validate_authentication_config(executor)
    authentication = dict(executor["authentication"])
    mode = str(authentication["mode"])
    provider = str(executor["provider"])
    credential_names = [str(item) for item in authentication.get("credential_environment", [])]
    present = sorted(name for name in credential_names if os.environ.get(name))
    forbidden_present = mode == SUBSCRIPTION_MODE and bool(present)

    if mode == SYNTHETIC_MODE:
        return {
            "checked_at": utc_now(),
            "requested_mode": mode,
            "observed_mode": mode,
            "authenticated": True,
            "credential_environment_present": [],
            "status_command": None,
            "status_output_sha256": None,
            "status_returncode": 0,
            "detail": "synthetic executor requires no external authentication",
        }

    if mode in {API_KEY_MODE, ACCESS_TOKEN_MODE}:
        authenticated = bool(present)
        return {
            "checked_at": utc_now(),
            "requested_mode": mode,
            "observed_mode": mode if authenticated else None,
            "authenticated": authenticated,
            "credential_environment_present": present,
            "status_command": None,
            "status_output_sha256": None,
            "status_returncode": 0 if authenticated else 1,
            "detail": (
                f"credential environment present: {', '.join(present)}"
                if authenticated
                else f"none of the configured credential variables are present: {', '.join(credential_names)}"
            ),
        }

    status_argv = authentication.get("status_argv")
    if not isinstance(status_argv, list) or not status_argv:
        raise WorkflowError("subscription-session authentication requires status_argv")
    if forbidden_present:
        return {
            "checked_at": utc_now(),
            "requested_mode": mode,
            "observed_mode": API_KEY_MODE,
            "authenticated": False,
            "credential_environment_present": present,
            "status_command": [str(item) for item in status_argv],
            "status_output_sha256": None,
            "status_returncode": None,
            "detail": (
                "subscription benchmark refused because an API credential environment variable is present: "
                + ", ".join(present)
            ),
        }
    result = run(
        [str(item) for item in status_argv],
        check=False,
        timeout_seconds=float(authentication.get("status_timeout_seconds", 30)),
        max_stdout_bytes=256 * 1024,
        max_stderr_bytes=256 * 1024,
        environment=EnvironmentPolicy(
            allowlist=tuple(str(item) for item in executor.get("environment_allowlist", [])),
            values={},
            unsafe_inherit=False,
        ),
        probe_version=True,
        digest_executable=True,
    )
    output = "\n".join((str(result.stdout), str(result.stderr))).strip()
    observed = _classify_status(provider, output)
    authenticated = result.returncode == 0 and observed == SUBSCRIPTION_MODE
    return {
        "checked_at": utc_now(),
        "requested_mode": mode,
        "observed_mode": observed,
        "authenticated": authenticated,
        "credential_environment_present": present,
        "status_command": list(result.argv),
        "status_output_sha256": _digest_text(output),
        "status_returncode": result.returncode,
        "status_process": result.as_dict(include_output=False),
        "detail": (
            "authenticated subscription session confirmed"
            if authenticated
            else "subscription session was not confirmed; run the provider CLI login flow before benchmarking"
        ),
    }


def require_authentication(executor: Mapping[str, Any]) -> dict[str, Any]:
    evidence = preflight_authentication(executor)
    if not evidence["authenticated"]:
        raise WorkflowError(str(evidence["detail"]))
    return evidence
