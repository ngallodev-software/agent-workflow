"""Lightweight constants required to construct and dispatch the public CLI.

Keep this module dependency-free so normal command startup does not import
advanced capability implementations merely to discover parser choices or route
a parsed command.
"""

from __future__ import annotations


BUILTIN_TOP_LEVEL_COMMANDS = frozenset(
    {
        "doctor",
        "commands",
        "workflow",
        "completion",
        "config",
        "plugins",
        "orchestrator",
        "delegate",
        "worktree",
        "agent-run",
        "assess-sealed-runs",
        "ledger",
        "supervisor",
        "index",
        "agent",
        "eval",
        "benchmark",
        "pack",
    }
)

CORE_COMMANDS = frozenset({"commands", "plugins", "doctor", "completion", "config"})
REPORTING_COMMANDS = frozenset({"assess-sealed-runs", "ledger"})

# Role-scoped command-profile names are parser/catalog metadata, not capability code.
# Keep them here so scoped parser construction does not import command_catalog and
# its schema-validation dependencies on every built-in CLI invocation.
COMMAND_PROFILES = ("orchestrator", "implementation", "review")

EVALUATION_TEMPLATE_KINDS = (
    "evaluation-plan",
    "benchmark-manifest",
    "sealed-run-assessment",
    "benchmark-report",
    "ledger-row",
    "lifecycle-archive",
)

AUTHORIZED_WORKFLOW_TEMPLATES = (
    "pipeline",
    "parallel-review-fan-in",
    "implementation-independent-review",
)
