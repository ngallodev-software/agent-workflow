from __future__ import annotations

import unittest
from dataclasses import replace

from agent_workflow.config import AgentClassPolicy, ExecutorPolicy, defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.routing import advise_routing


class RoutingAdviceTests(unittest.TestCase):
    def test_task_types_route_to_stable_agent_classes(self):
        settings = defaults()
        cases = {
            "research": ("exploratory", "TASK_EXPLORATORY"),
            "discovery": ("exploratory", "TASK_EXPLORATORY"),
            "review": ("review", "TASK_REVIEW"),
            "security": ("review", "TASK_REVIEW"),
            "implementation": ("implementation", "TASK_IMPLEMENTATION"),
            "unknown": ("implementation", "TASK_IMPLEMENTATION"),
        }
        for task_type, (agent_class, code) in cases.items():
            with self.subTest(task_type=task_type):
                advice = advise_routing({"task_type": task_type}, settings)
                self.assertEqual(advice["recommendation"]["agent_class"], agent_class)
                self.assertIn(code, advice["explanation_codes"])

    def test_interactivity_metadata_is_advisory_and_explained(self):
        settings = defaults()
        required = advise_routing(
            {"task_type": "research", "requires_interaction": True}, settings
        )
        self.assertTrue(required["recommendation"]["interactive"])
        self.assertIn("INTERACTION_REQUIRED", required["explanation_codes"])
        disabled = advise_routing(
            {"task_type": "implementation", "requires_interaction": False}, settings
        )
        self.assertFalse(disabled["recommendation"]["interactive"])
        self.assertIn("INTERACTION_NOT_REQUIRED", disabled["explanation_codes"])

    def test_enforced_selection_and_policy_disagreement_are_separate(self):
        advice = advise_routing(
            {"task_type": "review"},
            defaults(),
            enforced_selection={"executor": "claude", "model": "sonnet"},
        )
        self.assertEqual(advice["recommendation"]["executor"], "codex")
        self.assertEqual(advice["enforced_selection"]["executor"], "claude")
        self.assertEqual(advice["policy_disagreements"], ["executor", "model"])
        self.assertIn("ENFORCED_SELECTION_DIFFERS", advice["explanation_codes"])

    def test_high_risk_implementation_has_stable_explanation(self):
        advice = advise_routing(
            {"task_type": "implementation", "risk": "critical"}, defaults()
        )
        self.assertIn("RISK_HIGH_IMPLEMENTATION", advice["explanation_codes"])

    def test_no_go_only_model_policy_is_rejected(self):
        base = defaults()
        settings = replace(
            base,
            executor_policies={
                **base.executor_policies,
                "codex": ExecutorPolicy(
                    interactive_command=["codex"],
                    models=("blocked-model",),
                    default_model="blocked-model",
                    no_go_models=("blocked-*",),
                ),
            },
            agent_classes={
                **base.agent_classes,
                "review": AgentClassPolicy(
                    interactive=False,
                    default_executor="codex",
                    default_model="blocked-model",
                    allowed_models={"codex": ("blocked-model",)},
                ),
            },
        )
        with self.assertRaisesRegex(WorkflowError, "no non-no-go model"):
            advise_routing({"task_type": "review"}, settings)

    def test_input_metadata_is_not_mutated_and_output_is_deterministic(self):
        metadata = {"task_type": "research", "requires_interaction": False}
        first = advise_routing(metadata, defaults())
        second = advise_routing(metadata, defaults())
        self.assertEqual(first, second)
        self.assertEqual(metadata, {"task_type": "research", "requires_interaction": False})


if __name__ == "__main__":
    unittest.main()
