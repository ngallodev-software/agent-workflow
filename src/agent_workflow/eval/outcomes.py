"""Typed operational outcome helpers shared by evaluation projections."""

from __future__ import annotations

from typing import Any, Mapping


def classify_attempt(
    status: Mapping[str, Any],
    *,
    receipt_verified: bool = True,
    completion_result: str | None = None,
) -> str:
    """Classify an attempt without implying review or acceptance authority."""
    if not receipt_verified:
        return "integrity-unverified"
    completion = completion_result or status.get("completion_result")
    policy = status.get("policy_result")
    executor = status.get("executor_result")
    if completion in {"missing", "invalid"}:
        return f"completion-{completion}"
    if policy == "failed":
        return "policy-failed"
    if executor in {"failed", "interrupted", "killed", "lost"}:
        return f"executor-{executor}"
    if bool(status.get("acceptance_eligible")):
        return "acceptance-eligible"
    if executor == "completed" or status.get("status") == "completed":
        return "completed-not-accepted"
    return "terminal-unclassified"
