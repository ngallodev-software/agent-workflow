import tempfile
import unittest
import hashlib
import json
from pathlib import Path

from agent_workflow.errors import WorkflowError
from agent_workflow.eval.reporting import build_report, render_markdown
from agent_workflow.receipts import seal_run
from agent_workflow.util import atomic_write_json, sha256_file
from run_fixtures import write_run_contracts


class EvaluationReportTests(unittest.TestCase):
    def test_report_reads_only_sealed_local_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            write_run_contracts(run, session_id="report-test")
            seal_run(run, session_id="report-test")
            final_hash = sha256_file(run / "final-receipt.json")
            scores = run / "scores"
            scores.mkdir()
            score_receipt = {
                "schema": "agent-workflow/score-receipt/v1",
                "scorer": {"id": "schema_validity", "version": "1"},
                "final_receipt_sha256": final_hash,
                "verdict": "pass",
                "facts": {},
                "evidence": [],
            }
            digest = hashlib.sha256(
                json.dumps(
                    score_receipt, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            atomic_write_json(scores / f"schema_validity-{digest}.json", score_receipt)
            atomic_write_json(
                scores / "score-set.json",
                {
                    "final_receipt_sha256": final_hash,
                    "verdict": "pass",
                    "scores": [score_receipt],
                },
            )
            value = build_report(
                run,
                expected_final_receipt_sha256=final_hash,
            )
            self.assertEqual(value["score_verdict"], "pass")
            self.assertIn("report-test", render_markdown(value))

    def test_report_rejects_forged_unsealed_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            write_run_contracts(run, session_id="forged-score")
            seal_run(run, session_id="forged-score")
            final_hash = sha256_file(run / "final-receipt.json")
            scores = run / "scores"
            scores.mkdir()
            receipt = {
                "schema": "agent-workflow/score-receipt/v1",
                "scorer": {"id": "schema_validity", "version": "1"},
                "final_receipt_sha256": final_hash,
                "verdict": "pass",
                "facts": {},
                "evidence": [{"path": "not-sealed.txt", "sha256": "0" * 64}],
            }
            digest = hashlib.sha256(
                json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            atomic_write_json(scores / f"schema_validity-{digest}.json", receipt)
            atomic_write_json(
                scores / "score-set.json",
                {
                    "final_receipt_sha256": final_hash,
                    "verdict": "pass",
                    "scores": [receipt],
                },
            )
            with self.assertRaisesRegex(WorkflowError, "absent from .*final"):
                build_report(
                    run,
                    expected_final_receipt_sha256=final_hash,
                )
