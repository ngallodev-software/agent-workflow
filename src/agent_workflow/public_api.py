"""Stable host-facing read contracts over existing Agent-Workflow authority."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_context import read as read_agent_context
from .agent_run_control import messages as read_messages
from .config import Settings
from .errors import WorkflowError
from .lifecycle import lifecycle_receipts
from .state import read_status, run_dir
from .steering import current_delivery
from .contracts import validate_instance

MESSAGES_SCHEMA = "agent-workflow/public-message-state/v1"
SUMMARY_SCHEMA = "agent-workflow/public-run-summary/v1"
PROVENANCE_SCHEMA = "agent-workflow/operator-provenance-view/v1"
MAX_PUBLIC_MESSAGES = 512


def _json_object(path: Path, *, missing_ok: bool = True) -> dict[str, Any] | None:
    if not path.is_file():
        if missing_ok:
            return None
        raise WorkflowError(f"required run artifact is missing: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read run artifact {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"run artifact must be a JSON object: {path.name}")
    return value


def message_state(settings: Settings, agent_run_id: str) -> dict[str, Any]:
    """Return bounded durable steering/message acknowledgement state."""
    root = run_dir(settings, agent_run_id)
    all_items = read_messages(settings, agent_run_id)
    truncated = len(all_items) > MAX_PUBLIC_MESSAGES
    items = all_items[-MAX_PUBLIC_MESSAGES:] if truncated else all_items
    acknowledgements = {
        str(item.get("correlation_id")): item
        for item in all_items
        if item.get("kind") == "ack" and item.get("correlation_id")
    }
    def project(item: dict[str, Any]) -> dict[str, Any]:
        message_id = str(item["message_id"])
        delivery = current_delivery(root, message_id)
        ack = acknowledgements.get(message_id)
        return {
            "message_id": message_id,
            "sequence": item["sequence"],
            "timestamp": item["timestamp"],
            "actor": item["actor"],
            "content": item["content"],
            "delivery_outcome": delivery.get("outcome") if delivery else None,
            "delivery_attempt": delivery.get("attempt") if delivery else None,
            "acknowledged": ack is not None,
            "ack_sequence": ack.get("sequence") if ack else None,
            "ack_actor": ack.get("actor") if ack else None,
            "ack_content": ack.get("content") if ack else None,
        }
    all_steering = []
    for item in all_items:
        if item.get("kind") != "steer":
            continue
        all_steering.append(project(item))
    steering = [project(item) for item in items if item.get("kind") == "steer"]
    pending_all = [
        item
        for item in all_steering
        if not item["acknowledged"]
        and item["delivery_outcome"] not in {"expired", "rejected", "applied"}
    ]
    result = {
        "schema": MESSAGES_SCHEMA,
        "agent_run_id": agent_run_id,
        "latest_sequence": max((int(item["sequence"]) for item in all_items), default=0),
        "truncated": truncated,
        "pending": [item for item in steering if not item["acknowledged"] and item["delivery_outcome"] not in {"expired", "rejected", "applied"}],
        "pending_count": len(pending_all),
        "pending_truncated": len(pending_all) > len([item for item in steering if not item["acknowledged"] and item["delivery_outcome"] not in {"expired", "rejected", "applied"}]),
        "steering": steering,
    }
    validate_instance(result, MESSAGES_SCHEMA, artifact="public message state")
    return result


def run_summary(settings: Settings, agent_run_id: str) -> dict[str, Any]:
    """Summarize completion, evaluation, review, and acceptance without new authority."""
    root = run_dir(settings, agent_run_id)
    status = read_status(settings, agent_run_id)
    final_status = _json_object(root / "final-status.json") or {}
    completion = _json_object(root / "completion.json")
    collection = _json_object(root / "collections" / "completion.json")
    score = _json_object(root / "scores" / "score-set.json")
    chain = lifecycle_receipts(
        root,
        expected_final_receipt_sha256=status.get("final_receipt_sha256"),
    )
    reviewed = next((item["receipt"] for item in reversed(chain) if item["receipt"].get("action") == "reviewed"), None)
    disposition = next((item["receipt"] for item in reversed(chain) if item["receipt"].get("action") in {"accepted", "rejected"}), None)
    try:
        context = read_agent_context(settings, agent_run_id)
    except WorkflowError:
        context = None
    result = {
        "schema": SUMMARY_SCHEMA,
        "agent_run_id": agent_run_id,
        "role": status.get("role"),
        "worker_mode": status.get("worker_mode"),
        "execution": {
            "status": status.get("status"),
            "disposition": status.get("disposition"),
            "failure_category": status.get("failure_category"),
            "final_receipt_sha256": status.get("final_receipt_sha256"),
        },
        "assignment": {
            "state": context.get("state") if context else None,
            "completed": bool(context and context.get("completed_assignment")),
        },
        "completion": {
            "present": completion is not None,
            "result": completion.get("result") if completion else None,
            "validation_status": (
                collection.get("validation_status") if collection else status.get("completion_validation_status")
            ),
            "head_revision": completion.get("head_revision") if completion else None,
        },
        "evaluation": {
            "present": score is not None,
            "state": status.get("evaluation_state"),
            "passed": score.get("passed") if score else None,
            "score": score.get("score") if score else None,
        },
        "review": {
            "state": "reviewed" if reviewed else None,
            "sequence": next((item["sequence"] for item in reversed(chain) if item["receipt"] is reviewed), None),
            "actor": reviewed.get("actor") if reviewed else None,
            "reason": reviewed.get("reason") if reviewed else None,
            "reviewer_independent": reviewed.get("reviewer_independent") if reviewed else None,
        },
        "acceptance": {
            "state": disposition.get("action") if disposition else None,
            "sequence": next((item["sequence"] for item in reversed(chain) if item["receipt"] is disposition), None),
            "actor": disposition.get("actor") if disposition else None,
            "reason": disposition.get("reason") if disposition else None,
            "reviewer_independent": disposition.get("reviewer_independent") if disposition else None,
        },
        "policy_result": final_status.get("policy_result", status.get("policy_result")),
    }
    validate_instance(result, SUMMARY_SCHEMA, artifact="public run summary")
    return result


def operator_provenance(settings: Settings, agent_run_id: str) -> dict[str, Any]:
    """Return explicit restricted provenance for integrations and operators."""
    root = run_dir(settings, agent_run_id)
    status = read_status(settings, agent_run_id)
    provenance = _json_object(root / "run-provenance.json", missing_ok=False) or {}
    result = {
        "schema": PROVENANCE_SCHEMA,
        "restricted": True,
        "agent_run_id": agent_run_id,
        "role": status.get("role"),
        "repository_root": status.get("repository_root"),
        "worktree": status.get("workdir"),
        "branch": status.get("branch"),
        "source_revision": status.get("source_revision"),
        "dirty_at_launch": status.get("dirty_at_launch"),
        "prompt_sha256": status.get("prompt_sha256"),
        "pack_id": status.get("pack_id"),
        "executor": provenance.get("executor"),
        "executor_version": provenance.get("executor_version"),
        "model": provenance.get("model"),
        "started_at": provenance.get("started_at"),
        "finished_at": provenance.get("finished_at"),
        "final_receipt_sha256": status.get("final_receipt_sha256"),
    }
    validate_instance(result, PROVENANCE_SCHEMA, artifact="operator provenance view")
    return result
