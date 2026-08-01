"""Presentation-only traffic-light derivation for Agent Workflow.

Do not store the light as lifecycle truth. Recompute it from authoritative
run state, observed tmux state, inbox/review state, and policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Attention(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class AttentionResult:
    attention: Attention
    label: str
    reasons: tuple[str, ...]


RED_FLAGS = {
    "failed",
    "blocked",
    "orphaned",
    "terminal_unavailable",
    "security_violation",
    "unsafe_to_continue",
}
YELLOW_FLAGS = {
    "awaiting_review",
    "acknowledgement_required",
    "possibly_stalled",
    "retrying",
    "needs_decision",
}
NEUTRAL_FLAGS = {"queued", "not_started", "archived", "unknown"}


def derive_attention(
    *,
    lifecycle_status: str | None,
    observed_flags: set[str] | None = None,
    inbox_requires_action: bool = False,
    review_required: bool = False,
) -> AttentionResult:
    flags = set(observed_flags or ())
    if lifecycle_status:
        flags.add(lifecycle_status)

    red = sorted(flags & RED_FLAGS)
    if red:
        return AttentionResult(Attention.RED, "Action required", tuple(red))

    yellow = sorted(flags & YELLOW_FLAGS)
    if inbox_requires_action:
        yellow.append("inbox_requires_action")
    if review_required:
        yellow.append("review_required")
    if yellow:
        return AttentionResult(Attention.YELLOW, "Attention", tuple(dict.fromkeys(yellow)))

    if flags & NEUTRAL_FLAGS:
        return AttentionResult(Attention.NEUTRAL, "No live signal", tuple(sorted(flags & NEUTRAL_FLAGS)))

    return AttentionResult(Attention.GREEN, "Healthy", ("no_operator_action_needed",))
