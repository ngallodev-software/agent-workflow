from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from agent_workflow.bindings import resolve_json_pointer, resolve_node_inputs
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.receipts import seal_run
from agent_workflow.util import atomic_write_json, sha256_file
from agent_workflow.workflow import initial_status, normalize_snapshot
from run_fixtures import write_run_contracts


def _sealed_result_run(settings, run_id: str, value: dict[str, object]) -> Path:
    run = settings.state_root / "runs" / run_id
    write_run_contracts(run, session_id=run_id)
    atomic_write_json(run / "result.json", value)
    digest = sha256_file(run / "result.json")
    atomic_write_json(
        run / "collections" / "task-result.json",
        {
            "schema": "agent-workflow/task-result-collection/v1",
            "session_id": run_id,
            "required": True,
            "schema_path": "result.schema.json",
            "source_path": "handoff/result.json",
            "source_sha256": digest,
            "stored_path": "result.json",
            "stored_sha256": digest,
            "validation_status": "valid",
            "validation_errors": [],
            "collected_at": "2026-07-24T00:00:00+00:00",
        },
    )
    seal_run(run, session_id=run_id)
    return run


def _binding_fixture(root: Path):
    settings = replace(defaults(), state_root=root / "state")
    _sealed_result_run(settings, "source-run", {"nested": {"answer": 42}, "items": ["a", "b"]})
    snapshot = normalize_snapshot(
        {
            "workflow_id": "binding-workflow",
            "pack_id": "pack",
            "pack_manifest_sha256": "a" * 64,
            "nodes": [
                {
                    "node_id": "source",
                    "session_id": "source-run",
                    "prompt_path": "source.md",
                    "dependencies": [],
                },
                {
                    "node_id": "target",
                    "session_id": "target-run",
                    "prompt_path": "target.md",
                    "dependencies": ["source"],
                    "input_bindings": {
                        "answer": {
                            "source_node_id": "source",
                            "pointer": "/nested/answer",
                            "required": True,
                            "max_bytes": 128,
                        }
                    },
                },
            ],
        }
    )
    status = initial_status(snapshot)
    states = {item["node_id"]: item for item in status["nodes"]}
    states["source"].update(state="completed", run_id="source-run", attempt=1)
    states["target"]["state"] = "eligible"
    node = next(item for item in snapshot["nodes"] if item["node_id"] == "target")
    return settings, snapshot, status, node


class WorkflowBindingTests(unittest.TestCase):
    def test_json_pointer_rejects_invalid_escapes_and_array_aliases(self):
        with self.assertRaisesRegex(WorkflowError, "invalid escape"):
            resolve_json_pointer({"a": 1}, "/~2")
        self.assertIsNot(resolve_json_pointer(["zero"], "/00"), "zero")
        self.assertEqual(resolve_json_pointer({"a/b": {"~": 7}}, "/a~1b/~0"), 7)

    def test_binding_snapshot_replay_is_idempotent_and_preserves_creation_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings, snapshot, status, node = _binding_fixture(root)
            workflow_dir = root / "workflow"
            with patch("agent_workflow.bindings.utc_now", return_value="2026-07-24T01:00:00+00:00"):
                first = resolve_node_inputs(
                    snapshot=snapshot,
                    status=status,
                    node=node,
                    settings=settings,
                    workflow_run_dir=workflow_dir,
                    attempt=1,
                )
            with patch("agent_workflow.bindings.utc_now", return_value="2099-01-01T00:00:00+00:00"):
                second = resolve_node_inputs(
                    snapshot=snapshot,
                    status=status,
                    node=node,
                    settings=settings,
                    workflow_run_dir=workflow_dir,
                    attempt=1,
                )
            assert first is not None and second is not None
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(second["artifact"]["created_at"], "2026-07-24T01:00:00+00:00")
            self.assertEqual(second["artifact"]["bindings"][0]["value"], 42)
            self.assertEqual(0, Path(second["path"]).stat().st_mode & 0o222)

    def test_existing_binding_snapshot_must_be_regular_read_only_and_match_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings, snapshot, status, node = _binding_fixture(root)
            workflow_dir = root / "workflow"
            evidence = resolve_node_inputs(
                snapshot=snapshot,
                status=status,
                node=node,
                settings=settings,
                workflow_run_dir=workflow_dir,
                attempt=1,
            )
            assert evidence is not None
            path = Path(evidence["path"])
            os.chmod(path, 0o644)
            with self.assertRaisesRegex(WorkflowError, "read-only"):
                resolve_node_inputs(
                    snapshot=snapshot,
                    status=status,
                    node=node,
                    settings=settings,
                    workflow_run_dir=workflow_dir,
                    attempt=1,
                )

    def test_binding_source_must_be_an_ancestor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings, snapshot, status, node = _binding_fixture(root)
            detached = dict(node)
            detached["dependencies"] = []
            detached["input_bindings"] = node["input_bindings"]
            altered = normalize_snapshot(
                {
                    **snapshot,
                    "nodes": [
                        next(item for item in snapshot["nodes"] if item["node_id"] == "source"),
                        detached,
                    ],
                }
            )
            altered_node = next(item for item in altered["nodes"] if item["node_id"] == "target")
            altered_status = initial_status(altered)
            states = {item["node_id"]: item for item in altered_status["nodes"]}
            states["source"].update(state="completed", run_id="source-run", attempt=1)
            with self.assertRaisesRegex(WorkflowError, "predecessor"):
                resolve_node_inputs(
                    snapshot=altered,
                    status=altered_status,
                    node=altered_node,
                    settings=settings,
                    workflow_run_dir=root / "workflow",
                    attempt=1,
                )


if __name__ == "__main__":
    unittest.main()
