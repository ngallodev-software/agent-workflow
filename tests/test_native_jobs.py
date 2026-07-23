from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from agent_workflow.errors import WorkflowError
from agent_workflow.native_jobs import NATIVE_JOB_SCHEMA, validate_native_job


FIXTURE = Path("tests/fixtures/native-jobs/valid-job.json")


class NativeJobTests(unittest.TestCase):
    def _pack_with_job(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name) / "pack"
        (root / "prompts").mkdir(parents=True)
        (root / "prompts" / "P0-01.md").write_text("prompt", encoding="utf-8")
        job = root / "jobs" / "P0-01.json"
        job.parent.mkdir()
        shutil.copy2(FIXTURE, job)
        return tmp, root, job

    def test_valid_job_returns_typed_command_and_paths(self) -> None:
        tmp, root, job_path = self._pack_with_job()
        with tmp:
            job = validate_native_job(job_path, pack_root=root)
            self.assertEqual(job.schema, NATIVE_JOB_SCHEMA)
            self.assertEqual(job.ticket_id, "P0-01")
            self.assertEqual(job.prompt_path, root / "prompts" / "P0-01.md")
            self.assertEqual(job.acceptance_commands[0].argv, ("python3", "-m", "pytest", "-q"))
            self.assertTrue(job.review_requirement.independent)

    def test_job_is_json_only_and_rejects_unknown_schema(self) -> None:
        tmp, root, job_path = self._pack_with_job()
        with tmp:
            yaml_path = job_path.with_suffix(".yaml")
            yaml_path.write_text("schema: ignored", encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "must be a .json"):
                validate_native_job(yaml_path, pack_root=root)
            value = json.loads(job_path.read_text(encoding="utf-8"))
            value["schema"] = "example/external-job/v1"
            job_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "unsupported native job schema"):
                validate_native_job(job_path, pack_root=root)

    def test_rejects_prompt_and_policy_path_escapes(self) -> None:
        tmp, root, job_path = self._pack_with_job()
        with tmp:
            value = json.loads(job_path.read_text(encoding="utf-8"))
            value["prompt_path"] = "../outside.md"
            job_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "prompt_path must be a relative"):
                validate_native_job(job_path, pack_root=root)
            value["prompt_path"] = "prompts/P0-01.md"
            value["path_policy"]["allowed_paths"] = ["../outside.py"]
            job_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "allowed_paths entry must be a relative"):
                validate_native_job(job_path, pack_root=root)

    def test_rejects_bad_command_shape_and_duplicate_ids(self) -> None:
        tmp, root, job_path = self._pack_with_job()
        with tmp:
            value = json.loads(job_path.read_text(encoding="utf-8"))
            value["acceptance_commands"] = [{"id": "unit", "argv": "pytest"}]
            job_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "acceptance_commands.0.argv"):
                validate_native_job(job_path, pack_root=root)
            value["acceptance_commands"] = [
                {"id": "unit", "argv": ["pytest"]},
                {"id": "unit", "argv": ["python3"]},
            ]
            job_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "duplicate command IDs"):
                validate_native_job(job_path, pack_root=root)
