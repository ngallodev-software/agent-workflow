from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_workflow import contracts
from agent_workflow.contracts import load_schema, read_contract, validate_instance
from agent_workflow.errors import WorkflowError
from agent_workflow.migrations import migrate_contract
from agent_workflow.receipts import seal_run
from run_fixtures import write_run_contracts


class ContractTests(unittest.TestCase):
    def test_user_base_schema_layout_seals_run_contracts(self) -> None:
        """A user-site installation must discover its data-files schemas."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            userbase = root / "userbase"
            schema_root = userbase / "share" / "agent-workflow" / "schemas"
            shutil.copytree(Path("schemas"), schema_root)
            run = root / "run"
            write_run_contracts(run, session_id="userbase-test")

            # Isolate discovery from this checkout and the active interpreter prefix.
            with (
                patch.object(
                    contracts,
                    "__file__",
                    str(root / "isolated" / "agent_workflow" / "contracts.py"),
                ),
                patch.object(contracts.sys, "prefix", str(root / "prefix")),
                patch.object(contracts.site, "getuserbase", return_value=str(userbase)),
            ):
                contracts._schema_index.cache_clear()
                self.assertIn(schema_root, contracts._schema_roots())
                self.assertEqual(
                    contracts._schema_index()["agent-workflow/command/v1"],
                    schema_root / "command.schema.json",
                )
                seal_run(run, session_id="userbase-test")
                self.assertTrue((run / "final-receipt.json").is_file())
            contracts._schema_index.cache_clear()

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
