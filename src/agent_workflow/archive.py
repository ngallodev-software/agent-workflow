from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from . import tmux
from .config import Settings, enforce_trust
from .contracts import validate_instance
from .errors import WorkflowError
from .eval.scoring import validate_score_set
from .lifecycle import lifecycle_receipts
from .receipts import read_sealed_contract, verify_seal_details
from .state import list_statuses, run_dir, runs_root
from .util import atomic_write_json, fsync_directory, utc_now, validate_id


ARCHIVE_SCHEMA = "agent-workflow/run-archive/v1"


def _archive_root(settings: Settings) -> Path:
    enforce_trust(settings)
    runs_root(settings)
    root = settings.state_root / "archive"
    if root.exists() or root.is_symlink():
        if root.is_symlink() or not root.is_dir():
            raise WorkflowError(f"archive root is unsafe: {root}")
    else:
        root.mkdir(mode=0o700)
        fsync_directory(root.parent)
    return root


def _read_score_set(run: Path, path: Path, *, final_receipt: dict[str, Any], final_hash: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise WorkflowError(f"accepted run score set is missing or unsafe: {path}")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"accepted run score set is invalid: {path}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"accepted run score set must be an object: {path}")
    validate_score_set(
        run,
        value,
        final_receipt=final_receipt,
        expected_final_receipt_sha256=final_hash,
    )
    return digest


def verify_archive_candidate(settings: Settings, session_id: str) -> dict[str, Any]:
    """Verify the immutable acceptance chain before a run leaves ``runs/``."""
    validate_id(session_id, "session ID")
    source = run_dir(settings, session_id)
    if source.is_symlink() or not source.is_dir():
        raise WorkflowError(f"active run directory is missing or unsafe: {source}")

    final_receipt, final_hash = verify_seal_details(source)
    final_status, _ = read_sealed_contract(
        source, final_receipt, "final-status.json", "agent-workflow/session-status/v2"
    )
    if final_status.get("session_id") != session_id:
        raise WorkflowError("final status belongs to another run")
    if final_status.get("status") != "completed":
        raise WorkflowError("only completed runs can be archived")
    completion, _ = read_sealed_contract(
        source, final_receipt, "completion.json", "agent-workflow/completion/v1"
    )
    collection, _ = read_sealed_contract(
        source,
        final_receipt,
        "collections/completion.json",
        "agent-workflow/completion-collection/v1",
    )
    if completion.get("result") != "completed":
        raise WorkflowError("only runs with completed completion handoffs can be archived")
    if collection.get("validation_status") != "valid":
        raise WorkflowError("only runs with valid completion collections can be archived")

    chain = lifecycle_receipts(source, expected_final_receipt_sha256=final_hash)
    if not chain or chain[-1]["receipt"].get("action") != "accepted":
        raise WorkflowError("run has no authoritative accepted lifecycle receipt")
    accepted = chain[-1]["receipt"]
    if accepted.get("revision") != completion.get("head_revision"):
        raise WorkflowError("accepted revision does not match the completion handoff")
    score_hash = accepted.get("score_receipt_sha256")
    if score_hash is not None:
        actual_score_hash = _read_score_set(
            source,
            source / "scores" / "score-set.json",
            final_receipt=final_receipt,
            final_hash=final_hash,
        )
        if actual_score_hash != score_hash:
            raise WorkflowError("accepted score set changed after acceptance")

    host_session = final_status.get("tmux_session")
    if isinstance(host_session, str) and host_session:
        if shutil.which("tmux") is None:
            raise WorkflowError("cannot verify tmux closure because tmux is unavailable")
        if tmux.session_exists(host_session):
            raise WorkflowError(
                f"tmux session is still live; terminate it before archiving: {host_session}"
            )

    return {
        "session_id": session_id,
        "source": str(source),
        "final_receipt_sha256": final_hash,
        "accepted_revision": completion.get("head_revision"),
        "accepted_at": accepted.get("created_at"),
    }


def _archive_one(settings: Settings, candidate: dict[str, Any], *, reason: str) -> dict[str, Any]:
    source = Path(candidate["source"])
    root = _archive_root(settings)
    destination = root / candidate["session_id"]
    if destination.exists() or destination.is_symlink():
        raise WorkflowError(f"archive destination already exists: {destination}")
    try:
        os.rename(source, destination)
    except OSError as exc:
        raise WorkflowError(f"cannot move run into archive: {source} -> {destination}: {exc}") from exc
    fsync_directory(root)
    manifest = {
        "schema": ARCHIVE_SCHEMA,
        "session_id": candidate["session_id"],
        "source_run": str(source),
        "archived_run": str(destination),
        "archived_at": utc_now(),
        "reason": reason,
        "final_receipt_sha256": candidate["final_receipt_sha256"],
        "accepted_revision": candidate["accepted_revision"],
        "operation": "moved",
    }
    validate_instance(manifest, ARCHIVE_SCHEMA, artifact="archive manifest")
    atomic_write_json(destination / "archive-manifest.json", manifest, mode=0o444)
    return {**candidate, "archived": str(destination), "manifest": str(destination / "archive-manifest.json")}


def archive_runs(
    settings: Settings,
    session_ids: list[str],
    *,
    all_verified: bool = False,
    confirmed: bool = False,
    dry_run: bool = False,
    reason: str = "verified completed work no longer needed in the active run list",
) -> dict[str, Any]:
    if not session_ids and not all_verified:
        raise WorkflowError("provide one or more session IDs or use --all-verified")
    if session_ids and all_verified:
        raise WorkflowError("session IDs and --all-verified are mutually exclusive")
    if not dry_run and not confirmed:
        raise WorkflowError("archiving changes state; repeat with --verified")
    if not reason.strip():
        raise WorkflowError("archive reason must be non-empty")

    if all_verified:
        selected = sorted(
            {
                str(item.get("session_id"))
                for item in list_statuses(settings)
                if item.get("session_id")
            }
        )
    else:
        selected = list(dict.fromkeys(session_ids))

    eligible: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for session_id in selected:
        try:
            candidate = verify_archive_candidate(settings, session_id)
        except WorkflowError as exc:
            if not all_verified:
                raise WorkflowError(f"cannot archive {session_id}: {exc}") from exc
            skipped.append({"session_id": session_id, "reason": str(exc)})
        else:
            eligible.append(candidate)

    archived: list[dict[str, Any]] = []
    if not dry_run:
        for candidate in eligible:
            archived.append(_archive_one(settings, candidate, reason=reason))
    return {
        "archive_root": str(_archive_root(settings)),
        "dry_run": dry_run,
        "requested": selected,
        "eligible": [item["session_id"] for item in eligible],
        "archived": archived,
        "skipped": skipped,
    }
