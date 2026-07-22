import tempfile
import unittest
from pathlib import Path

from agent_workflow.errors import WorkflowError
from agent_workflow.eval.oracles import resolve_oracle, scan_for_leak
from agent_workflow.util import sha256_file


class OracleBoundaryTests(unittest.TestCase):
    def test_oracle_is_resolved_by_id_and_hash_outside_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            oracle = root / "oracles" / "task-1"
            oracle.mkdir(parents=True)
            manifest = oracle / "oracle.json"
            manifest.write_text('{"expected": "pass"}\n', encoding="utf-8")
            value = resolve_oracle("task-1", sha256_file(manifest), root / "oracles")
            self.assertEqual(value.oracle_id, "task-1")
            with self.assertRaisesRegex(WorkflowError, "escapes"):
                resolve_oracle("../escape", "0" * 64, root / "oracles")

    def test_canary_scan_detects_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "output.log"
            artifact.write_bytes(b"prefix evaluator-secret suffix")
            self.assertEqual(
                scan_for_leak(b"evaluator-secret", [artifact]), [str(artifact)]
            )
