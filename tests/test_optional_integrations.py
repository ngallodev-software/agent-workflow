import json
import tempfile
import unittest
from pathlib import Path

from agent_workflow.integrations.swebench import write_prediction


class OptionalIntegrationTests(unittest.TestCase):
    def test_swebench_prediction_uses_official_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patch = root / "patch.diff"
            output = root / "predictions.jsonl"
            patch.write_text("diff --git a/a b/a\n", encoding="utf-8")
            write_prediction(
                instance_id="project__issue-1",
                model_name_or_path="codex",
                patch_path=patch,
                output=output,
            )
            value = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                set(value), {"instance_id", "model_name_or_path", "model_patch"}
            )
