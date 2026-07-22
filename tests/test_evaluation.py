from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_workflow.errors import WorkflowError
from agent_workflow.evaluation import validate_evaluation


class EvaluationPlanTests(unittest.TestCase):
    def _write(self, root: Path, **changes) -> Path:
        value = {
            "schema": "agent-workflow/evaluation-plan/v1",
            "dataset_split": "validation",
            "task_ids": ["P0-00"],
            "repetitions": 3,
            "timeout_seconds": 300,
            "max_retries": 0,
            "scorers": ["acceptance_commands", "writable_scope"],
            "sandbox": "docker",
        }
        value.update(changes)
        path = root / "evals" / "evaluation.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_valid_plan_has_stable_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write(root)
            first = validate_evaluation(path, pack_root=root, task_ids={"P0-00"})
            path.write_text(
                json.dumps(first.data, indent=2, sort_keys=True), encoding="utf-8"
            )
            second = validate_evaluation(path, pack_root=root, task_ids={"P0-00"})
            self.assertEqual(first.sha256, second.sha256)

    def test_unknown_task_and_oracle_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write(root, task_ids=["P9-99"])
            with self.assertRaisesRegex(WorkflowError, "unknown tasks"):
                validate_evaluation(path, pack_root=root, task_ids={"P0-00"})
            path = self._write(
                root,
                oracle_refs={"P9-99": {"id": "secret", "sha256": "0" * 64}},
            )
            with self.assertRaisesRegex(WorkflowError, "oracle_refs"):
                validate_evaluation(path, pack_root=root, task_ids={"P0-00"})

    def test_plan_escape_and_malformed_instance_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "pack"
            root.mkdir()
            outside = self._write(Path(tmp), repetitions=0)
            with self.assertRaisesRegex(WorkflowError, "escapes pack root"):
                validate_evaluation(outside, pack_root=root)
            inside = self._write(root, repetitions=0)
            with self.assertRaisesRegex(WorkflowError, "repetitions"):
                validate_evaluation(inside, pack_root=root)
