from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_workflow.contracts import load_schema, read_contract, validate_instance
from agent_workflow.errors import WorkflowError
from agent_workflow.migrations import migrate_contract


class ContractTests(unittest.TestCase):
    def test_packaged_schema_loads_and_validates_instance(self) -> None:
        schema = load_schema("agent-workflow/evaluation-plan/v1")
        self.assertEqual(schema["$id"], "agent-workflow/evaluation-plan/v1")
        value = {
            "schema": "agent-workflow/evaluation-plan/v1",
            "dataset_split": "development",
            "task_ids": ["P0-00"],
            "repetitions": 1,
            "timeout_seconds": 60,
            "scorers": ["acceptance_commands"],
            "sandbox": "docker",
        }
        validate_instance(value, value["schema"])
        with self.assertRaisesRegex(WorkflowError, "repetitions"):
            validate_instance({**value, "repetitions": 0}, value["schema"])

    def test_read_contract_rejects_wrong_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "value.json"
            path.write_text(json.dumps({"schema": "unknown/v1"}), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "unexpected contract schema"):
                read_contract(path, "agent-workflow/evaluation-plan/v1")

    def test_status_v1_migrates_in_memory(self) -> None:
        source = {
            "schema": "agent-workflow/session-status/v1",
            "status": "accepted",
            "session_id": "sample",
        }
        migrated = migrate_contract(source, "agent-workflow/session-status/v2")
        self.assertEqual(source["status"], "accepted")
        self.assertEqual(migrated["status"], "completed")
        self.assertEqual(migrated["disposition"], "accepted")
        self.assertEqual(migrated["schema"], "agent-workflow/session-status/v2")
