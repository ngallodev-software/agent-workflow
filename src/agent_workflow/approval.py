from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .lifecycle import lifecycle_receipts
from .receipts import read_sealed_contract, verify_seal_details


def lifecycle_disposition(run_dir: Path) -> dict[str, Any] | None:
    """Return the latest canonical lifecycle disposition for a sealed child run."""
    run_dir = run_dir.resolve()
    final_receipt, expected = verify_seal_details(run_dir)
    if final_receipt.get("session_id") != run_dir.name:
        raise WorkflowError("approval final receipt belongs to another run")
    completion, completion_digest = read_sealed_contract(
        run_dir,
        final_receipt,
        "completion.json",
        "agent-workflow/completion/v1",
    )
    expected_revision = completion.get("head_revision")
    if not isinstance(expected_revision, str) or not expected_revision:
        raise WorkflowError("approval requires a completion head revision")
    chain = lifecycle_receipts(
        run_dir, expected_final_receipt_sha256=expected
    )
    if not chain:
        return None
    entry = chain[-1]
    receipt = entry["receipt"]
    if receipt.get("action") == "accepted":
        if receipt.get("revision") != expected_revision:
            raise WorkflowError("approval receipt revision mismatch")
        if len(chain) < 2 or chain[-2]["receipt"].get("action") != "reviewed":
            raise WorkflowError("accepted approval has no canonical prior review receipt")
        if (
            chain[-2]["receipt"].get("score_receipt_sha256")
            != receipt.get("score_receipt_sha256")
        ):
            raise WorkflowError("approval score evidence changed after review")
    return {
        "action": receipt["action"],
        "receipt": receipt,
        "receipt_path": str(entry["path"]),
        "receipt_name": entry["path"].name,
        "receipt_sha256": entry["sha256"],
        "final_receipt_sha256": expected,
        "final_receipt_path": str(run_dir / "final-receipt.json"),
        "completion_sha256": completion_digest,
        "revision": expected_revision,
    }


def accepted_lifecycle_receipt(run_dir: Path) -> dict[str, Any]:
    disposition = lifecycle_disposition(run_dir)
    if disposition is None:
        raise WorkflowError("approval requires a lifecycle receipt")
    if disposition["action"] != "accepted":
        raise WorkflowError("approval requires an accepted lifecycle receipt")
    return dict(disposition["receipt"])


def is_approved(run_dir: Path) -> bool:
    try:
        disposition = lifecycle_disposition(run_dir)
    except WorkflowError:
        return False
    return disposition is not None and disposition["action"] == "accepted"
