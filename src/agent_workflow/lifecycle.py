from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from .config import Settings
from .contracts import read_contract, validate_instance
from .errors import WorkflowError
from .eval.scoring import validate_score_set
from .receipts import verify_seal
from .state import read_status, run_dir, update_status
from .util import sha256_file, utc_now

Action = Literal["reviewed", "accepted", "rejected"]


def _score(
    run: Path, final_hash: str, final_receipt: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    path = run / "scores" / "score-set.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"valid score set required: {path}: {exc}") from exc
    value = validate_score_set(
        run,
        value,
        final_receipt=final_receipt,
        expected_final_receipt_sha256=final_hash,
    )
    return value, sha256_file(path)


def _append_receipt(run: Path, value: dict[str, Any]) -> Path:
    validate_instance(
        value, "agent-workflow/lifecycle-receipt/v1", artifact="lifecycle receipt"
    )
    root = run / "receipts"
    root.mkdir(parents=True, exist_ok=True)
    sequence = len(list(root.glob("[0-9]*-*.json"))) + 1
    path = root / f"{sequence:06d}-{value['action']}.json"
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    except FileExistsError as exc:
        raise WorkflowError(f"lifecycle receipt already exists: {path}") from exc
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def record(
    settings: Settings,
    session_id: str,
    *,
    action: Action,
    actor: str,
    reason: str,
    revision: str | None = None,
) -> dict[str, Any]:
    if not actor.strip() or not reason.strip():
        raise WorkflowError("lifecycle actor and reason must be non-empty")
    status = read_status(settings, session_id)
    if status.get("status") != "completed":
        raise WorkflowError("only a completed execution can be reviewed")
    run = run_dir(settings, session_id)
    expected = status.get("final_receipt_sha256")
    if not isinstance(expected, str):
        raise WorkflowError("status has no recorded final receipt checksum")
    final_receipt = verify_seal(run, expected_sha256=expected)
    score, score_hash = _score(run, expected, final_receipt)
    completion = read_contract(
        run / "completion.json", "agent-workflow/completion/v1"
    )
    independent = actor != status.get("executor")
    if action == "accepted":
        if status.get("disposition") != "reviewed":
            raise WorkflowError("acceptance requires a prior reviewed disposition")
        if score.get("verdict") != "pass":
            raise WorkflowError("acceptance requires a passing deterministic score set")
        reviewed_path = status.get("lifecycle_receipt_path")
        if not isinstance(reviewed_path, str):
            raise WorkflowError("acceptance requires the prior review receipt")
        reviewed = read_contract(
            Path(reviewed_path), "agent-workflow/lifecycle-receipt/v1"
        )
        if reviewed.get("score_receipt_sha256") != score_hash:
            raise WorkflowError("score set changed after review")
        if status.get("tier") in {"high", "critical"} and not reviewed.get(
            "reviewer_independent"
        ):
            raise WorkflowError(
                "high-risk acceptance requires an independent prior review"
            )
        if completion.get("result") != "completed":
            raise WorkflowError("acceptance requires completion result 'completed'")
        if status.get("tier") not in {"low", "medium", "high", "critical"}:
            raise WorkflowError(
                "acceptance requires a recorded task tier; relaunch with --tier"
            )
        expected_revision = completion.get("head_revision")
        if not revision or revision != expected_revision:
            raise WorkflowError(
                f"accepted revision mismatch: {revision}; expected {expected_revision}"
            )
        if status.get("tier") in {"high", "critical"} and not independent:
            raise WorkflowError("high-risk acceptance requires an independent reviewer")
    value = {
        "schema": "agent-workflow/lifecycle-receipt/v1",
        "session_id": session_id,
        "action": action,
        "actor": actor,
        "reason": reason,
        "created_at": utc_now(),
        "final_receipt_sha256": expected,
        "score_receipt_sha256": score_hash,
        "revision": revision,
        "reviewer_independent": independent,
    }
    path = _append_receipt(run, value)
    result = update_status(
        settings,
        session_id,
        disposition=action,
        disposition_at=value["created_at"],
        disposition_actor=actor,
        lifecycle_receipt_path=str(path),
        accepted_revision=revision if action == "accepted" else status.get("accepted_revision"),
        _actor=actor,
        _reason=reason,
        _receipt_refs=(str(path),),
    )
    return {**result, "lifecycle_receipt": str(path)}
