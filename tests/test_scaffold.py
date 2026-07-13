import tempfile
import unittest
from pathlib import Path

from agent_workflow.manifests import validate_pack
from agent_workflow.pack import scaffold


class ScaffoldTests(unittest.TestCase):
    def test_scaffold_creates_valid_three_phase_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "sample-pack"
            scaffold(destination, 3, "Sample Pack")
            report = validate_pack(destination)
            self.assertTrue(report.ok, report.errors)
            self.assertEqual(report.phases, 3)
            self.assertTrue(
                (destination / "phase-2/tickets/P2-00-baseline-and-preflight.md").is_file()
            )
            self.assertTrue(
                (destination / "scripts/launch-delegation.sh").stat().st_mode & 0o111
            )
