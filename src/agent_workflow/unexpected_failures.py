"""Durable, schema-shaped diagnostics for unexpected internal failures.

Expected operational errors continue to use :class:`WorkflowError` and remain concise.
This module is only for exceptions that escape the normal command contract.
"""
from __future__ import annotations

import os
import re
import subprocess
import traceback as traceback_module
import uuid
from pathlib import Path
from typing import Any, Iterable, Sequence

from . import __version__
from .runtime.redaction import redact_argv, redact_text, secret_values_from_argv
from .util import atomic_write_json, utc_now

_SCHEMA = "agent-workflow/unexpected-failure/v1"
_MAX_TEXT = 8192
_MAX_CAPTURE = 16384
_MAX_CHAIN = 8
_MAX_FRAMES = 64

# Defense in depth for values that were not present in argv, such as provider
# diagnostics copied into subprocess stderr. Keep this deliberately narrow so
# useful paths and ordinary exception text remain visible.
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(token|password|passwd|secret|api[-_]?key|credential|authorization)\b"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)


def _bounded(value: str, limit: int = _MAX_TEXT) -> str:
    if len(value) <= limit:
        return value
    omitted = len(value) - limit
    return value[:limit] + f"<truncated:{omitted}>"


def _safe_text(value: object, secrets: Iterable[str], limit: int = _MAX_TEXT) -> str:
    text = redact_text(str(value), secrets)
    text = _SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", text)
    text = _BEARER.sub("Bearer <redacted>", text)
    text = _PRIVATE_KEY.sub("<redacted-private-key>", text)
    return _bounded(text, limit)


def _exception_details(exc: BaseException, secrets: tuple[str, ...]) -> dict[str, Any]:
    details: dict[str, Any] = {}
    if isinstance(exc, OSError):
        for name in ("errno", "winerror"):
            value = getattr(exc, name, None)
            if isinstance(value, int):
                details[name] = value
        for name in ("strerror", "filename", "filename2"):
            value = getattr(exc, name, None)
            if value is not None:
                details[name] = _safe_text(value, secrets)
    if isinstance(exc, subprocess.CalledProcessError):
        details["returncode"] = int(exc.returncode)
        details["command"] = _safe_text(exc.cmd, secrets)
        if exc.stdout is not None:
            details["stdout"] = _safe_text(exc.stdout, secrets, _MAX_CAPTURE)
        if exc.stderr is not None:
            details["stderr"] = _safe_text(exc.stderr, secrets, _MAX_CAPTURE)
    elif isinstance(exc, subprocess.TimeoutExpired):
        details["timeout_seconds"] = float(exc.timeout)
        details["command"] = _safe_text(exc.cmd, secrets)
        if exc.stdout is not None:
            details["stdout"] = _safe_text(exc.stdout, secrets, _MAX_CAPTURE)
        if exc.stderr is not None:
            details["stderr"] = _safe_text(exc.stderr, secrets, _MAX_CAPTURE)
    return details


def _exception_chain(exc: BaseException, secrets: tuple[str, ...]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[int] = set()
    current = exc.__cause__ or exc.__context__
    while current is not None and len(result) < _MAX_CHAIN and id(current) not in seen:
        seen.add(id(current))
        result.append(
            {
                "type": type(current).__name__,
                "module": type(current).__module__,
                "message": _safe_text(current, secrets),
            }
        )
        current = current.__cause__ or current.__context__
    return result


def _frames(exc: BaseException, secrets: tuple[str, ...]) -> list[dict[str, Any]]:
    extracted = traceback_module.extract_tb(exc.__traceback__)[-_MAX_FRAMES:]
    return [
        {
            "path": _safe_text(frame.filename, secrets, 4096),
            "line": max(1, int(frame.lineno)),
            "function": _safe_text(frame.name, secrets, 512),
        }
        for frame in extracted
    ]


def _fallback_state_root() -> Path:
    root = Path(os.path.expandvars(os.path.expanduser(os.environ.get("XDG_STATE_HOME", "~/.local/state"))))
    return root.resolve() / "agent-workflow"


def record_unexpected_failure(
    exc: BaseException,
    *,
    settings: object | None,
    argv: Sequence[str],
    top_level: str | None,
) -> dict[str, str]:
    """Persist one bounded local diagnostic and return its public locator.

    The caller should expose only ``correlation_id`` and ``path`` to the terminal.
    No environment variables, locals, prompt bodies, or arbitrary file contents are
    captured. Subprocess output is included only when the exception itself carries it.
    """
    correlation_id = uuid.uuid4().hex
    secrets = secret_values_from_argv(tuple(argv))
    redacted_argv = list(redact_argv(tuple(argv), secret_values=secrets))[:256]
    state_root = getattr(settings, "state_root", None)
    if not isinstance(state_root, Path):
        state_root = _fallback_state_root()
    directory = state_root / "diagnostics" / "unexpected"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        directory.chmod(0o700)
    except OSError:
        pass
    path = directory / f"{correlation_id}.json"
    record: dict[str, Any] = {
        "schema": _SCHEMA,
        "correlation_id": correlation_id,
        "recorded_at": utc_now(),
        "host_version": __version__,
        "command": {
            "argv": [_safe_text(item, secrets, 4096) for item in redacted_argv],
            "cwd": _safe_text(Path.cwd(), secrets, 4096),
            "top_level": _safe_text(top_level, secrets, 128) if top_level else None,
        },
        "exception": {
            "type": type(exc).__name__,
            "module": type(exc).__module__,
            "message": _safe_text(exc, secrets),
            "chain": _exception_chain(exc, secrets),
            "details": _exception_details(exc, secrets),
        },
        "traceback": _frames(exc, secrets),
    }
    # Validate the fixed builder when the schema registry is healthy. Diagnostic
    # capture remains best-effort: a broken schema registry must not erase the
    # only evidence for the underlying crash.
    try:
        from .contracts import validate_instance

        validate_instance(record, _SCHEMA, artifact=str(path))
    except Exception:
        pass
    atomic_write_json(path, record, mode=0o600)
    return {"correlation_id": correlation_id, "path": str(path)}
