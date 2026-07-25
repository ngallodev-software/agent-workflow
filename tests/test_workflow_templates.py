from __future__ import annotations

import unittest

from agent_workflow.errors import WorkflowError
from agent_workflow.workflow_templates import AUTHORIZED_TEMPLATES, expand_workflow_template


def _node(node_id: str) -> dict[str, object]:
    return {
        "node_id": node_id,
        "session_id": f"session-{node_id.lower()}",
        "prompt_path": f"tickets/{node_id}.md",
    }


class WorkflowTemplateTests(unittest.TestCase):
    def _expand(self, template: str, parameters):
        return expand_workflow_template(
            template,
            workflow_id=f"wf-{template}",
            pack_id="pack",
            pack_manifest_sha256="c" * 64,
            parameters=parameters,
        )

    def test_pipeline_expansion_is_deterministic_and_canonical(self):
        parameters = {"steps": [_node("A"), _node("B"), _node("C")]}
        first = self._expand("pipeline", parameters)
        second = self._expand("pipeline", parameters)
        self.assertEqual(first, second)
        by_id = {node["node_id"]: node for node in first["nodes"]}
        self.assertEqual(by_id["A"]["dependencies"], [])
        self.assertEqual(by_id["B"]["dependencies"], ["A"])
        self.assertEqual(by_id["C"]["dependencies"], ["B"])
        self.assertEqual(parameters["steps"][1].get("dependencies"), None)

    def test_parallel_review_fan_in_has_parallel_reviews_and_sorted_fan_in(self):
        graph = self._expand(
            "parallel-review-fan-in",
            {
                "subject": _node("SUBJECT"),
                "reviews": [_node("REVIEW_B"), _node("REVIEW_A")],
                "fan_in": _node("MERGE"),
            },
        )
        by_id = {node["node_id"]: node for node in graph["nodes"]}
        self.assertEqual(by_id["REVIEW_A"]["dependencies"], ["SUBJECT"])
        self.assertEqual(by_id["REVIEW_B"]["dependencies"], ["SUBJECT"])
        self.assertEqual(by_id["MERGE"]["dependencies"], ["REVIEW_A", "REVIEW_B"])

    def test_implementation_independent_review_is_a_two_node_chain(self):
        graph = self._expand(
            "implementation-independent-review",
            {"implementation": _node("IMPLEMENT"), "review": _node("REVIEW")},
        )
        by_id = {node["node_id"]: node for node in graph["nodes"]}
        self.assertEqual(by_id["IMPLEMENT"]["dependencies"], [])
        self.assertEqual(by_id["REVIEW"]["dependencies"], ["IMPLEMENT"])

    def test_only_three_authorized_templates_and_invalid_parameters_fail(self):
        self.assertEqual(
            AUTHORIZED_TEMPLATES,
            (
                "pipeline",
                "parallel-review-fan-in",
                "implementation-independent-review",
            ),
        )
        cases = (
            ("persona-catalog", {}),
            ("pipeline", {"steps": []}),
            ("pipeline", {"steps": ["not-a-node"]}),
            ("parallel-review-fan-in", {"subject": _node("A"), "reviews": [_node("R")], "fan_in": _node("F")}),
            ("implementation-independent-review", {"implementation": _node("A")}),
        )
        for template, parameters in cases:
            with self.subTest(template=template, parameters=parameters):
                with self.assertRaises(WorkflowError):
                    self._expand(template, parameters)

    def test_template_expansion_rejects_duplicate_or_missing_node_ids(self):
        with self.assertRaisesRegex(WorkflowError, "duplicate workflow node ID"):
            self._expand("pipeline", {"steps": [_node("A"), _node("A")]})
        broken = _node("A")
        broken["node_id"] = ""
        with self.assertRaises(WorkflowError):
            self._expand("pipeline", {"steps": [broken]})


if __name__ == "__main__":
    unittest.main()
