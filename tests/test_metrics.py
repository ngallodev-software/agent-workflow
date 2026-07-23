import json
import tempfile
import unittest
from pathlib import Path

from agent_workflow.errors import WorkflowError
from agent_workflow.messages import append_message
from agent_workflow.metrics import normalize_usage, write_execution_evidence
from agent_workflow.receipts import make_read_only, seal_run, verify_seal
from agent_workflow.util import atomic_write_json, sha256_file
from run_fixtures import write_run_contracts


class MetricsTests(unittest.TestCase):
    def test_normalization_preserves_unknown_as_null_and_rejects_invalid_numbers(self):
        self.assertEqual(
            normalize_usage({"prompt_tokens": 10, "completion_tokens": 3}),
            {
                "input_tokens": 10,
                "cached_input_tokens": None,
                "output_tokens": 3,
                "provider_total_tokens": None,
                "cost": None,
                "currency": None,
            },
        )
        self.assertIsNone(normalize_usage({"input_tokens": -1})["input_tokens"])
        self.assertIsNone(normalize_usage({"output_tokens": True})["output_tokens"])
        self.assertEqual(
            4,
            normalize_usage({"prompt_tokens_details": {"cached_tokens": 4}})["cached_input_tokens"],
        )

    def test_command_collection_populates_only_verification_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            write_run_contracts(run, session_id="metrics-duration")
            atomic_write_json(run / "collections" / "commands-post.json", {
                "schema": "agent-workflow/command-collection-set/v1", "phase": "post",
                "commands": [{"duration_seconds": 0.25}, {"duration_seconds": 0.75}, {"duration_seconds": -1}],
            })
            metrics = write_execution_evidence(run, elapsed_seconds=3.0)
            stages = {item["stage"]: item for item in metrics["stages"]}
            self.assertEqual(1.0, stages["verification"]["elapsed_seconds"])
            self.assertEqual(3.0, stages["total"]["elapsed_seconds"])

    def test_metrics_include_required_stages_and_control_events_are_sealed_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            write_run_contracts(run, session_id="metrics-run")
            provenance = json.loads((run / "run-provenance.json").read_text())
            provenance["usage"] = {"input_tokens": 7, "output_tokens": 2}
            atomic_write_json(run / "run-provenance.json", provenance)
            steer = append_message(run, session_id="metrics-run", direction="parent_to_child", kind="steer", actor="parent", content="check")
            append_message(run, session_id="metrics-run", direction="child_to_parent", kind="ack", actor="worker-1", content="applied", correlation_id=steer["message_id"])
            metrics = write_execution_evidence(run, elapsed_seconds=1.25)
            stages = {stage["stage"]: stage for stage in metrics["stages"]}
            self.assertEqual({"orchestrator", "child:worker-1", "verification", "total"}, set(stages))
            self.assertEqual(1, stages["orchestrator"]["steer_acknowledged_count"])
            self.assertIsNone(stages["verification"]["input_tokens"])
            verified = verify_seal(run, expected_sha256=sha256_file(run / "final-receipt.json")) if False else None
            receipt = seal_run(run, session_id="metrics-run")
            digest = sha256_file(run / "final-receipt.json")
            verified = verify_seal(run, expected_sha256=digest)
            paths = {item["path"] for item in verified["artifacts"]}
            self.assertIn("execution-metrics.json", paths)
            self.assertIn("control-events.jsonl", paths)
            make_read_only(run)
            self.assertEqual(0, (run / "execution-metrics.json").stat().st_mode & 0o222)
            self.assertEqual(0, (run / "control-events.jsonl").stat().st_mode & 0o222)

    def test_sealing_rejects_invalid_metrics_and_control_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            write_run_contracts(run, session_id="metrics-run")
            atomic_write_json(run / "execution-metrics.json", {"schema": "agent-workflow/execution-metrics/v1"})
            with self.assertRaises(WorkflowError):
                seal_run(run, session_id="metrics-run")
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            write_run_contracts(run, session_id="metrics-run")
            (run / "control-events.jsonl").write_text("{}\n", encoding="utf-8")
            with self.assertRaises(WorkflowError):
                seal_run(run, session_id="metrics-run")
