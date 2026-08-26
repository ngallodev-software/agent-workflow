"""Review-gate verification over one indexed Agent Run."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .config import Settings
from .errors import WorkflowError
from .lifecycle import lifecycle_receipts
from .receipts import read_sealed_contract, verify_seal_details
from .state import run_dir


def verify_review_projection(
    settings: Settings, connection: sqlite3.Connection, agent_run_id: str
) -> dict[str, Any]:
    """Verify one reviewed run without changing the global index verdict."""
    result: dict[str, Any] = {
        "review_scope": agent_run_id,
        "review_valid": False,
        "review_errors": [],
        "review_evidence": None,
    }
    try:
        row = connection.execute(
            "SELECT source_dir FROM runs WHERE agent_run_id=?", (agent_run_id,)
        ).fetchone()
        if row is None:
            raise WorkflowError("review target is not indexed")
        indexed = Path(str(row["source_dir"]))
        allowed = (run_dir(settings, agent_run_id), settings.state_root / "archive" / agent_run_id)
        target = next((candidate for candidate in allowed if candidate == indexed), None)
        if target is None or target.is_symlink() or not target.is_dir():
            raise WorkflowError("review target is outside trusted active/archive evidence")
        final_receipt, final_digest = verify_seal_details(target)
        if final_receipt.get("agent_run_id") != agent_run_id:
            raise WorkflowError("review final receipt belongs to another run")
        final_status, final_status_digest = read_sealed_contract(
            target, final_receipt, "final-status.json", "agent-workflow/agent-run-status/v1"
        )
        if final_status.get("agent_run_id") != agent_run_id or final_status.get("status") != "completed":
            raise WorkflowError("review target is not a completed run")
        completion, completion_digest = read_sealed_contract(
            target, final_receipt, "completion.json", "agent-workflow/completion/v1"
        )
        collection, collection_digest = read_sealed_contract(
            target, final_receipt, "collections/completion.json", "agent-workflow/completion-collection/v1"
        )
        if completion.get("result") != "completed" or completion.get("unresolved"):
            raise WorkflowError("review completion is not a successful direct gate")
        disposition = completion.get("review_disposition")
        if disposition is not None and disposition != "approved":
            raise WorkflowError(
                f"review completion disposition is not approved: {disposition}"
            )
        if any(item.get("result") != "pass" for item in completion.get("criteria", [])):
            raise WorkflowError("review completion contains a failed direct gate")
        if any(item.get("exit_code") != 0 for item in completion.get("commands", [])):
            raise WorkflowError("review completion contains a failed command gate")
        if collection.get("validation_status") != "valid":
            raise WorkflowError("review completion collection is not valid")
        if final_status.get("policy_result") == "failed":
            raise WorkflowError("review run failed execution policy")
        chain = lifecycle_receipts(target, expected_final_receipt_sha256=final_digest)
        if not chain or chain[-1]["receipt"].get("action") != "reviewed":
            raise WorkflowError("review target has no current reviewed lifecycle gate")
        reviewed = chain[-1]
        result["review_valid"] = True
        result["review_evidence"] = {
            "source_dir": str(target),
            "final_receipt_sha256": final_digest,
            "final_status_sha256": final_status_digest,
            "completion_sha256": completion_digest,
            "completion_collection_sha256": collection_digest,
            "review_receipt_sha256": reviewed["sha256"],
            "review_receipt_path": str(reviewed["path"]),
        }
    except (OSError, WorkflowError, KeyError, TypeError, ValueError) as exc:
        result["review_errors"] = [str(exc)]
    return result
