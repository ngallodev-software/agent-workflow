"""Resolve launch prerequisites from live sealed lifecycle evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from .config import Settings
from .errors import WorkflowError
from .lifecycle import lifecycle_receipts
from .receipts import verify_seal_details
from .state import run_dir

PreflightStatus = Literal["accepted", "rejected", "missing", "stale"]


def resolve_prerequisites(settings: Settings, prerequisite_ids: list[str]) -> dict[str, Any]:
    """Resolve prerequisites without consulting mutable status projections."""
    if not prerequisite_ids:
        return {"schema": "agent-workflow/preflight/v1", "status": "accepted", "reason": "no prerequisites required", "prerequisites": []}
    results = [_resolve_single(settings, session_id) for session_id in prerequisite_ids]
    statuses = {item["status"] for item in results}
    if statuses == {"accepted"}:
        status: PreflightStatus = "accepted"
        reason = "all prerequisites accepted"
    elif "stale" in statuses:
        status = "stale"
        reason = "; ".join(item["reason"] for item in results if item["status"] == "stale")
    elif "missing" in statuses:
        status = "missing"
        reason = "; ".join(item["reason"] for item in results if item["status"] == "missing")
    else:
        status = "rejected"
        reason = "; ".join(item["reason"] for item in results if item["status"] != "accepted")
    return {"schema": "agent-workflow/preflight/v1", "status": status, "reason": reason, "prerequisites": results}


def _resolve_single(settings: Settings, session_id: str) -> dict[str, Any]:
    run = run_dir(settings, session_id)
    base = {"session_id": session_id}
    if not run.exists():
        return {**base, "status": "missing", "reason": f"prerequisite session not found: {session_id}"}
    if not (run / "final-receipt.json").exists():
        return {**base, "status": "missing", "reason": f"prerequisite has no sealed final receipt: {session_id}"}
    try:
        _final_receipt, final_digest = verify_seal_details(run)
        receipts = lifecycle_receipts(run, expected_final_receipt_sha256=final_digest)
    except WorkflowError as exc:
        return {**base, "status": "stale", "reason": f"prerequisite immutable evidence is stale: {exc}"}
    if not receipts:
        return {**base, "status": "missing", "reason": f"prerequisite has no lifecycle receipts: {session_id}"}
    latest = receipts[-1]
    action = latest["receipt"].get("action")
    evidence = {"receipt_sequence": latest["sequence"], "receipt_sha256": latest["sha256"], "final_receipt_sha256": final_digest}
    if action == "accepted":
        return {**base, "status": "accepted", "reason": "prerequisite accepted in current lifecycle receipt", **evidence}
    if action == "rejected":
        return {**base, "status": "rejected", "reason": f"prerequisite rejected: {latest['receipt'].get('reason', 'no reason provided')}", **evidence}
    return {**base, "status": "rejected", "reason": "prerequisite reviewed but not accepted", **evidence}


def preflight_error(preflight: dict[str, Any]) -> WorkflowError:
    return WorkflowError(f"launch preflight failed ({preflight.get('status')} prerequisites): {preflight.get('reason')}")


def preflight_run_record(*, session_id: str, ticket_id: str | None, pack_id: str | None, workdir: Path, prompt_path: Path, log_path: Path, preflight: dict[str, Any], created_at: str) -> dict[str, Any]:
    """Return a schema-valid terminal status for a rejected launch attempt."""
    return {"schema": "agent-workflow/session-status/v2", "session_id": session_id, "ticket_id": ticket_id, "pack_id": pack_id, "status": "failed", "failure_category": "preflight_failed", "preflight": preflight, "disposition": None, "created_at": created_at, "updated_at": created_at, "workdir": str(workdir), "prompt_path": str(prompt_path), "prompt_source": str(prompt_path), "log_path": str(log_path), "interactive": False, "executor_interactive": False, "tmux_session": None, "tmux_target": None, "tmux_pane_id": None, "tmux_mode": None, "final_receipt_path": None}
