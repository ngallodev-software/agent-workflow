"""Deterministic, receipt-based evaluation primitives."""

from .commands import CommandSpec, collect_commands
from .scope import ScopePolicy, collect_scope, compare_scope
from .scoring import score_trial

__all__ = [
    "CommandSpec",
    "ScopePolicy",
    "collect_commands",
    "collect_scope",
    "compare_scope",
    "score_trial",
]
