from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.approval import lifecycle_disposition
from agent_workflow.lifecycle import record
from agent_workflow.receipts import seal_run
from agent_workflow.util import atomic_write_json, sha256_file
from agent_workflow.workflow import (
    normalize_snapshot,
    record_workflow_binding,
    record_workflow_transition,
    snapshot_sha256,
    workflow_events_path,
    workflow_snapshot_path,
)
from agent_workflow.workflow_receipt import (
    build_workflow_receipt,
    seal_workflow,
    verify_workflow_receipt,
    workflow_receipt_path,
)
from run_fixtures import write_run_contracts


def _sealed_child(settings, run_id: str) -> Path:
    run = settings.state_root / "runs" / run_id
    write_run_contracts(run, session_id=run_id)
    completion = json.loads((run / "completion.json").read_text(encoding="utf-8"))
    completion.update(result="completed", head_revision="abc123", unresolved=[])
    atomic_write_json(run / "completion.json", completion)
    final_status = json.loads((run / "final-status.json").read_text(encoding="utf-8"))
    final_status.update(status="completed", disposition=None)
    atomic_write_json(run / "final-status.json", final_status)
    seal_run(run, session_id=run_id)
    status = json.loads((run / "status.json").read_text(encoding="utf-8"))
    status.update(
        status="completed",
        final_receipt_path=str(run / "final-receipt.json"),
        final_receipt_sha256=sha256_file(run / "final-receipt.json"),
    )
    atomic_write_json(run / "status.json", status)
    return run


def _terminal_workflow(root: Path):
    settings = replace(defaults(), state_root=root / "state")
    run_dir = root / "workflow"
    run_dir.mkdir()
    child = _sealed_child(settings, "child-one")
    snapshot = normalize_snapshot(
        {
            "workflow_id": "receipt-workflow",
            "pack_id": "receipt-pack",
            "pack_manifest_sha256": "a" * 64,
            "nodes": [
                {
                    "node_id": "build",
                    "session_id": "child-one",
                    "prompt_path": "tickets/build.md",
                    "dependencies": [],
                }
            ],
        }
    )
    atomic_write_json(workflow_snapshot_path(run_dir), snapshot)
    workflow_snapshot_path(run_dir).chmod(0o444)
    workflow_events_path(run_dir).touch()
    digest = snapshot_sha256(snapshot)
    record_workflow_binding(
        run_dir,
        workflow_id=snapshot["workflow_id"],
        node_id="build",
        run_id="child-one",
        attempt=1,
        actor="scheduler",
        reason="launch",
        snapshot_sha256=digest,
    )
    record_workflow_transition(
        run_dir,
        workflow_id=snapshot["workflow_id"],
        node_id="build",
        actor="scheduler",
        reason="running",
        snapshot_sha256=digest,
        previous_state="eligible",
        next_state="running",
    )
    record_workflow_transition(
        run_dir,
        workflow_id=snapshot["workflow_id"],
        node_id="build",
        actor="scheduler",
        reason="completed",
        snapshot_sha256=digest,
        previous_state="running",
        next_state="completed",
    )
    return settings, run_dir, child


def _accepted_child(settings, run_id: str) -> tuple[Path, dict[str, object]]:
    run = settings.state_root / "runs" / run_id
    write_run_contracts(run, session_id=run_id)
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
    final_status = json.loads((run / "final-status.json").read_text(encoding="utf-8"))
    final_status.update(status="completed", disposition=None)
    atomic_write_json(run / "final-status.json", final_status)
    seal_run(run, session_id=run_id)
    final_digest = sha256_file(run / "final-receipt.json")
    score_receipts = []
    for scorer_id in ("schema_validity", "acceptance_commands"):
        score = {
            "schema": "agent-workflow/score-receipt/v1",
            "scorer": {"id": scorer_id, "version": "1"},
            "final_receipt_sha256": final_digest,
            "verdict": "pass",
            "facts": {},
            "evidence": [],
        }
        encoded = json.dumps(score, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        atomic_write_json(run / "scores" / f"{scorer_id}-{digest}.json", score, mode=0o444)
        score_receipts.append(score)
    atomic_write_json(
        run / "scores" / "score-set.json",
        {
            "schema": "agent-workflow/score-set/v1",
            "final_receipt_sha256": final_digest,
            "verdict": "pass",
            "scores": score_receipts,
        },
    )
    status = json.loads((run / "status.json").read_text(encoding="utf-8"))
    status.update(
        status="completed",
        final_receipt_path=str(run / "final-receipt.json"),
        final_receipt_sha256=final_digest,
        tier="medium",
    )
    atomic_write_json(run / "status.json", status)
    record(settings, run_id, action="reviewed", actor="reviewer", reason="review")
    record(
        settings,
        run_id,
        action="accepted",
        actor="reviewer",
        reason="approved",
        revision="abc123",
    )
    disposition = lifecycle_disposition(run)
    assert disposition is not None
    return run, disposition


def _terminal_approval_workflow(root: Path):
    settings = replace(defaults(), state_root=root / "state")
    child, disposition = _accepted_child(settings, "approval-child")
    run_dir = root / "approval-workflow"
    run_dir.mkdir()
    snapshot = normalize_snapshot(
        {
            "workflow_id": "approval-receipt-workflow",
            "pack_id": "receipt-pack",
            "pack_manifest_sha256": "c" * 64,
            "nodes": [
                {
                    "node_id": "build",
                    "session_id": "approval-child",
                    "prompt_path": "build.md",
                    "dependencies": [],
                },
                {
                    "node_id": "approve",
                    "kind": "approval",
                    "approval_for": "build",
                    "dependencies": ["build"],
                },
            ],
        }
    )
    atomic_write_json(workflow_snapshot_path(run_dir), snapshot)
    workflow_snapshot_path(run_dir).chmod(0o444)
    workflow_events_path(run_dir).touch()
    digest = snapshot_sha256(snapshot)
    record_workflow_binding(
        run_dir,
        workflow_id=snapshot["workflow_id"],
        node_id="build",
        run_id="approval-child",
        attempt=1,
        actor="scheduler",
        reason="launch",
        snapshot_sha256=digest,
    )
    record_workflow_transition(
        run_dir,
        workflow_id=snapshot["workflow_id"],
        node_id="build",
        actor="scheduler",
        reason="running",
        snapshot_sha256=digest,
        previous_state="eligible",
        next_state="running",
    )
    record_workflow_transition(
        run_dir,
        workflow_id=snapshot["workflow_id"],
        node_id="build",
        actor="scheduler",
        reason="completed",
        snapshot_sha256=digest,
        previous_state="running",
        next_state="completed",
    )
    record_workflow_transition(
        run_dir,
        workflow_id=snapshot["workflow_id"],
        node_id="approve",
        actor="scheduler",
        reason="eligible",
        snapshot_sha256=digest,
        previous_state="blocked",
        next_state="eligible",
    )
    record_workflow_transition(
        run_dir,
        workflow_id=snapshot["workflow_id"],
        node_id="approve",
        actor="scheduler",
        reason="canonical lifecycle receipt accepted",
        snapshot_sha256=digest,
        previous_state="eligible",
        next_state="completed",
        details={
            "approval_for": "build",
            "subject_run_id": "approval-child",
            "approval_action": "accepted",
            "approval_receipt_sha256": disposition["receipt_sha256"],
            "final_receipt_sha256": disposition["final_receipt_sha256"],
            "completion_sha256": disposition["completion_sha256"],
            "revision": disposition["revision"],
        },
    )
    return settings, run_dir, child, disposition


class WorkflowReceiptTests(unittest.TestCase):
    def test_terminal_workflow_seals_and_verifies_all_child_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings, run_dir, child = _terminal_workflow(Path(tmp))
            evidence = seal_workflow(settings=settings, run_dir=run_dir)
            receipt = evidence["receipt"]
            self.assertTrue(evidence["verified"])
            self.assertEqual(receipt["workflow_state"], "completed")
            self.assertEqual(receipt["node_count"], 1)
            self.assertEqual(receipt["nodes"][0]["child_run_id"], "child-one")
            self.assertEqual(
                receipt["nodes"][0]["child_final_receipt_sha256"],
                sha256_file(child / "final-receipt.json"),
            )
            self.assertEqual(receipt["events_sha256"], sha256_file(workflow_events_path(run_dir)))
            self.assertEqual(verify_workflow_receipt(settings=settings, run_dir=run_dir)["receipt"], receipt)

    def test_partial_workflow_cannot_be_sealed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = replace(defaults(), state_root=root / "state")
            run_dir = root / "workflow"
            run_dir.mkdir()
            snapshot = normalize_snapshot(
                {
                    "workflow_id": "partial-workflow",
                    "pack_id": "pack",
                    "pack_manifest_sha256": "b" * 64,
                    "nodes": [
                        {
                            "node_id": "pending",
                            "session_id": "pending-run",
                            "prompt_path": "tickets/pending.md",
                            "dependencies": [],
                        }
                    ],
                }
            )
            atomic_write_json(workflow_snapshot_path(run_dir), snapshot)
            workflow_snapshot_path(run_dir).chmod(0o444)
            workflow_events_path(run_dir).touch()
            with self.assertRaisesRegex(WorkflowError, "requires terminal nodes"):
                build_workflow_receipt(settings=settings, run_dir=run_dir)

    def test_child_receipt_substitution_fails_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings, run_dir, child = _terminal_workflow(Path(tmp))
            seal_workflow(settings=settings, run_dir=run_dir)
            path = child / "final-receipt.json"
            os.chmod(path, 0o644)
            receipt = json.loads(path.read_text(encoding="utf-8"))
            receipt["sealed_at"] = "2099-01-01T00:00:00+00:00"
            atomic_write_json(path, receipt)
            os.chmod(path, 0o444)
            with self.assertRaisesRegex(WorkflowError, "durable evidence"):
                verify_workflow_receipt(settings=settings, run_dir=run_dir)

    def test_omitted_or_duplicate_nodes_fail_against_durable_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings, run_dir, _ = _terminal_workflow(Path(tmp))
            seal_workflow(settings=settings, run_dir=run_dir)
            path = workflow_receipt_path(run_dir)
            original = json.loads(path.read_text(encoding="utf-8"))
            for mutation in ("omit", "duplicate"):
                tampered = json.loads(json.dumps(original))
                if mutation == "omit":
                    tampered["nodes"] = []
                    tampered["node_count"] = 0
                else:
                    tampered["nodes"].append(dict(tampered["nodes"][0]))
                    tampered["node_count"] = 2
                os.chmod(path, 0o644)
                atomic_write_json(path, tampered)
                os.chmod(path, 0o444)
                with self.subTest(mutation=mutation):
                    with self.assertRaises(WorkflowError):
                        verify_workflow_receipt(settings=settings, run_dir=run_dir)
            os.chmod(path, 0o644)
            atomic_write_json(path, original)
            os.chmod(path, 0o444)
            self.assertTrue(verify_workflow_receipt(settings=settings, run_dir=run_dir)["verified"])

    def test_receipt_itself_must_be_canonical_regular_read_only_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings, run_dir, _ = _terminal_workflow(Path(tmp))
            seal_workflow(settings=settings, run_dir=run_dir)
            path = workflow_receipt_path(run_dir)
            os.chmod(path, 0o644)
            with self.assertRaisesRegex(WorkflowError, "read-only"):
                verify_workflow_receipt(settings=settings, run_dir=run_dir)

    def test_approval_evidence_is_reverified_when_workflow_receipt_is_built(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings, run_dir, _, disposition = _terminal_approval_workflow(Path(tmp))
            sealed = seal_workflow(settings=settings, run_dir=run_dir)
            approval = next(
                item for item in sealed["receipt"]["nodes"] if item["node_id"] == "approve"
            )
            self.assertEqual(
                approval["approval_receipt_sha256"], disposition["receipt_sha256"]
            )
            receipt_path = Path(disposition["receipt_path"])
            os.chmod(receipt_path, 0o644)
            value = json.loads(receipt_path.read_text(encoding="utf-8"))
            value["reason"] = "tampered after workflow transition"
            atomic_write_json(receipt_path, value)
            os.chmod(receipt_path, 0o444)
            with self.assertRaisesRegex(WorkflowError, "canonical evidence"):
                verify_workflow_receipt(settings=settings, run_dir=run_dir)


if __name__ == "__main__":
    unittest.main()
