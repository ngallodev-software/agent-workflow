import tempfile
import unittest
import json
import os
from pathlib import Path

from agent_workflow.errors import WorkflowError
from agent_workflow.receipts import make_read_only, seal_run, verify_seal
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
            with self.assertRaisesRegex(WorkflowError, "read-only|checksum mismatch"):
                verify_seal(root, expected_sha256=expected)

            receipt_path.unlink()
            seal_run(root, session_id="test-run")
            expected = sha256_file(root / "final-receipt.json")

            (root / "output.log").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "mismatch"):
                verify_seal(root, expected_sha256=expected)

    def test_seal_rejects_symlinked_lock_and_receipt_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run_contracts(root)
            target = root / "target"
            target.touch()
            os.symlink(target, root / "seal.lock")
            with self.assertRaises(WorkflowError):
                seal_run(root, session_id="unsafe-lock")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run_contracts(root)
            target = root / "missing-receipt-target"
            os.symlink(target, root / "final-receipt.json")
            with self.assertRaisesRegex(WorkflowError, "already sealed or unsafe"):
                seal_run(root, session_id="unsafe-receipt")

    def test_make_read_only_covers_optional_sealed_trees(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assignment = root / "assignments" / "child" / "record.json"
            assignment.parent.mkdir(parents=True)
            assignment.write_text("{}\n", encoding="utf-8")
            make_read_only(root)
            self.assertEqual(0, assignment.stat().st_mode & 0o222)

    def test_make_read_only_rejects_symlinks_without_chmodding_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside.json"
            outside.write_text("{}\n", encoding="utf-8")
            assignments = root / "assignments"
            assignments.mkdir()
            os.symlink(outside, assignments / "linked.json")
            before = outside.stat().st_mode & 0o777
            with self.assertRaisesRegex(WorkflowError, "symlink"):
                make_read_only(root)
            self.assertEqual(before, outside.stat().st_mode & 0o777)

    def test_verify_rejects_intermediate_symlink_even_when_target_stays_inside_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run_contracts(root)
            seal_run(root, session_id="intermediate-link")
            original = root / "collections"
            target = root / "collections-real"
            original.rename(target)
            os.symlink(target.name, original)
            with self.assertRaisesRegex(WorkflowError, "directory|symlink|open"):
                verify_seal(root)

    def test_seal_rejects_missing_required_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "prompt.md").write_text("ticket\n", encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "missing artifacts"):
                seal_run(root, session_id="incomplete")
