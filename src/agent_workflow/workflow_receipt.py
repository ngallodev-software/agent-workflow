from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Mapping

from .contracts import read_contract, validate_instance
from .approval import lifecycle_disposition
from .errors import WorkflowError
from .receipts import read_sealed_contract, verify_seal_details
from .state import run_dir as session_run_dir
from .util import atomic_write_json, sha256_file, utc_now
from .workflow import (
    TERMINAL_NODE_STATES,
    normalize_snapshot,
    read_stored_workflow_snapshot,
    read_workflow_events,
    reconstruct_workflow_status,
    snapshot_sha256,
    workflow_events_path,
    workflow_lock,
    workflow_snapshot_path,
)

WORKFLOW_RECEIPT_SCHEMA = "agent-workflow/workflow-receipt/v1"


def workflow_receipt_path(run_dir: Path) -> Path:
    return Path(run_dir) / "workflow-receipt.json"


def _read_workflow_receipt(path: Path) -> tuple[dict[str, Any], str]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WorkflowError(f"cannot open workflow receipt {path}: {exc}") from exc
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError(f"workflow receipt must be a regular file: {path}")
        if info.st_mode & 0o222:
            raise WorkflowError("workflow receipt must be read-only")
        data = stream.read()
    try:
        receipt = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read workflow receipt {path}: {exc}") from exc
    if not isinstance(receipt, dict):
        raise WorkflowError(f"workflow receipt must be a JSON object: {path}")
    validate_instance(receipt, WORKFLOW_RECEIPT_SCHEMA, artifact=str(path))
    return receipt, hashlib.sha256(data).hexdigest()


def _binding_history(events_path: Path) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for event in read_workflow_events(events_path):
        if event.get("kind") != "node-bound":
            continue
        binding = event.get("binding")
        if not isinstance(binding, Mapping):
            raise WorkflowError("workflow node-bound event is missing binding")
        node_id = str(event.get("node_id", ""))
        result.setdefault(node_id, []).append(
            {
                "run_id": binding.get("run_id"),
                "attempt": binding.get("attempt"),
                "retry_of_run_id": binding.get("retry_of_run_id"),
                "bound_at": binding.get("bound_at"),
            }
        )
    return result


def _task_receipt(settings: Any, node_status: Mapping[str, Any]) -> dict[str, Any]:
    run_id = node_status.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        if node_status.get("state") == "completed":
            raise WorkflowError(
                f"completed task {node_status.get('node_id')} has no child run binding"
            )
        return {
            "child_run_id": None,
            "child_final_receipt_sha256": None,
            "child_completion_sha256": None,
        }
    child = session_run_dir(settings, run_id).resolve()
    receipt_path = child / "final-receipt.json"
    if not receipt_path.is_file():
        if node_status.get("state") == "completed":
            raise WorkflowError(f"completed task child run is not sealed: {run_id}")
        return {
            "child_run_id": run_id,
            "child_final_receipt_sha256": None,
            "child_completion_sha256": None,
        }
    final_receipt, expected = verify_seal_details(child)
    if final_receipt.get("session_id") != run_id:
        raise WorkflowError(f"child final receipt belongs to another run: {run_id}")
    _, completion_digest = read_sealed_contract(
        child,
        final_receipt,
        "completion.json",
        "agent-workflow/completion/v1",
    )
    return {
        "child_run_id": run_id,
        "child_final_receipt_sha256": expected,
        "child_completion_sha256": completion_digest,
    }


def _approval_receipt_digest(
    *,
    settings: Any,
    node: Mapping[str, Any],
    node_status: Mapping[str, Any],
    status_by_id: Mapping[str, Mapping[str, Any]],
) -> str | None:
    recorded = node_status.get("approval_receipt_sha256")
    if recorded is None:
        if node_status.get("state") == "completed":
            raise WorkflowError(
                f"completed approval node {node_status.get('node_id')} has no approval receipt digest"
            )
        return None
    if not isinstance(recorded, str) or not recorded:
        raise WorkflowError(
            f"approval node {node_status.get('node_id')} has an invalid receipt digest"
        )
    subject_id = str(node.get("approval_for", ""))
    subject_status = status_by_id.get(subject_id)
    run_id = subject_status.get("run_id") if isinstance(subject_status, Mapping) else None
    if not isinstance(run_id, str) or not run_id:
        raise WorkflowError(
            f"approval node {node_status.get('node_id')} has no authoritative subject run"
        )
    disposition = lifecycle_disposition(session_run_dir(settings, run_id))
    if disposition is None:
        raise WorkflowError(
            f"approval node {node_status.get('node_id')} has no canonical lifecycle disposition"
        )
    if disposition["receipt_sha256"] != recorded:
        raise WorkflowError(
            f"approval node {node_status.get('node_id')} receipt digest does not match canonical evidence"
        )
    expected_action = "accepted" if node_status.get("state") == "completed" else "rejected"
    if disposition["action"] != expected_action:
        raise WorkflowError(
            f"approval node {node_status.get('node_id')} terminal state contradicts canonical disposition"
        )
    return recorded


def _build_workflow_receipt_unlocked(
    *, settings: Any, run_dir: Path, created_at: str | None = None
) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    snapshot_path = workflow_snapshot_path(run_dir)
    events_path = workflow_events_path(run_dir)
    snapshot = read_stored_workflow_snapshot(snapshot_path)
    if not events_path.is_file():
        raise WorkflowError("workflow event journal is missing")
    status = reconstruct_workflow_status(snapshot, events_path)
    nonterminal = [
        item["node_id"]
        for item in status["nodes"]
        if item["state"] not in TERMINAL_NODE_STATES
    ]
    if nonterminal:
        raise WorkflowError(
            "workflow receipt requires terminal nodes; nonterminal: "
            + ", ".join(sorted(nonterminal))
        )
    histories = _binding_history(events_path)
    snapshot_nodes = {str(item["node_id"]): item for item in snapshot["nodes"]}
    status_by_id = {str(item["node_id"]): item for item in status["nodes"]}
    receipt_nodes: list[dict[str, Any]] = []
    for node_status in status["nodes"]:
        node_id = str(node_status["node_id"])
        node = snapshot_nodes[node_id]
        kind = str(node.get("kind", "task"))
        task_evidence = (
            _task_receipt(settings, node_status)
            if kind == "task"
            else {
                "child_run_id": None,
                "child_final_receipt_sha256": None,
                "child_completion_sha256": None,
            }
        )
        approval_digest = (
            _approval_receipt_digest(
                settings=settings,
                node=node,
                node_status=node_status,
                status_by_id=status_by_id,
            )
            if kind == "approval"
            else None
        )
        receipt_nodes.append(
            {
                "node_id": node_id,
                "kind": kind,
                "state": node_status["state"],
                "terminal_reason": node_status.get("terminal_reason"),
                "attempt": node_status.get("attempt"),
                "retry_of_run_id": node_status.get("retry_of_run_id"),
                "binding_history": histories.get(node_id, []),
                "input_binding_sha256": node_status.get("input_binding_sha256"),
                "approval_receipt_sha256": approval_digest,
                **task_evidence,
            }
        )
    receipt = {
        "schema": WORKFLOW_RECEIPT_SCHEMA,
        "workflow_id": snapshot["workflow_id"],
        "created_at": created_at or utc_now(),
        "workflow_state": status["workflow_state"],
        "snapshot_sha256": snapshot_sha256(snapshot),
        "snapshot_file_sha256": sha256_file(snapshot_path),
        "events_sha256": sha256_file(events_path),
        "event_count": status["event_count"],
        "node_count": len(receipt_nodes),
        "nodes": receipt_nodes,
    }
    validate_instance(receipt, WORKFLOW_RECEIPT_SCHEMA, artifact="workflow receipt")
    return receipt


def build_workflow_receipt(
    *, settings: Any, run_dir: Path, created_at: str | None = None
) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    with workflow_lock(run_dir, exclusive=False):
        return _build_workflow_receipt_unlocked(
            settings=settings, run_dir=run_dir, created_at=created_at
        )


def _verify_workflow_receipt_unlocked(*, settings: Any, run_dir: Path) -> dict[str, Any]:
    path = workflow_receipt_path(run_dir)
    receipt, receipt_digest = _read_workflow_receipt(path)
    rebuilt = _build_workflow_receipt_unlocked(
        settings=settings, run_dir=run_dir, created_at=str(receipt["created_at"])
    )
    if receipt != rebuilt:
        raise WorkflowError("workflow receipt does not match current durable evidence")
    return {
        "receipt": receipt,
        "receipt_path": str(path),
        "receipt_sha256": receipt_digest,
        "verified": True,
    }


def seal_workflow(*, settings: Any, run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    with workflow_lock(run_dir):
        path = workflow_receipt_path(run_dir)
        if path.exists() or path.is_symlink():
            return _verify_workflow_receipt_unlocked(
                settings=settings, run_dir=run_dir
            )
        receipt = _build_workflow_receipt_unlocked(settings=settings, run_dir=run_dir)
        atomic_write_json(path, receipt, mode=0o444)
        stored, receipt_digest = _read_workflow_receipt(path)
        if stored != receipt:
            raise WorkflowError("workflow receipt changed during atomic installation")
        return {
            "receipt": receipt,
            "receipt_path": str(path),
            "receipt_sha256": receipt_digest,
            "verified": True,
        }


def verify_workflow_receipt(*, settings: Any, run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    with workflow_lock(run_dir, exclusive=False):
        return _verify_workflow_receipt_unlocked(settings=settings, run_dir=run_dir)
