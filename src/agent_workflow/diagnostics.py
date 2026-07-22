from __future__ import annotations

from collections.abc import Sequence


def classify_failure(
    *, exit_code: int | None, stderr: str = "", errors: Sequence[str] = ()
) -> str | None:
    if exit_code in (None, 0) and not errors:
        return None
    text = (stderr + "\n" + "\n".join(errors)).lower()
    rules = (
        ("command_not_found", ("not found", "no such file or directory")),
        ("permission_denied", ("permission denied", "requires --verbose")),
        ("authentication", ("unauthorized", "authentication", "api key")),
        ("rate_limited", ("rate limit", "too many requests", "http 429")),
        ("contract_invalid", ("invalid json", "schema", "contract")),
    )
    for category, needles in rules:
        if any(needle in text for needle in needles):
            return category
    return "unclassified"
