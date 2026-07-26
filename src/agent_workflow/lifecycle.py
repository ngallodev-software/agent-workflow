from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Literal

from .config import Settings
from .contracts import validate_instance
from .errors import WorkflowError
from .eval.scoring import validate_score_set
from .receipts import read_sealed_contract, verify_seal_details
from .state import run_dir, update_status
from .util import fsync_directory, utc_now
from .path_security import open_relative, validate_directory

Action = Literal["reviewed", "accepted", "rejected"]
_RECEIPT_NAME = re.compile(r"^(?P<sequence>[0-9]{6})-(?P<action>reviewed|accepted|rejected)\.json$")


def _read_lifecycle_receipt_descriptor(descriptor: int, display_name: str) -> tuple[dict[str, Any], str]:
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError("lifecycle receipt must be a regular non-symlink file")
        if info.st_mode & 0o222:
            raise WorkflowError("lifecycle receipt must be read-only")
        data = stream.read()
    try:
        receipt = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read lifecycle receipt {display_name}") from exc
    if not isinstance(receipt, dict):
        raise WorkflowError("lifecycle receipt must be a JSON object")
    validate_instance(
        receipt, "agent-workflow/lifecycle-receipt/v1", artifact="lifecycle receipt"
    )
    return receipt, hashlib.sha256(data).hexdigest()


def _read_lifecycle_receipt(path: Path) -> tuple[dict[str, Any], str]:
    """Read one lifecycle receipt with no-follow final-component protection."""
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise WorkflowError("cannot open lifecycle receipt") from exc
    return _read_lifecycle_receipt_descriptor(descriptor, path.name)


def lifecycle_receipts(run: Path, *, expected_final_receipt_sha256: str | None = None) -> list[dict[str, Any]]:
    """Reconstruct the immutable lifecycle receipt chain from its canonical directory.

    Mutable status fields are deliberately ignored. Every receipt must be a
    contiguous, read-only, regular file directly below ``receipts/`` and must
    identify the run whose directory contains it.
    """
    run = validate_directory(run, label="run directory")
    root = run / "receipts"
    if not root.exists() and not root.is_symlink():
        return []
    try:
        root_fd = os.open(
            root,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as exc:
        raise WorkflowError("lifecycle receipt root is unsafe") from exc
    entries: list[dict[str, Any]] = []
    try:
        names = sorted(os.listdir(root_fd))
        expected_sequence = 1
        for name in names:
            match = _RECEIPT_NAME.fullmatch(name)
            if match is None:
                raise WorkflowError("unexpected lifecycle receipt artifact")
            sequence = int(match.group("sequence"))
            if sequence != expected_sequence:
                raise WorkflowError(
                    f"lifecycle receipt sequence mismatch: expected {expected_sequence:06d}"
                )
            try:
                descriptor = open_relative(root_fd, name, flags=os.O_RDONLY)
            except OSError as exc:
                raise WorkflowError("lifecycle receipt entry is unsafe") from exc
            receipt, receipt_sha256 = _read_lifecycle_receipt_descriptor(descriptor, name)
            if receipt.get("action") != match.group("action"):
                raise WorkflowError("lifecycle receipt action does not match filename")
            if receipt.get("session_id") != run.name:
                raise WorkflowError("lifecycle receipt belongs to another run")
            if (
                expected_final_receipt_sha256 is not None
                and receipt.get("final_receipt_sha256") != expected_final_receipt_sha256
            ):
                raise WorkflowError("lifecycle receipt final-receipt digest mismatch")
            entries.append(
                {
                    "sequence": sequence,
                    "path": root / name,
                    "sha256": receipt_sha256,
                    "receipt": receipt,
                }
            )
            expected_sequence += 1
    finally:
        os.close(root_fd)
    return entries


def _read_score_set(path: Path) -> tuple[dict[str, Any], str]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WorkflowError(f"valid score set required: {path}: {exc}") from exc
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError(f"valid score set required: {path}: not a regular file")
        data = stream.read()
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"valid score set required: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"valid score set required: {path}: expected JSON object")
    return value, hashlib.sha256(data).hexdigest()


def _score(
    run: Path,
    final_hash: str,
    final_receipt: dict[str, Any],
    *,
    required: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    path = run / "scores" / "score-set.json"
    if not path.exists() and not path.is_symlink():
        if required:
            raise WorkflowError(f"valid score set required: {path}: file not found")
        return None, None
    value, score_digest = _read_score_set(path)
    value = validate_score_set(
        run,
        value,
        final_receipt=final_receipt,
        expected_final_receipt_sha256=final_hash,
    )
    return value, score_digest


def _append_receipt(run: Path, value: dict[str, Any]) -> Path:
    validate_instance(
        value, "agent-workflow/lifecycle-receipt/v1", artifact="lifecycle receipt"
    )
    root = run / "receipts"
    if root.exists() or root.is_symlink():
        try:
            root_info = root.lstat()
        except OSError as exc:
            raise WorkflowError(f"cannot inspect lifecycle receipt root {root}: {exc}") from exc
        if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
            raise WorkflowError(f"lifecycle receipt root is unsafe: {root}")
    else:
        root.mkdir(parents=True, mode=0o700)
        fsync_directory(run)
    sequence = len(lifecycle_receipts(run)) + 1
    path = root / f"{sequence:06d}-{value['action']}.json"
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o444)
    except FileExistsError as exc:
        raise WorkflowError(f"lifecycle receipt already exists: {path}") from exc
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    fsync_directory(root)
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
    run = run_dir(settings, session_id)
    final_receipt, expected = verify_seal_details(run)
    final_status, _ = read_sealed_contract(
        run,
        final_receipt,
        "final-status.json",
        "agent-workflow/session-status/v2",
    )
    if final_status.get("session_id") != session_id:
        raise WorkflowError("final status belongs to another run")
    if final_status.get("status") != "completed":
        raise WorkflowError("only a completed execution can be reviewed")
    sealed_paths = {
        item.get("path")
        for item in final_receipt.get("artifacts", [])
        if isinstance(item, dict)
    }
    evaluation_required = bool(final_status.get("evaluation_path")) or (
        "evaluation-runtime.json" in sealed_paths
    )
    score, score_hash = _score(
        run, expected, final_receipt, required=evaluation_required
    )
    completion, _ = read_sealed_contract(
        run,
        final_receipt,
        "completion.json",
        "agent-workflow/completion/v1",
    )
    collection, _ = read_sealed_contract(
        run,
        final_receipt,
        "collections/completion.json",
        "agent-workflow/completion-collection/v1",
    )
    chain = lifecycle_receipts(run, expected_final_receipt_sha256=expected)
    if chain and chain[-1]["receipt"].get("action") == "accepted":
        raise WorkflowError("lifecycle disposition is already terminal")
    independent = actor != final_status.get("executor")
    if action == "accepted":
        if not chain or chain[-1]["receipt"].get("action") != "reviewed":
            raise WorkflowError("acceptance requires a prior reviewed disposition")
        reviewed = chain[-1]["receipt"]
        if score is not None and score.get("verdict") != "pass":
            raise WorkflowError("acceptance requires a passing deterministic score set")
        if reviewed.get("score_receipt_sha256") != score_hash:
            raise WorkflowError("score set changed after review")
        if final_status.get("tier") in {"high", "critical"} and not reviewed.get(
            "reviewer_independent"
        ):
            raise WorkflowError(
                "high-risk acceptance requires an independent prior review"
            )
        if completion.get("result") != "completed":
            raise WorkflowError("acceptance requires completion result 'completed'")
        if collection.get("validation_status") != "valid":
            raise WorkflowError("acceptance requires a valid collected completion")
        if final_status.get("tier") not in {"low", "medium", "high", "critical"}:
            raise WorkflowError(
                "acceptance requires a recorded task tier; relaunch with --tier"
            )
        expected_revision = completion.get("head_revision")
        if not revision or revision != expected_revision:
            raise WorkflowError(
                f"accepted revision mismatch: {revision}; expected {expected_revision}"
            )
        if final_status.get("tier") in {"high", "critical"} and not independent:
            raise WorkflowError("high-risk acceptance requires an independent reviewer")
    elif action == "reviewed" and chain and chain[-1]["receipt"].get("action") == "reviewed":
        raise WorkflowError("run is already reviewed")
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
    projection_updates: dict[str, Any] = {
        "disposition": action,
        "disposition_at": value["created_at"],
        "disposition_actor": actor,
        "lifecycle_receipt_path": str(path),
    }
    if action == "accepted":
        projection_updates["accepted_revision"] = revision
    result = update_status(
        settings,
        session_id,
        **projection_updates,
        _actor=actor,
        _reason=reason,
        _receipt_refs=(str(path),),
    )
    return {**result, "lifecycle_receipt": str(path)}
