import tempfile
import unittest
from pathlib import Path

from agent_workflow.eval.scoring import score_trial
from agent_workflow.receipts import seal_run
from agent_workflow.util import atomic_write_json
from agent_workflow.util import sha256_file
from run_fixtures import write_run_contracts


class DeterministicScoringTests(unittest.TestCase):
    def test_scores_sealed_commands_and_is_byte_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            output = Path(tmp) / "scores"
            collections = root / "collections"
            root.mkdir()
            collections.mkdir()
            write_run_contracts(root, session_id="score-test")
            atomic_write_json(
                root / "evaluation-runtime.json",
                {
                    "schema": "agent-workflow/evaluation-runtime/v1",
                    "scorers": ["acceptance_commands", "evidence_fidelity"],
                },
            )
            atomic_write_json(
                collections / "commands-post.json",
                {
                    "schema": "agent-workflow/command-collection-set/v1",
                    "phase": "post",
                    "commands": [
                        {
                            "id": "unit",
                            "argv": ["python3", "-m", "pytest"],
                            "cwd": ".",
                            "exit_code": 0,
                            "timed_out": False,
                        }
                    ],
                },
            )
            seal_run(root, session_id="score-test")
            expected = sha256_file(root / "final-receipt.json")

            first = score_trial(
                root,
                output_dir=output,
                expected_final_receipt_sha256=expected,
            )
            initial_files = {path.name: path.read_bytes() for path in output.iterdir()}
            second = score_trial(
                root,
                output_dir=output,
                expected_final_receipt_sha256=expected,
            )
            final_files = {path.name: path.read_bytes() for path in output.iterdir()}

            self.assertEqual(first, second)
            self.assertEqual(first["verdict"], "pass")
            self.assertEqual(initial_files, final_files)

    def test_missing_required_collectors_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            write_run_contracts(root, session_id="missing-collectors")
            seal_run(root, session_id="missing-collectors")
            result = score_trial(
                root,
                output_dir=Path(tmp) / "scores",
                expected_final_receipt_sha256=sha256_file(
                    root / "final-receipt.json"
                ),
            )
            self.assertEqual(result["verdict"], "invalid")
            self.assertIn(
                "acceptance_commands",
                {
                    score["scorer"]["id"]
                    for score in result["scores"]
                    if score["verdict"] == "invalid"
                },
            )
