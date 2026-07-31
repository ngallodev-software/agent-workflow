from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .lifecycle import lifecycle_receipts
from .receipts import read_sealed_contract, verify_seal_details
from .state import TERMINAL_STATUSES, run_dir, read_status, update_status
from .util import fsync_directory, utc_now
from .contracts import validate_instance

_OVERRIDE_NAME = "force-accept-receipt.json"


def _read_override(run_dir: Path) -> tuple[dict[str, Any], str] | None:
    path = run_dir / _OVERRIDE_NAME
    if not path.exists() and not path.is_symlink():
        return None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise WorkflowError("force-accept receipt is unavailable") from exc
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o222:
            raise WorkflowError("force-accept receipt must be a read-only regular file")
        data = stream.read()
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError("force-accept receipt is invalid") from exc
    validate_instance(value, "agent-workflow/force-accept-receipt/v1", artifact="force-accept receipt")
    return value, hashlib.sha256(data).hexdigest()


def force_accept(
    settings: Any,
    session_id: str,
    *,
    actor: str,
    reason: str,
    acknowledgement: str,
    command: list[str],
) -> dict[str, Any]:
    if not actor.strip() or not reason.strip():
        raise WorkflowError("force-accept actor and reason must be non-empty")
    if acknowledgement != "FORCE-ACCEPT":
        raise WorkflowError("force-accept requires acknowledgement FORCE-ACCEPT")
    run = run_dir(settings, session_id)
    if _read_override(run) is not None:
        raise WorkflowError("force-accept override already exists")
    final_receipt, expected = verify_seal_details(run)
    if final_receipt.get("session_id") != session_id:
        raise WorkflowError("force-accept final receipt belongs to another run")
    final_status, _ = read_sealed_contract(run, final_receipt, "final-status.json", "agent-workflow/session-status/v2")
    if final_status.get("session_id") != session_id:
        raise WorkflowError("force-accept final status belongs to another run")
    if final_status.get("status") not in TERMINAL_STATUSES:
        raise WorkflowError("force-accept requires a terminal run")
    completion, _ = read_sealed_contract(run, final_receipt, "completion.json", "agent-workflow/completion/v1")
    collection, _ = read_sealed_contract(run, final_receipt, "collections/completion.json", "agent-workflow/completion-collection/v1")
    if not isinstance(completion, dict) or not isinstance(collection, dict):
        raise WorkflowError("force-accept requires valid completion evidence")
    chain = lifecycle_receipts(run, expected_final_receipt_sha256=expected)
    if chain and chain[-1]["receipt"].get("action") == "accepted":
        raise WorkflowError("lifecycle disposition is already terminal")
    failures: list[str] = []
    if not chain or chain[-1]["receipt"].get("action") != "reviewed":
        failures.append("acceptance requires a prior reviewed disposition")
    if completion.get("result") != "completed":
        failures.append("acceptance requires completion result 'completed'")
    if collection.get("validation_status") != "valid":
        failures.append("acceptance requires a valid collected completion")
    if final_status.get("tier") not in {"low", "medium", "high", "critical"}:
        failures.append("acceptance requires a recorded task tier")
    if not failures:
        failures.append("normal acceptance gate was not satisfied")
    encoded_command = json.dumps(command, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    value = {
        "schema": "agent-workflow/force-accept-receipt/v1",
        "session_id": session_id,
        "actor": actor,
        "created_at": utc_now(),
        "reason": reason,
        "acknowledgement": acknowledgement,
        "command": command,
        "command_sha256": hashlib.sha256(encoded_command).hexdigest(),
        "final_receipt_sha256": expected,
        "normal_gate_failures": sorted(set(failures)),
    }
    validate_instance(value, "agent-workflow/force-accept-receipt/v1", artifact="force-accept receipt")
    path = run / _OVERRIDE_NAME
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o444)
    except FileExistsError as exc:
        raise WorkflowError("force-accept override already exists") from exc
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    fsync_directory(run)
    result = update_status(
        settings, session_id, disposition="force-accepted", disposition_at=value["created_at"],
        disposition_actor=actor, force_accept_receipt_path=str(path),
        _actor=actor, _reason=reason, _receipt_refs=(str(path),),
    )
    return {**result, "force_accept_receipt": str(path), "normal_gate_failures": value["normal_gate_failures"]}


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
    override = _read_override(run_dir)
    if override is not None:
        override_receipt, override_digest = override
        if override_receipt.get("final_receipt_sha256") != expected:
            raise WorkflowError("force-accept receipt final-receipt digest mismatch")
        return {
            "action": "force-accepted", "receipt": override_receipt,
            "receipt_path": str(run_dir / _OVERRIDE_NAME), "receipt_name": _OVERRIDE_NAME,
            "receipt_sha256": override_digest, "final_receipt_sha256": expected,
            "final_receipt_path": str(run_dir / "final-receipt.json"),
            "completion_sha256": completion_digest, "revision": expected_revision,
        }
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
    return disposition is not None and disposition["action"] in {"accepted", "force-accepted"}
