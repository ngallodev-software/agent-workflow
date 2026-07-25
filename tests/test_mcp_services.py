from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from agent_workflow.config import defaults
from agent_workflow.mcp.services import (
    MAX_PAGE_SIZE,
    PackValidationRequest,
    PageRequest,
    ServiceError,
    WorkflowReadService,
)


class McpServiceTests(unittest.TestCase):
    def _service(self, root: Path) -> WorkflowReadService:
        settings = defaults(root / "config.toml")
        settings = settings.__class__(**{**settings.__dict__, "state_root": root / "state"})
        return WorkflowReadService(settings, repository_root=root)

    def _run(self, root: Path, session_id: str = "run-1") -> Path:
        run = root / "state" / "runs" / session_id
        run.mkdir(parents=True)
        (run / "status.json").write_text(
            json.dumps(
                {
                    "schema": "agent-workflow/session-status/v2",
                    "session_id": session_id,
                    "status": "running",
                    "executor": "codex",
                    "agent_name": "larry",
                    "model": "gpt-5.4-mini",
                    "workdir": "/secret/worktree",
                    "error": "/secret/token",
                }
            ),
            encoding="utf-8",
        )
        return run

    def test_status_is_redacted_and_service_is_shared_transport_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._run(root)
            status = self._service(root).get_status("run-1")
            self.assertEqual(status["agent_name"], "larry")
            self.assertNotIn("workdir", status)
            self.assertNotIn("error", status)

    def test_invalid_identifier_missing_run_and_pagination_bounds_are_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self._service(Path(tmp))
            for session_id, category in (("../bad", "invalid_identifier"), ("missing", "not_found")):
                with self.subTest(session_id=session_id), self.assertRaises(ServiceError) as caught:
                    service.get_status(session_id)
                self.assertEqual(caught.exception.category, category)
            with self.assertRaises(ServiceError) as caught:
                service.list_runs(PageRequest(limit=MAX_PAGE_SIZE + 1))
            self.assertEqual(caught.exception.category, "invalid_limit")

    def test_run_and_receipt_symlink_escapes_are_denied(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            runs = root / "state" / "runs"
            runs.mkdir(parents=True)
            (runs / "escaped").symlink_to(outside, target_is_directory=True)
            service = self._service(root)
            with self.assertRaises(ServiceError) as caught:
                service.get_status("escaped")
            self.assertEqual(caught.exception.category, "forbidden_root")

            run = self._run(root, "safe")
            (run / "receipts").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ServiceError) as caught:
                service.list_receipts("safe")
            self.assertEqual(caught.exception.category, "forbidden_root")

    def test_pack_validation_rejects_traversal_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            service = self._service(root)
            with self.assertRaises(ServiceError) as caught:
                service.validate_pack(PackValidationRequest("../outside"))
            self.assertEqual(caught.exception.category, "forbidden_root")
            link = root / "pack-link"
            link.symlink_to(Path(outside_tmp), target_is_directory=True)
            with self.assertRaises(ServiceError) as caught:
                service.validate_pack(PackValidationRequest("pack-link"))
            self.assertEqual(caught.exception.category, "forbidden_root")

    def test_receipts_return_names_and_hashes_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self._run(root)
            receipts = run / "receipts"
            receipts.mkdir()
            (receipts / "001-final.json").write_text('{"ok":true}\n', encoding="utf-8")
            result = self._service(root).list_receipts("run-1").as_dict()
            self.assertEqual(result["items"][0]["name"], "001-final.json")
            self.assertEqual(len(result["items"][0]["sha256"]), 64)
