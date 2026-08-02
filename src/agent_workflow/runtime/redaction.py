"""Deterministic secret detection and redaction for process evidence."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Sequence

_SECRET_OPTION = re.compile(
    r"(?:token|password|passwd|secret|api[-_]?key|auth(?:entication)?|credential|private[-_]?key)",
    re.IGNORECASE,
)


def _secret_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="surrogatepass")).hexdigest()[:16]


def _redaction(value: str) -> str:
    return f"<redacted:{_secret_digest(value)}>"


def redact_text(value: str, secret_values: Iterable[str] = ()) -> str:
    redacted = value
    for secret in sorted({item for item in secret_values if item}, key=len, reverse=True):
        redacted = redacted.replace(secret, _redaction(secret))
    return redacted


def redact_bytes(value: bytes, secret_values: Iterable[str] = ()) -> bytes:
    redacted = value
    for secret in sorted({item for item in secret_values if item}, key=len, reverse=True):
        needle = secret.encode("utf-8", errors="surrogatepass")
        redacted = redacted.replace(needle, _redaction(secret).encode())
    return redacted


def secret_values_from_argv(argv: Sequence[str]) -> tuple[str, ...]:
    """Return values following secret-looking options for launch diagnostics."""
    values: list[str] = []
    for index, item in enumerate(argv):
        option, separator, value = item.partition("=")
        if separator and _SECRET_OPTION.search(option):
            values.append(value)
        elif _SECRET_OPTION.search(item) and index + 1 < len(argv):
            values.append(argv[index + 1])
    return tuple(value for value in values if value)


def redact_argv(
    argv: Sequence[str],
    *,
    secret_values: Iterable[str] = (),
    secret_positions: Iterable[int] = (),
) -> tuple[str, ...]:
    secrets = tuple(secret_values)
    positions = set(secret_positions)
    result: list[str] = []
    for index, item in enumerate(argv):
        if index in positions:
            result.append(_redaction(item))
            continue
        option, separator, value = item.partition("=")
        if separator and _SECRET_OPTION.search(option):
            result.append(option + "=" + _redaction(value))
            continue
        if _SECRET_OPTION.search(item) and index + 1 < len(argv):
            result.append(item)
            positions.add(index + 1)
            continue
        result.append(redact_text(item, secrets))
    return tuple(result)
