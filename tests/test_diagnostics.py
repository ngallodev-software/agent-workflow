import unittest

from agent_workflow.diagnostics import classify_failure


class FailureTaxonomyTests(unittest.TestCase):
    def test_known_failures_are_stable_and_unknown_stays_unclassified(self):
        cases = {
            "permission denied": "permission_denied",
            "HTTP 429 rate limit": "rate_limited",
            "API key unauthorized": "authentication",
            "executable not found": "command_not_found",
            "surprising failure": "unclassified",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(
                    classify_failure(exit_code=1, stderr=text), expected
                )
        self.assertIsNone(classify_failure(exit_code=0))
