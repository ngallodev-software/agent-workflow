from __future__ import annotations

from agent_workflow.policy import evaluate_budgets


def test_budget_policy_matrix_keeps_policy_failures_separate_from_executor_outcomes() -> None:
    cases = [
        (
            {"input_tokens": 289732, "output_tokens": 4982},
            {"max_input_tokens": 80000, "max_output_tokens": 10000},
            155.79,
            {
                "policy_result": "failed",
                "policy_failure_category": "budget_exhausted",
                "metrics": ["input_tokens"],
            },
        ),
        (
            {},
            {},
            1.0,
            {
                "policy_result": "not_evaluated",
                "policy_failure_category": None,
                "metrics": [],
            },
        ),
        (
            {"currency": "EUR", "provider_billed_cost": 4.0},
            {"currency": "USD", "max_cost": 3.0, "max_wall_seconds": 2},
            2.5,
            {
                "policy_result": "failed",
                "policy_failure_category": "budget_exhausted",
                "metrics": ["cost", "currency", "wall_seconds"],
            },
        ),
    ]

    for usage, budget, wall_seconds, expected in cases:
        result = evaluate_budgets(usage, budget, wall_seconds=wall_seconds)
        assert result["policy_result"] == expected["policy_result"]
        assert result["policy_failure_category"] == expected["policy_failure_category"]
        assert [item["metric"] for item in result["policy_failures"]] == expected["metrics"]
