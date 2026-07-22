import unittest

from agent_workflow.errors import WorkflowError
from agent_workflow.eval.compare import ComparisonPolicy, compare_trials


def trial(repetition: int, verdict: str, prompt: str = "p") -> dict[str, object]:
    return {
        "fixture_revision": "f",
        "task_id": "t",
        "base_revision": "b",
        "prompt_sha256": prompt,
        "oracle_sha256": "o",
        "acceptance_commands_sha256": "a",
        "scope_policy_sha256": "s",
        "scorer_versions_sha256": "v",
        "sandbox": "docker",
        "budget_sha256": "budget",
        "repetition": repetition,
        "verdict": verdict,
    }


class ComparisonTests(unittest.TestCase):
    def test_single_trial_never_declares_winner_or_tail_metrics(self):
        value = compare_trials([trial(0, "fail")], [trial(0, "pass")])
        self.assertIsNone(value["winner"])
        self.assertEqual(value["paired_n"], 1)
        self.assertFalse(value["tail_metrics_eligible"]["p90"])

    def test_mismatched_cohort_fails_closed(self):
        with self.assertRaisesRegex(WorkflowError, "cohorts do not match"):
            compare_trials([trial(0, "pass")], [trial(0, "pass", prompt="different")])
        value = compare_trials(
            [trial(0, "pass")],
            [trial(0, "pass", prompt="different")],
            policy=ComparisonPolicy(allow_unpaired=True),
        )
        self.assertTrue(value["descriptive_only"])
        self.assertIsNone(value["winner"])

    def test_unpaired_analysis_never_declares_winner(self):
        baseline = [trial(index, "fail") for index in range(10)]
        candidate = [trial(index, "pass") for index in range(10)]
        candidate.append(trial(99, "pass"))
        value = compare_trials(
            baseline,
            candidate,
            policy=ComparisonPolicy(allow_unpaired=True),
        )
        self.assertTrue(value["descriptive_only"])
        self.assertIsNone(value["winner"])
