import tempfile
import unittest
import json
import os
from pathlib import Path

from agent_workflow.errors import WorkflowError
from agent_workflow.receipts import seal_run, verify_seal
from agent_workflow.util import sha256_file
from run_fixtures import write_run_contracts


class ReceiptTests(unittest.TestCase):
    def test_seal_is_anchored_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run_contracts(root)
            (root / "output.log").write_text("done\n", encoding="utf-8")

            first = seal_run(root, session_id="test-run")
            expected = sha256_file(root / "final-receipt.json")
            self.assertEqual(
                verify_seal(root, expected_sha256=expected), first
            )
            with self.assertRaisesRegex(WorkflowError, "already sealed"):
                seal_run(root, session_id="test-run")

            receipt_path = root / "final-receipt.json"
            os.chmod(receipt_path, 0o644)
            forged = json.loads(receipt_path.read_text(encoding="utf-8"))
            forged["artifacts"] = [
                item for item in forged["artifacts"] if item["path"] != "output.log"
            ]
            receipt_path.write_text(json.dumps(forged), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "checksum mismatch"):
                verify_seal(root, expected_sha256=expected)

            receipt_path.unlink()
            seal_run(root, session_id="test-run")
            expected = sha256_file(root / "final-receipt.json")

            (root / "output.log").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "mismatch"):
                verify_seal(root, expected_sha256=expected)

    def test_seal_rejects_missing_required_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "prompt.md").write_text("ticket\n", encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "missing artifacts"):
                seal_run(root, session_id="incomplete")
