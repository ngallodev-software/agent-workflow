import tempfile
import unittest
from pathlib import Path

from agent_workflow.ledger import build_ledger, render_ledger


class LedgerTests(unittest.TestCase):
    def test_missing_and_corrupt_sessions_remain_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            phase = pack / "phase-0"
            phase.mkdir(parents=True)
            (phase / "task-manifest.yaml").write_text(
                "tasks:\n"
                "  - id: P0-01\n"
                "    tier: low\n"
                "    session: first\n"
                "    prompt: tickets/one.md\n"
                "  - id: P0-02\n"
                "    tier: low\n"
                "    session: second\n"
                "    prompt: tickets/two.md\n",
                encoding="utf-8",
            )
            runs = root / "runs"
            (runs / "second").mkdir(parents=True)
            (runs / "second" / "status.json").write_text("{", encoding="utf-8")
            value = build_ledger(pack, runs)
            self.assertEqual(len(value["rows"]), 2)
            self.assertEqual(value["rows"][0]["status"], "missing")
            self.assertIn("invalid status", value["rows"][1]["error"])
            self.assertEqual(
                value["rows"][1]["next_action"],
                "agent-workflow status second --json",
            )
            self.assertIn("P0-01", render_ledger(value))
