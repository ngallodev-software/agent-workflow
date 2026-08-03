"""Append-only supplemental interpretation of sealed source evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from .config import Settings, enforce_trust
from .contracts import read_contract, validate_instance
from .errors import WorkflowError
from .index_sources import source_fingerprint
from .path import read_regular_file, require_directory
from .receipts import read_sealed_json, verify_seal_details
from .state import run_dir, runs_root
from .util import atomic_write_json, utc_now, validate_id

REPAIR_SCHEMA = "agent-workflow/evidence-repair/v1"
REPAIR_RECEIPT_SCHEMA = "agent-workflow/evidence-repair-receipt/v1"
ADAPTER_ID = "completion-normalize-v1"
ADAPTER_VERSION = "1"
ADAPTER_SPEC = {
    "id": ADAPTER_ID,
    "version": ADAPTER_VERSION,
    "purpose": "Normalize only completion identity/schema and review-disposition encoding.",
    "allowed_changes": ["schema", "session_id", "result", "review_disposition", "disposition"],
    "forbidden_changes": [
        "base_revision", "head_revision", "changed_files", "criteria", "commands",
        "unresolved", "ticket_id", "pack_id", "usage"
    ],
}
ADAPTER_SHA256 = hashlib.sha256(
    json.dumps(ADAPTER_SPEC, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def evidence_repairs_root(settings: Settings) -> Path:
    enforce_trust(settings)
    runs_root(settings)
    root = settings.state_root / "evidence-repairs"
    if root.exists() or root.is_symlink():
        if root.is_symlink() or not root.is_dir():
            raise WorkflowError(f"evidence repair root is unsafe: {root}")
    else:
        root.mkdir(mode=0o700)
    return require_directory(root, label="evidence repair root")


def repair_dir(settings: Settings, repair_id: str) -> Path:
    validate_id(repair_id, "repair ID")
    return evidence_repairs_root(settings) / repair_id


def _relative_artifact(value: str) -> str:
    path = PurePosixPath(value)
    if "\\" in value:
        raise WorkflowError("source artifact path must use normalized POSIX separators")
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise WorkflowError("source artifact path must be a normalized run-relative path")
    if path.as_posix() != value:
        raise WorkflowError("source artifact path must use normalized POSIX separators")
    return value


def _adapter_descriptor() -> dict[str, str]:
    return {"id": ADAPTER_ID, "version": ADAPTER_VERSION, "sha256": ADAPTER_SHA256}


def _normalize_completion(source: dict[str, Any], source_session_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    canonical = copy.deepcopy(source)
    differences: list[dict[str, Any]] = []

    def change(field: str, after: Any, *, remove: bool = False) -> None:
        before = canonical.get(field)
        if remove:
            canonical.pop(field, None)
        else:
            canonical[field] = after
        if before != after or remove:
            differences.append({
                "field": field,
                "before": before,
                "after": None if remove else after,
                "classification": "structural-normalization",
            })

    if canonical.get("schema") != "agent-workflow/completion/v1":
        change("schema", "agent-workflow/completion/v1")
    if canonical.get("session_id") is None:
        change("session_id", source_session_id)
    elif canonical.get("session_id") != source_session_id:
        raise WorkflowError("repair source completion session_id does not match source run")

    legacy_disposition = canonical.get("disposition")
    if legacy_disposition is not None:
        if legacy_disposition not in {"approved", "changes_requested", "blocked"}:
            raise WorkflowError("legacy completion disposition is unsupported")
        if canonical.get("review_disposition") not in {None, legacy_disposition}:
            raise WorkflowError("legacy and native review dispositions conflict")
        if canonical.get("review_disposition") is None:
            change("review_disposition", legacy_disposition)
        change("disposition", None, remove=True)

    result = canonical.get("result")
    if result == "changes_requested":
        change("result", "partial")
        if canonical.get("review_disposition") is None:
            change("review_disposition", "changes_requested")
    elif result == "approved":
        change("result", "completed")
        if canonical.get("review_disposition") is None:
            change("review_disposition", "approved")

    protected = (
        "base_revision", "head_revision", "changed_files", "criteria", "commands",
        "unresolved", "ticket_id", "pack_id", "usage"
    )
    for field in protected:
        if canonical.get(field) != source.get(field):
            raise WorkflowError(f"adapter attempted to change substantive completion field: {field}")

    validate_instance(canonical, "agent-workflow/completion/v1", artifact="repaired canonical completion")
    return canonical, differences


def _artifact_record(path: Path, root: Path) -> dict[str, Any]:
    read = read_regular_file(path)
    return {
        "path": path.relative_to(root).as_posix(),
        "size": len(read.data),
        "sha256": read.sha256,
    }


def _make_read_only(path: Path) -> None:
    info = path.stat()
    os.chmod(path, info.st_mode & ~0o222)


def _verify_repair_artifacts(root: Path, receipt: dict[str, Any]) -> None:
    expected_paths = {"adapter.json", "canonical-completion.json", "evidence-repair.json"}
    receipt_paths = [item["path"] for item in receipt["artifacts"]]
    if len(receipt_paths) != len(set(receipt_paths)) or set(receipt_paths) != expected_paths:
        raise WorkflowError("evidence repair receipt artifact set is invalid")
    for item in receipt["artifacts"]:
        relative = _relative_artifact(item["path"])
        path = root / relative
        read = read_regular_file(path)
        if len(read.data) != item["size"] or read.sha256 != item["sha256"]:
            raise WorkflowError(f"evidence repair artifact changed: {relative}")
        if read.mode & 0o222:
            raise WorkflowError(f"evidence repair artifact is writable: {relative}")


def verify_evidence_repair(settings: Settings, repair_id: str) -> dict[str, Any]:
    root = require_directory(repair_dir(settings, repair_id), label="evidence repair directory")
    receipt = read_contract(root / "repair-receipt.json", REPAIR_RECEIPT_SCHEMA)
    repair = read_contract(root / "evidence-repair.json", REPAIR_SCHEMA)
    if receipt["repair_id"] != repair_id or repair["repair_id"] != repair_id:
        raise WorkflowError("evidence repair identity mismatch")
    if receipt["source_session_id"] != repair["source"]["session_id"]:
        raise WorkflowError("evidence repair source identity mismatch")
    if receipt["source_final_receipt_sha256"] != repair["source"]["final_receipt_sha256"]:
        raise WorkflowError("evidence repair source receipt mismatch")
    _verify_repair_artifacts(root, receipt)
    source = run_dir(settings, repair["source"]["session_id"])
    _final, digest = verify_seal_details(
        source, expected_sha256=repair["source"]["final_receipt_sha256"]
    )
    if digest != receipt["source_final_receipt_sha256"]:
        raise WorkflowError("source final receipt changed after evidence repair")
    adapter_value = json.loads(read_regular_file(root / "adapter.json").data.decode("utf-8"))
    if adapter_value != ADAPTER_SPEC or repair["adapter"] != _adapter_descriptor():
        raise WorkflowError("evidence repair adapter identity changed")
    canonical_read = read_regular_file(root / "canonical-completion.json")
    if canonical_read.sha256 != repair["canonical"]["sha256"]:
        raise WorkflowError("evidence repair canonical digest changed")
    canonical = read_contract(root / "canonical-completion.json", "agent-workflow/completion/v1")
    if canonical["session_id"] != repair["source"]["session_id"]:
        raise WorkflowError("repaired completion source binding changed")
    return {
        "schema": REPAIR_SCHEMA,
        "repair_id": repair_id,
        "source_session_id": repair["source"]["session_id"],
        "source_final_receipt_sha256": digest,
        "source_artifact_path": repair["source"]["artifact_path"],
        "source_artifact_sha256": repair["source"]["artifact_sha256"],
        "adapter": repair["adapter"],
        "canonical_sha256": repair["canonical"]["sha256"],
        "validation_result": repair["canonical"]["validation_result"],
        "source_mutation_verified": repair["source_mutation_check"]["unchanged"],
        "receipt_path": str(root / "repair-receipt.json"),
        "repair_dir": str(root),
    }


def create_evidence_repair(
    settings: Settings,
    *,
    source_session_id: str,
    source_receipt_sha256: str,
    source_artifact_path: str,
    adapter: str,
    output_run: str,
    actor: str,
) -> dict[str, Any]:
    validate_id(source_session_id, "source run ID")
    validate_id(output_run, "repair ID")
    if not actor.strip():
        raise WorkflowError("evidence repair actor must be non-empty")
    if adapter != ADAPTER_ID:
        raise WorkflowError(f"unsupported evidence repair adapter: {adapter}")
    relative = _relative_artifact(source_artifact_path)
    source = run_dir(settings, source_session_id)
    final, digest = verify_seal_details(source, expected_sha256=source_receipt_sha256)
    sealed = {
        item.get("path"): item.get("sha256")
        for item in final.get("artifacts", [])
        if isinstance(item, dict)
    }
    source_artifact_sha256 = sealed.get(relative)
    if not isinstance(source_artifact_sha256, str):
        raise WorkflowError(f"source artifact is not sealed by the named receipt: {relative}")

    target = repair_dir(settings, output_run)
    if target.exists() or target.is_symlink():
        existing = verify_evidence_repair(settings, output_run)
        expected = (source_session_id, digest, relative, source_artifact_sha256, adapter)
        actual = (
            existing["source_session_id"], existing["source_final_receipt_sha256"],
            existing["source_artifact_path"], existing["source_artifact_sha256"],
            existing["adapter"]["id"],
        )
        if actual != expected:
            raise WorkflowError("repair ID already binds different source evidence")
        return {**existing, "idempotent": True}

    before = source_fingerprint(source)
    source_value, actual_source_sha256 = read_sealed_json(source, final, relative)
    if actual_source_sha256 != source_artifact_sha256:
        raise WorkflowError("sealed source artifact digest mismatch")
    if not isinstance(source_value, dict):
        raise WorkflowError("completion repair source artifact must be a JSON object")
    canonical, differences = _normalize_completion(source_value, source_session_id)

    target.mkdir(mode=0o700)
    try:
        atomic_write_json(target / "adapter.json", ADAPTER_SPEC)
        atomic_write_json(target / "canonical-completion.json", canonical)
        canonical_sha256 = read_regular_file(target / "canonical-completion.json").sha256
        after = source_fingerprint(source)
        if before != after:
            raise WorkflowError("source run changed while evidence repair was being prepared")
        repair = {
            "schema": REPAIR_SCHEMA,
            "repair_id": output_run,
            "created_at": utc_now(),
            "actor": actor,
            "source": {
                "session_id": source_session_id,
                "final_receipt_sha256": digest,
                "artifact_path": relative,
                "artifact_sha256": source_artifact_sha256,
            },
            "adapter": _adapter_descriptor(),
            "canonical": {
                "path": "canonical-completion.json",
                "sha256": canonical_sha256,
                "schema": "agent-workflow/completion/v1",
                "validation_result": "valid",
            },
            "original_interpretation": {
                "schema": source_value.get("schema"),
                "result": source_value.get("result"),
                "review_disposition": source_value.get("review_disposition") or source_value.get("disposition"),
            },
            "supplemental_interpretation": {
                "result": canonical["result"],
                "review_disposition": canonical.get("review_disposition"),
                "acceptance_authority": False,
            },
            "normalization_differences": differences,
            "source_mutation_check": {
                "fingerprint_before": before,
                "fingerprint_after": after,
                "unchanged": True,
            },
        }
        validate_instance(repair, REPAIR_SCHEMA, artifact="evidence repair")
        atomic_write_json(target / "evidence-repair.json", repair)
        artifacts = [
            _artifact_record(target / name, target)
            for name in ("adapter.json", "canonical-completion.json", "evidence-repair.json")
        ]
        receipt = {
            "schema": REPAIR_RECEIPT_SCHEMA,
            "repair_id": output_run,
            "source_session_id": source_session_id,
            "source_final_receipt_sha256": digest,
            "sealed_at": utc_now(),
            "artifacts": artifacts,
        }
        validate_instance(receipt, REPAIR_RECEIPT_SCHEMA, artifact="evidence repair receipt")
        atomic_write_json(target / "repair-receipt.json", receipt, mode=0o444)
        for name in ("adapter.json", "canonical-completion.json", "evidence-repair.json"):
            _make_read_only(target / name)
        return {**verify_evidence_repair(settings, output_run), "idempotent": False}
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise


def list_evidence_repairs(settings: Settings, *, source_session_id: str | None = None) -> list[dict[str, Any]]:
    if source_session_id is not None:
        validate_id(source_session_id, "source run ID")
    rows: list[dict[str, Any]] = []
    for path in sorted(evidence_repairs_root(settings).iterdir()):
        if path.is_symlink() or not path.is_dir():
            continue
        try:
            row = verify_evidence_repair(settings, path.name)
        except WorkflowError as exc:
            row = {
                "repair_id": path.name,
                "validation_result": "invalid",
                "error": str(exc),
                "repair_dir": str(path),
            }
            try:
                record = read_contract(path / "evidence-repair.json", REPAIR_SCHEMA)
                row["source_session_id"] = record["source"]["session_id"]
            except WorkflowError:
                pass
        if source_session_id is None or row.get("source_session_id") == source_session_id:
            rows.append(row)
    return rows


def supplemental_repairs_for_run(run: Path, receipt_sha256: str) -> list[dict[str, Any]]:
    """Return only cryptographically verified supplemental repairs for a sealed run."""
    try:
        source = require_directory(run, label="source run directory")
        final, digest = verify_seal_details(source, expected_sha256=receipt_sha256)
    except WorkflowError:
        return []
    sealed = {
        item.get("path"): item.get("sha256")
        for item in final.get("artifacts", [])
        if isinstance(item, dict)
    }
    root = source.parent.parent / "evidence-repairs"
    if not root.exists():
        return []
    try:
        root = require_directory(root, label="evidence repair root")
    except WorkflowError:
        return []

    rows: list[dict[str, Any]] = []
    for path in sorted(root.iterdir()):
        if path.is_symlink() or not path.is_dir():
            continue
        try:
            directory = require_directory(path, label="evidence repair directory")
            record = read_contract(directory / "evidence-repair.json", REPAIR_SCHEMA)
            receipt = read_contract(directory / "repair-receipt.json", REPAIR_RECEIPT_SCHEMA)
            if record["repair_id"] != path.name or receipt["repair_id"] != path.name:
                raise WorkflowError("evidence repair identity mismatch")
            if receipt["source_session_id"] != record["source"]["session_id"]:
                raise WorkflowError("evidence repair source identity mismatch")
            if receipt["source_final_receipt_sha256"] != record["source"]["final_receipt_sha256"]:
                raise WorkflowError("evidence repair source receipt mismatch")
            _verify_repair_artifacts(directory, receipt)
            adapter_value = json.loads(read_regular_file(directory / "adapter.json").data.decode("utf-8"))
            if adapter_value != ADAPTER_SPEC or record["adapter"] != _adapter_descriptor():
                raise WorkflowError("evidence repair adapter identity changed")
            canonical_read = read_regular_file(directory / "canonical-completion.json")
            if canonical_read.sha256 != record["canonical"]["sha256"]:
                raise WorkflowError("evidence repair canonical digest changed")
            canonical = read_contract(directory / "canonical-completion.json", "agent-workflow/completion/v1")
            if canonical["session_id"] != source.name:
                raise WorkflowError("repaired completion source binding changed")
            source_artifact = record["source"]["artifact_path"]
            if sealed.get(source_artifact) != record["source"]["artifact_sha256"]:
                raise WorkflowError("repair source artifact no longer matches sealed source receipt")
        except (WorkflowError, json.JSONDecodeError, OSError):
            continue
        if (
            record["source"]["session_id"] == source.name
            and record["source"]["final_receipt_sha256"] == digest
            and receipt["source_final_receipt_sha256"] == digest
        ):
            rows.append({
                "repair_id": record["repair_id"],
                "source_artifact_path": source_artifact,
                "source_artifact_sha256": record["source"]["artifact_sha256"],
                "adapter": record["adapter"],
                "canonical_sha256": record["canonical"]["sha256"],
                "validation_result": record["canonical"]["validation_result"],
                "acceptance_authority": False,
                "repair_path": str(directory),
            })
    return rows
