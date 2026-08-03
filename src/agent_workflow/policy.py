"""Orthogonal execution-policy evaluation.

Policy failures affect acceptance eligibility but never rewrite observed process,
completion, or evidence outcomes.
"""

from __future__ import annotations

from typing import Any


def evaluate_budgets(
    usage: dict[str, Any] | None,
    budgets: dict[str, Any] | None,
    *,
    wall_seconds: float,
) -> dict[str, Any]:
    configured = isinstance(budgets, dict) and any(
        budgets.get(key) is not None
        for key in (
            "max_input_tokens",
            "max_output_tokens",
            "max_cost",
            "currency",
            "max_wall_seconds",
        )
    )
    failures: list[dict[str, Any]] = []
    usage = usage if isinstance(usage, dict) else {}
    budgets = budgets if isinstance(budgets, dict) else {}

    for usage_key, budget_key in (
        ("input_tokens", "max_input_tokens"),
        ("output_tokens", "max_output_tokens"),
    ):
        used = usage.get(usage_key)
        limit = budgets.get(budget_key)
        if isinstance(used, (int, float)) and isinstance(limit, (int, float)) and used > limit:
            failures.append(
                {
                    "metric": usage_key,
                    "observed": used,
                    "limit": limit,
                    "operator": ">",
                    "accounting_version": "provider-evidence/v1",
                }
            )

    cost = usage.get("provider_billed_cost")
    cost_source = "provider_billed_cost"
    if cost is None:
        cost = usage.get("local_estimated_cost")
        cost_source = "local_estimated_cost"
    if cost is None:
        cost = usage.get("cost", usage.get("total_cost"))
        cost_source = "legacy_cost"
    max_cost = budgets.get("max_cost")
    if isinstance(cost, (int, float)) and isinstance(max_cost, (int, float)) and cost > max_cost:
        failures.append(
            {
                "metric": "cost",
                "observed": cost,
                "limit": max_cost,
                "operator": ">",
                "source": cost_source,
                "accounting_version": "provider-evidence/v1",
            }
        )

    expected_currency = budgets.get("currency")
    actual_currency = usage.get("currency")
    if expected_currency and actual_currency and expected_currency != actual_currency:
        failures.append(
            {
                "metric": "currency",
                "observed": actual_currency,
                "limit": expected_currency,
                "operator": "!=",
                "accounting_version": "provider-evidence/v1",
            }
        )

    wall_limit = budgets.get("max_wall_seconds")
    if isinstance(wall_limit, (int, float)) and wall_seconds > wall_limit:
        failures.append(
            {
                "metric": "wall_seconds",
                "observed": round(wall_seconds, 6),
                "limit": wall_limit,
                "operator": ">",
                "accounting_version": "monotonic-wall/v1",
            }
        )

    legacy = [
        f"{item['metric']}:{item['observed']}{item['operator']}{item['limit']}"
        for item in failures
    ]
    return {
        "policy_result": "failed" if failures else "passed" if configured else "not_evaluated",
        "policy_failures": failures,
        "budget_exceeded": legacy,
        "policy_failure_category": "budget_exhausted" if failures else None,
    }
