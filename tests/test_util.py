import tempfile
import unittest
from pathlib import Path

from agent_workflow.errors import WorkflowError
from agent_workflow.util import atomic_write_json, read_json, slug, validate_id


class UtilTests(unittest.TestCase):
    def test_safe_identifiers_and_slug(self):
        self.assertEqual(validate_id("project-p0-01"), "project-p0-01")
        self.assertEqual(slug("P0-01 Proxy Contract"), "p0-01-proxy-contract")
        with self.assertRaises(WorkflowError):
            validate_id("../unsafe")

    def test_atomic_json_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            atomic_write_json(path, {"status": "running"})
            self.assertEqual(read_json(path)["status"], "running")
