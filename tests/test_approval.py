from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from agent_workflow.approval import accepted_lifecycle_receipt, is_approved
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.ledger import build_ledger
from agent_workflow.scheduler import SchedulerService
from agent_workflow.lifecycle import record
from agent_workflow.util import atomic_write_json
from agent_workflow.workflow import (
    normalize_snapshot,
    record_workflow_binding,
    record_workflow_transition,
    snapshot_sha256,
)
from run_fixtures import write_run_contracts


def _completed_run(root: Path, session_id: str) -> Path:
    run = root / "state" / "runs" / session_id
    write_run_contracts(run, session_id=session_id)
    completion = json.loads((run / "completion.json").read_text(encoding="utf-8"))
    completion.update(result="completed", head_revision="abc123", unresolved=[])
    atomic_write_json(run / "completion.json", completion)
    atomic_write_json(
        run / "evaluation-runtime.json",
        {
            "schema": "agent-workflow/evaluation-runtime/v1",
            "scorers": ["acceptance_commands"],
        },
    )
    from agent_workflow.receipts import seal_run

    seal_run(run, session_id=session_id)
    status = json.loads((run / "status.json").read_text(encoding="utf-8"))
    status.update(
        status="completed",
        disposition=None,
        final_receipt_path=str(run / "final-receipt.json"),
        final_receipt_sha256=hashlib.sha256(
            (run / "final-receipt.json").read_bytes()
        ).hexdigest(),
        tier="medium",
    )
    atomic_write_json(run / "status.json", status)
    scores = run / "scores"
    scores.mkdir()
    score_receipts = []
    for scorer_id in ("schema_validity", "acceptance_commands"):
        score_receipt = {
            "schema": "agent-workflow/score-receipt/v1",
            "scorer": {"id": scorer_id, "version": "1"},
            "final_receipt_sha256": status["final_receipt_sha256"],
            "verdict": "pass",
            "facts": {},
            "evidence": [],
        }
        encoded = json.dumps(
            score_receipt, sort_keys=True, separators=(",", ":")
        ).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        atomic_write_json(scores / f"{scorer_id}-{digest}.json", score_receipt, mode=0o444)
        score_receipts.append(score_receipt)
    atomic_write_json(
        scores / "score-set.json",
        {
            "schema": "agent-workflow/score-set/v1",
            "final_receipt_sha256": status["final_receipt_sha256"],
            "verdict": "pass",
            "scores": score_receipts,
        },
    )
    return run


class ApprovalGateTests(unittest.TestCase):
    def test_accepted_receipt_satisfies_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = _completed_run(Path(tmp), "approval-accepted")
            settings = type("S", (), {"state_root": Path(tmp) / "state"})()
            record(
                settings,
                "approval-accepted",
                action="reviewed",
                actor="reviewer",
                reason="review",
            )
            record(
                settings,
                "approval-accepted",
                action="accepted",
                actor="reviewer",
                reason="approved",
                revision="abc123",
            )
            receipt = accepted_lifecycle_receipt(run)
            self.assertEqual(receipt["action"], "accepted")
            self.assertTrue(is_approved(run))

    def test_lifecycle_receipt_root_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = _completed_run(root, "approval-root-symlink")
            outside = root / "outside-receipts"
            outside.mkdir()
            os.symlink(outside, run / "receipts")
            settings = type("S", (), {"state_root": root / "state"})()
            with self.assertRaisesRegex(WorkflowError, "receipt root is unsafe"):
                record(
                    settings,
                    "approval-root-symlink",
                    action="reviewed",
                    actor="reviewer",
                    reason="review",
                )

    def test_rejected_tampered_unrelated_and_stale_receipts_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = _completed_run(root, "approval-primary")
            settings = type("S", (), {"state_root": root / "state"})()
            record(
                settings,
                "approval-primary",
                action="rejected",
                actor="reviewer",
                reason="reject",
            )
            self.assertFalse(is_approved(run))

            record(
                settings,
                "approval-primary",
                action="reviewed",
                actor="reviewer",
                reason="review",
            )
            record(
                settings,
                "approval-primary",
                action="accepted",
                actor="reviewer",
                reason="approved",
                revision="abc123",
            )
            receipt_path = run / "receipts" / "000003-accepted.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["final_receipt_sha256"] = "0" * 64
            atomic_write_json(receipt_path, receipt)
            self.assertFalse(is_approved(run))

            other = _completed_run(root, "approval-other")
            other_settings = type("S", (), {"state_root": root / "state"})()
            record(
                other_settings,
                "approval-other",
                action="reviewed",
                actor="reviewer",
                reason="review",
            )
            record(
                other_settings,
                "approval-other",
                action="accepted",
                actor="reviewer",
                reason="approved",
                revision="abc123",
            )
            status_path = run / "status.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status["lifecycle_receipt_path"] = str(
                other / "receipts" / "000002-accepted.json"
            )
            atomic_write_json(status_path, status)
            self.assertFalse(is_approved(run))

            stale_status = json.loads(status_path.read_text(encoding="utf-8"))
            stale_status["lifecycle_receipt_path"] = str(
                run / "receipts" / "000003-accepted.json"
            )
            stale_status["final_receipt_sha256"] = "f" * 64
            atomic_write_json(status_path, stale_status)
            self.assertFalse(is_approved(run))

            canonical = _completed_run(root, "approval-canonical")
            record(
                settings,
                "approval-canonical",
                action="reviewed",
                actor="reviewer",
                reason="review",
            )
            record(
                settings,
                "approval-canonical",
                action="accepted",
                actor="reviewer",
                reason="approved",
                revision="abc123",
            )
            canonical_status_path = canonical / "status.json"
            canonical_status = json.loads(
                canonical_status_path.read_text(encoding="utf-8")
            )
            canonical_status["lifecycle_receipt_path"] = str(
                other / "receipts" / "000002-accepted.json"
            )
            canonical_status["final_receipt_sha256"] = "f" * 64
            atomic_write_json(canonical_status_path, canonical_status)
            self.assertTrue(is_approved(canonical))

    def test_downstream_eligibility_follows_receipt_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_root = root / "pack"
            pack_root.mkdir()
            (pack_root / "phase-1").mkdir()
            (pack_root / "phase-1" / "task-manifest.yaml").write_text(
                "phase: 1\nname: gates\ntasks:\n  - id: DEP\n    tier: A\n    session: approval-dependency\n    prompt: tickets/DEP.md\n  - id: DOWN\n    tier: A\n    session: approval-dependent\n    prompt: tickets/DOWN.md\n    dependencies: [DEP]\n",
                encoding="utf-8",
            )
            dep_run = _completed_run(root, "approval-dependency")
            dep_settings = type("S", (), {"state_root": root / "state"})()
            record(
                dep_settings,
                "approval-dependency",
                action="reviewed",
                actor="reviewer",
                reason="review",
            )
            record(
                dep_settings,
                "approval-dependency",
                action="accepted",
                actor="reviewer",
                reason="approved",
                revision="abc123",
            )
            down_run = root / "state" / "runs" / "approval-dependent"
            write_run_contracts(down_run, session_id="approval-dependent", include_final=False)
            atomic_write_json(
                down_run / "status.json",
                {
                    "schema": "agent-workflow/session-status/v2",
                    "session_id": "approval-dependent",
                    "status": "missing",
                    "disposition": None,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                    "workdir": str(down_run),
                    "prompt_path": str(down_run / "prompt.md"),
                    "log_path": str(down_run / "output.log"),
                },
            )
            ledger = build_ledger(pack_root, root / "state" / "runs")
            row = next(item for item in ledger["rows"] if item["ticket"] == "DOWN")
            self.assertEqual(row["next_action"], "agent-workflow launch approval-dependent ...")
            self.assertTrue(is_approved(dep_run))

    def test_scheduler_advances_accepted_gate_and_launches_downstream(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = replace(defaults(), state_root=root / "state")
            subject_run = _completed_run(root, "approval-subject")
            record(settings, "approval-subject", action="reviewed", actor="reviewer", reason="review")
            record(
                settings,
                "approval-subject",
                action="accepted",
                actor="reviewer",
                reason="approved",
                revision="abc123",
            )
            workflow_dir = root / "workflow"
            workflow_dir.mkdir()
            snapshot = normalize_snapshot(
                {
                    "workflow_id": "accepted-gate-workflow",
                    "pack_id": "pack",
                    "pack_manifest_sha256": "a" * 64,
                    "nodes": [
                        {
                            "node_id": "subject",
                            "session_id": "approval-subject",
                            "prompt_path": "subject.md",
                            "dependencies": [],
                        },
                        {
                            "node_id": "gate",
                            "kind": "approval",
                            "approval_for": "subject",
                            "dependencies": ["subject"],
                        },
                        {
                            "node_id": "downstream",
                            "session_id": "approval-downstream",
                            "prompt_path": "downstream.md",
                            "dependencies": ["gate"],
                        },
                    ],
                }
            )
            digest = snapshot_sha256(snapshot)
            record_workflow_binding(
                workflow_dir,
                workflow_id=snapshot["workflow_id"],
                node_id="subject",
                run_id="approval-subject",
                attempt=1,
                actor="scheduler",
                reason="launch",
                snapshot_sha256=digest,
            )
            record_workflow_transition(
                workflow_dir, workflow_id=snapshot["workflow_id"], node_id="subject",
                actor="scheduler", reason="running", snapshot_sha256=digest,
                previous_state="eligible", next_state="running",
            )
            record_workflow_transition(
                workflow_dir, workflow_id=snapshot["workflow_id"], node_id="subject",
                actor="scheduler", reason="completed", snapshot_sha256=digest,
                previous_state="running", next_state="completed",
            )
            launched = []

            def launch(node, run_id):
                launched.append(run_id)
                write_run_contracts(settings.state_root / "runs" / run_id, session_id=run_id)
                return {"run_id": run_id}

            scheduler = SchedulerService(
                settings=settings,
                run_dir=workflow_dir,
                workdir=root,
                launch_fn=launch,
            )
            result = scheduler.launch_eligible(snapshot)
            status = scheduler.status(snapshot)
            states = {item["node_id"]: item["state"] for item in status["nodes"]}
            self.assertEqual(states["gate"], "completed")
            self.assertEqual(states["downstream"], "running")
            self.assertEqual(launched, ["approval-downstream"])
            self.assertEqual(result["plans"][0]["node_id"], "downstream")
            gate = next(item for item in status["nodes"] if item["node_id"] == "gate")
            self.assertEqual(
                gate["approval_receipt_sha256"],
                hashlib.sha256((subject_run / "receipts" / "000002-accepted.json").read_bytes()).hexdigest(),
            )

    def test_scheduler_rejected_or_tampered_gate_fails_downstream_closed(self):
        for disposition in ("rejected", "tampered"):
            with self.subTest(disposition=disposition), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                settings = replace(defaults(), state_root=root / "state")
                subject_run = _completed_run(root, "approval-subject")
                if disposition == "rejected":
                    record(settings, "approval-subject", action="rejected", actor="reviewer", reason="reject")
                else:
                    record(settings, "approval-subject", action="reviewed", actor="reviewer", reason="review")
                    record(
                        settings, "approval-subject", action="accepted", actor="reviewer",
                        reason="approved", revision="abc123",
                    )
                    receipt_path = subject_run / "receipts" / "000002-accepted.json"
                    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                    receipt["completion_sha256"] = "0" * 64
                    atomic_write_json(receipt_path, receipt)
                workflow_dir = root / "workflow"
                workflow_dir.mkdir()
                snapshot = normalize_snapshot(
                    {
                        "workflow_id": f"{disposition}-gate-workflow",
                        "pack_id": "pack",
                        "pack_manifest_sha256": "b" * 64,
                        "nodes": [
                            {"node_id": "subject", "session_id": "approval-subject", "prompt_path": "subject.md", "dependencies": []},
                            {"node_id": "gate", "kind": "approval", "approval_for": "subject", "dependencies": ["subject"]},
                            {"node_id": "downstream", "session_id": "approval-downstream", "prompt_path": "downstream.md", "dependencies": ["gate"]},
                        ],
                    }
                )
                digest = snapshot_sha256(snapshot)
                record_workflow_binding(
                    workflow_dir, workflow_id=snapshot["workflow_id"], node_id="subject",
                    run_id="approval-subject", attempt=1, actor="scheduler", reason="launch",
                    snapshot_sha256=digest,
                )
                record_workflow_transition(
                    workflow_dir, workflow_id=snapshot["workflow_id"], node_id="subject",
                    actor="scheduler", reason="running", snapshot_sha256=digest,
                    previous_state="eligible", next_state="running",
                )
                record_workflow_transition(
                    workflow_dir, workflow_id=snapshot["workflow_id"], node_id="subject",
                    actor="scheduler", reason="completed", snapshot_sha256=digest,
                    previous_state="running", next_state="completed",
                )
                scheduler = SchedulerService(
                    settings=settings, run_dir=workflow_dir, workdir=root,
                    launch_fn=lambda node, run_id: self.fail("downstream must not launch"),
                )
                result = scheduler.launch_eligible(snapshot)
                states = {item["node_id"]: item["state"] for item in scheduler.status(snapshot)["nodes"]}
                self.assertEqual(states["gate"], "failed")
                self.assertEqual(states["downstream"], "failed")
                self.assertEqual(result["plans"], [])
