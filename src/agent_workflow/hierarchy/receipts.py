"""Digest-sealed team and root receipts for bounded hierarchy v1."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from ..contracts import validate_instance
from ..errors import WorkflowError
from ..path import read_regular_file, require_directory
from ..util import atomic_write_json, validate_id, utc_now
from .contracts import (
    HIERARCHY_SCHEMA,
    read_contract_set,
    validate_hierarchy_contract,
    validate_team_delegation_contract,
)
from .journals import read_journal

TEAM_RECEIPT_SCHEMA = "agent-workflow/team-receipt/v1"
ROOT_RECEIPT_SCHEMA = "agent-workflow/root-orchestration-receipt/v1"
_DIGEST_PREFIX = "sha256:"
_TEAM_DISPOSITIONS = frozenset({"completed", "failed", "blocked", "cancelled", "rejected"})
_ROOT_OUTCOMES = frozenset({"completed", "failed", "blocked", "cancelled", "partial"})
_BUDGET_USAGE_KEYS = frozenset(
    {
        "workers_started",
        "peak_concurrent_workers",
        "peak_interactive_panes",
        "retries",
        "wall_seconds",
    }
)


@dataclass(frozen=True)
class EvidenceReference:
    """One exact immutable file relative to a caller-supplied evidence root."""

    kind: str
    path: str


@dataclass(frozen=True)
class JournalReference:
    """One exact hierarchy journal relative to the orchestration root."""

    label: str
    journal_id: str
    path: str


def _canonical_bytes(value: Mapping[str, Any], *, omit: str) -> bytes:
    material = copy.deepcopy(dict(value))
    material.pop(omit, None)
    return json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _identity_digest(value: Mapping[str, Any], *, omit: str) -> str:
    return _DIGEST_PREFIX + hashlib.sha256(_canonical_bytes(value, omit=omit)).hexdigest()


def _validate_receipt_digest(value: Mapping[str, Any], *, field: str, label: str) -> None:
    expected = _identity_digest(value, omit=field)
    if value.get(field) != expected:
        raise WorkflowError(f"{label} digest mismatch: expected {expected}, got {value.get(field)}")


def _relative(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise WorkflowError(f"invalid {label}: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(part in {"", ".", ".."} for part in path.parts):
        raise WorkflowError(f"invalid {label}: {value!r}")
    return value


def _read_readonly_file(root: Path, relative: str, *, label: str) -> tuple[bytes, str, int]:
    relative = _relative(relative, label=label)
    read = read_regular_file(require_directory(root, label=f"{label} root") / relative)
    if read.mode & 0o222:
        raise WorkflowError(f"{label} must be read-only: {relative}")
    return read.data, _DIGEST_PREFIX + read.sha256, read.size


def _read_readonly_json(path: Path, *, label: str) -> dict[str, Any]:
    read = read_regular_file(path)
    if read.mode & 0o222:
        raise WorkflowError(f"{label} must be read-only: {path}")
    try:
        value = json.loads(read.data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"invalid {label} JSON: {path}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{label} must be an object: {path}")
    return value


def _encoded_json(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(value), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _install_receipt(path: Path, value: Mapping[str, Any]) -> None:
    expected = _encoded_json(value)
    if path.exists() or path.is_symlink():
        read = read_regular_file(path)
        if read.mode & 0o222:
            raise WorkflowError(f"hierarchy receipt must be read-only: {path}")
        if read.data != expected:
            raise WorkflowError(f"immutable hierarchy receipt already differs: {path}")
        return
    require_directory(path.parent, label="hierarchy receipt parent")
    atomic_write_json(path, dict(value), mode=0o400)
    read = read_regular_file(path)
    if read.mode & 0o222 or read.data != expected:
        raise WorkflowError(f"failed to install immutable hierarchy receipt: {path}")


def _artifact_descriptor(root: Path, reference: EvidenceReference) -> dict[str, Any]:
    if not isinstance(reference, EvidenceReference):
        raise WorkflowError("invalid hierarchy evidence reference")
    if not reference.kind or len(reference.kind) > 128:
        raise WorkflowError(f"invalid hierarchy evidence kind: {reference.kind!r}")
    _, digest, size = _read_readonly_file(
        root,
        reference.path,
        label=f"hierarchy evidence {reference.kind}",
    )
    return {
        "kind": reference.kind,
        "path": reference.path,
        "sha256": digest,
        "size": size,
    }


def _verify_artifact_descriptor(root: Path, descriptor: Mapping[str, Any], *, label: str) -> None:
    kind = descriptor.get("kind")
    path = descriptor.get("path")
    if not isinstance(kind, str) or not isinstance(path, str):
        raise WorkflowError(f"invalid {label} descriptor")
    _, digest, size = _read_readonly_file(root, path, label=f"{label} {kind}")
    if descriptor.get("sha256") != digest or descriptor.get("size") != size:
        raise WorkflowError(f"{label} digest or size mismatch: {path}")


def _journal_descriptor(
    root: Path,
    reference: JournalReference,
    *,
    allowed_team_ids: frozenset[str],
) -> dict[str, Any]:
    if not isinstance(reference, JournalReference):
        raise WorkflowError("invalid hierarchy journal reference")
    validate_id(reference.label, "journal label")
    validate_id(reference.journal_id, "journal id")
    relative = _relative(reference.path, label="hierarchy journal path")
    path = require_directory(root, label="orchestration root") / relative
    records = read_journal(path, expected_journal_id=reference.journal_id)
    unexpected_teams = sorted(
        {
            record["team_id"]
            for record in records
            if record["team_id"] is not None and record["team_id"] not in allowed_team_ids
        }
    )
    if unexpected_teams:
        raise WorkflowError(
            "hierarchy journal contains out-of-scope team identities: "
            + ", ".join(unexpected_teams)
        )
    read = read_regular_file(path)
    return {
        "label": reference.label,
        "journal_id": reference.journal_id,
        "path": relative,
        "record_count": len(records),
        "last_message_id": records[-1]["message_id"] if records else None,
        "sha256": _DIGEST_PREFIX + read.sha256,
        "size": read.size,
    }


def _verify_journal_descriptor(
    root: Path,
    descriptor: Mapping[str, Any],
    *,
    allowed_team_ids: frozenset[str],
) -> None:
    journal_id = descriptor.get("journal_id")
    relative = descriptor.get("path")
    if not isinstance(journal_id, str) or not isinstance(relative, str):
        raise WorkflowError("invalid hierarchy journal descriptor")
    path = require_directory(root, label="orchestration root") / _relative(
        relative, label="hierarchy journal path"
    )
    records = read_journal(path, expected_journal_id=journal_id)
    unexpected_teams = sorted(
        {
            record["team_id"]
            for record in records
            if record["team_id"] is not None and record["team_id"] not in allowed_team_ids
        }
    )
    if unexpected_teams:
        raise WorkflowError(
            "hierarchy journal contains out-of-scope team identities: "
            + ", ".join(unexpected_teams)
        )
    read = read_regular_file(path)
    expected_last = records[-1]["message_id"] if records else None
    if (
        descriptor.get("record_count") != len(records)
        or descriptor.get("last_message_id") != expected_last
        or descriptor.get("sha256") != _DIGEST_PREFIX + read.sha256
        or descriptor.get("size") != read.size
    ):
        raise WorkflowError(f"hierarchy journal changed after receipt sealing: {relative}")


def _unique_descriptors(values: Iterable[Mapping[str, Any]], *, keys: tuple[str, ...], label: str) -> None:
    seen: set[tuple[Any, ...]] = set()
    for value in values:
        key = tuple(value.get(item) for item in keys)
        if key in seen:
            raise WorkflowError(f"duplicate {label}: {key}")
        seen.add(key)


def _validated_text_list(values: Iterable[str], *, label: str) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise WorkflowError(f"{label} must be a list of strings")
    result = list(values)
    if any(not isinstance(item, str) or not item or len(item) > 8192 for item in result):
        raise WorkflowError(f"{label} must contain bounded non-empty strings")
    if len(result) != len(set(result)):
        raise WorkflowError(f"{label} must not contain duplicates")
    return result


def _validate_budget_usage(
    usage: Mapping[str, Any],
    team_contract: Mapping[str, Any],
    *,
    worker_count: int,
) -> dict[str, int]:
    result = dict(usage)
    if set(result) != _BUDGET_USAGE_KEYS or any(
        type(value) is not int or value < 0 for value in result.values()
    ):
        raise WorkflowError("team receipt budget_usage has invalid fields or values")
    if result["workers_started"] != worker_count:
        raise WorkflowError(
            "team receipt workers_started must equal the exact sealed worker evidence set"
        )
    if result["peak_concurrent_workers"] > result["workers_started"]:
        raise WorkflowError("team receipt peak_concurrent_workers exceeds workers_started")
    limits = team_contract["budgets"]
    comparisons = {
        "workers_started": "max_workers",
        "peak_concurrent_workers": "max_concurrent_workers",
        "peak_interactive_panes": "max_interactive_panes",
        "retries": "max_retries",
        "wall_seconds": "max_wall_seconds",
    }
    for used_key, limit_key in comparisons.items():
        if result[used_key] > limits[limit_key]:
            raise WorkflowError(f"team receipt budget usage exceeds {limit_key}")
    return result


def _validate_worker_evidence(
    workers: Iterable[Mapping[str, Any]],
    team_contract: Mapping[str, Any],
) -> None:
    seen_workers: set[str] = set()
    seen_paths: set[str] = set()
    required_outputs = set(team_contract["required_outputs"])
    for worker in workers:
        run_id = worker.get("run_id")
        if not isinstance(run_id, str):
            raise WorkflowError("team receipt worker has no string run_id")
        validate_id(run_id, "worker run id")
        if run_id in seen_workers:
            raise WorkflowError(f"duplicate worker in team receipt: {run_id}")
        seen_workers.add(run_id)
        artifacts = worker.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise WorkflowError(f"worker evidence set is empty: {run_id}")
        _unique_descriptors(artifacts, keys=("kind",), label=f"worker {run_id} evidence kind")
        _unique_descriptors(artifacts, keys=("path",), label=f"worker {run_id} evidence path")
        kinds = {item.get("kind") for item in artifacts}
        missing = sorted(required_outputs - kinds)
        if missing:
            raise WorkflowError(
                f"worker {run_id} evidence is missing required outputs: {', '.join(missing)}"
            )
        for artifact in artifacts:
            path = artifact.get("path")
            if not isinstance(path, str):
                raise WorkflowError(f"worker {run_id} evidence has no string path")
            if path in seen_paths:
                raise WorkflowError(f"evidence path is assigned more than once: {path}")
            seen_paths.add(path)


def _validate_required_evidence_kinds(
    descriptors: Iterable[Mapping[str, Any]],
    required: Iterable[str],
    *,
    label: str,
) -> None:
    present = {item.get("kind") for item in descriptors}
    missing = sorted(set(required) - present)
    if missing:
        raise WorkflowError(f"{label} is missing required kinds: {', '.join(missing)}")


def create_team_receipt(
    orchestration_root: Path,
    evidence_root: Path,
    hierarchy: Mapping[str, Any],
    team_contract: Mapping[str, Any],
    *,
    journals: Iterable[JournalReference],
    workers: Mapping[str, Iterable[EvidenceReference]],
    review_evidence: Iterable[EvidenceReference] = (),
    unresolved_issues: Iterable[str] = (),
    scope_deviations: Iterable[str] = (),
    budget_usage: Mapping[str, int],
    terminal_disposition: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create and install one immutable team fan-in receipt."""
    validate_hierarchy_contract(hierarchy)
    validate_team_delegation_contract(team_contract, hierarchy)
    team_id = team_contract["team_id"]
    root = require_directory(Path(orchestration_root), label="orchestration root")
    evidence_root = require_directory(Path(evidence_root), label="hierarchy evidence root")
    contract_relative = f"teams/{team_id}/delegation-contract.json"
    contract_data, contract_file_digest, contract_size = _read_readonly_file(
        root, contract_relative, label="team delegation contract"
    )
    try:
        installed_contract = json.loads(contract_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError("installed team delegation contract is invalid JSON") from exc
    if installed_contract != dict(team_contract):
        raise WorkflowError("installed team delegation contract does not match receipt input")

    journal_rows = [
        _journal_descriptor(root, item, allowed_team_ids=frozenset({team_id}))
        for item in journals
    ]
    _unique_descriptors(journal_rows, keys=("label",), label="team journal label")
    _unique_descriptors(journal_rows, keys=("path",), label="team journal path")

    worker_rows: list[dict[str, Any]] = []
    for run_id in sorted(workers):
        validate_id(run_id, "worker run id")
        artifacts = [_artifact_descriptor(evidence_root, item) for item in workers[run_id]]
        if not artifacts:
            raise WorkflowError(f"worker evidence set is empty: {run_id}")
        _unique_descriptors(artifacts, keys=("kind",), label=f"worker {run_id} evidence kind")
        _unique_descriptors(artifacts, keys=("path",), label=f"worker {run_id} evidence path")
        worker_rows.append({"run_id": run_id, "artifacts": artifacts})
    _validate_worker_evidence(worker_rows, team_contract)

    review_rows = [_artifact_descriptor(evidence_root, item) for item in review_evidence]
    _unique_descriptors(review_rows, keys=("kind",), label="team review evidence kind")
    _unique_descriptors(review_rows, keys=("path",), label="team review evidence path")
    _validate_required_evidence_kinds(
        review_rows,
        team_contract["required_reviews"],
        label="team review evidence",
    )
    worker_paths = {
        artifact["path"] for worker in worker_rows for artifact in worker["artifacts"]
    }
    overlap = sorted(worker_paths & {item["path"] for item in review_rows})
    if overlap:
        raise WorkflowError(
            "team review evidence overlaps worker evidence: " + ", ".join(overlap)
        )
    issues = _validated_text_list(unresolved_issues, label="team receipt unresolved_issues")
    deviations = _validated_text_list(scope_deviations, label="team receipt scope_deviations")
    usage = _validate_budget_usage(
        budget_usage,
        team_contract,
        worker_count=len(worker_rows),
    )
    if terminal_disposition not in _TEAM_DISPOSITIONS:
        raise WorkflowError(f"invalid team terminal disposition: {terminal_disposition!r}")

    receipt = {
        "schema": TEAM_RECEIPT_SCHEMA,
        "version": 1,
        "orchestration_id": hierarchy["orchestration_id"],
        "team_id": team_id,
        "hierarchy_identity_sha256": hierarchy["identity_sha256"],
        "delegation_contract": {
            "path": contract_relative,
            "contract_sha256": team_contract["contract_sha256"],
            "file_sha256": contract_file_digest,
            "size": contract_size,
        },
        "journals": sorted(journal_rows, key=lambda item: item["label"]),
        "workers": worker_rows,
        "review_evidence": sorted(review_rows, key=lambda item: (item["kind"], item["path"])),
        "unresolved_issues": issues,
        "scope_deviations": deviations,
        "budget_usage": usage,
        "terminal_disposition": terminal_disposition,
        "created_at": created_at or utc_now(),
    }
    receipt["receipt_sha256"] = _identity_digest(receipt, omit="receipt_sha256")
    validate_instance(receipt, TEAM_RECEIPT_SCHEMA, artifact=f"team receipt {team_id}")
    path = root / f"teams/{team_id}/team-receipt.json"
    _install_receipt(path, receipt)
    return verify_team_receipt(root, evidence_root, hierarchy, team_contract)


def verify_team_receipt(
    orchestration_root: Path,
    evidence_root: Path,
    hierarchy: Mapping[str, Any],
    team_contract: Mapping[str, Any],
    *,
    receipt_path: str | None = None,
) -> dict[str, Any]:
    """Verify one team receipt and every file it seals."""
    validate_hierarchy_contract(hierarchy)
    validate_team_delegation_contract(team_contract, hierarchy)
    root = require_directory(Path(orchestration_root), label="orchestration root")
    evidence_root = require_directory(Path(evidence_root), label="hierarchy evidence root")
    team_id = team_contract["team_id"]
    relative = receipt_path or f"teams/{team_id}/team-receipt.json"
    receipt = _read_readonly_json(root / _relative(relative, label="team receipt path"), label="team receipt")
    validate_instance(receipt, TEAM_RECEIPT_SCHEMA, artifact=relative)
    _validate_receipt_digest(receipt, field="receipt_sha256", label="team receipt")
    if (
        receipt["orchestration_id"] != hierarchy["orchestration_id"]
        or receipt["team_id"] != team_id
        or receipt["hierarchy_identity_sha256"] != hierarchy["identity_sha256"]
    ):
        raise WorkflowError("team receipt identity does not match hierarchy contract")

    contract_descriptor = receipt["delegation_contract"]
    expected_contract_path = f"teams/{team_id}/delegation-contract.json"
    if contract_descriptor["path"] != expected_contract_path:
        raise WorkflowError("team receipt contains an unexpected delegation contract path")
    contract_data, file_digest, size = _read_readonly_file(
        root, contract_descriptor["path"], label="team delegation contract"
    )
    try:
        installed_contract = json.loads(contract_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError("installed team delegation contract is invalid JSON") from exc
    if installed_contract != dict(team_contract):
        raise WorkflowError("team receipt delegation contract does not match expected contract")
    if (
        contract_descriptor["contract_sha256"] != team_contract["contract_sha256"]
        or contract_descriptor["file_sha256"] != file_digest
        or contract_descriptor["size"] != size
    ):
        raise WorkflowError("team receipt delegation contract digest mismatch")

    _unique_descriptors(receipt["journals"], keys=("label",), label="team journal label")
    _unique_descriptors(receipt["journals"], keys=("path",), label="team journal path")
    for descriptor in receipt["journals"]:
        validate_id(descriptor["label"], "journal label")
        validate_id(descriptor["journal_id"], "journal id")
        _verify_journal_descriptor(
            root,
            descriptor,
            allowed_team_ids=frozenset({team_id}),
        )
    _validate_worker_evidence(receipt["workers"], team_contract)
    for worker in receipt["workers"]:
        run_id = worker["run_id"]
        for descriptor in worker["artifacts"]:
            _verify_artifact_descriptor(evidence_root, descriptor, label=f"worker {run_id} evidence")
    _unique_descriptors(receipt["review_evidence"], keys=("kind",), label="team review evidence kind")
    _unique_descriptors(receipt["review_evidence"], keys=("path",), label="team review evidence path")
    _validate_required_evidence_kinds(
        receipt["review_evidence"],
        team_contract["required_reviews"],
        label="team review evidence",
    )
    for descriptor in receipt["review_evidence"]:
        _verify_artifact_descriptor(evidence_root, descriptor, label="team review evidence")
    worker_paths = {
        artifact["path"] for worker in receipt["workers"] for artifact in worker["artifacts"]
    }
    overlap = sorted(worker_paths & {item["path"] for item in receipt["review_evidence"]})
    if overlap:
        raise WorkflowError(
            "team review evidence overlaps worker evidence: " + ", ".join(overlap)
        )
    _validate_budget_usage(
        receipt["budget_usage"],
        team_contract,
        worker_count=len(receipt["workers"]),
    )
    if receipt["terminal_disposition"] not in _TEAM_DISPOSITIONS:
        raise WorkflowError("invalid team terminal disposition")
    return receipt


def create_root_receipt(
    orchestration_root: Path,
    evidence_root: Path,
    *,
    root_journals: Iterable[JournalReference],
    cross_team_bindings: Iterable[EvidenceReference] = (),
    approval_evidence: Iterable[EvidenceReference] = (),
    unresolved_issues: Iterable[str] = (),
    outcome: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create and install the immutable root orchestration receipt."""
    root = require_directory(Path(orchestration_root), label="orchestration root")
    evidence_root = require_directory(Path(evidence_root), label="hierarchy evidence root")
    hierarchy, teams, manifest = read_contract_set(root)
    team_by_id = {item["team_id"]: item for item in teams}

    hierarchy_data, hierarchy_digest, hierarchy_size = _read_readonly_file(
        root, "hierarchy.json", label="hierarchy contract"
    )
    contract_set_data, contract_set_digest, contract_set_size = _read_readonly_file(
        root, "contract-set.json", label="hierarchy contract set"
    )
    if json.loads(hierarchy_data.decode("utf-8")) != hierarchy:
        raise WorkflowError("hierarchy contract changed during root receipt creation")
    if json.loads(contract_set_data.decode("utf-8")) != manifest:
        raise WorkflowError("hierarchy contract set changed during root receipt creation")

    declared_team_ids = frozenset(team_by_id)
    journal_rows = [
        _journal_descriptor(root, item, allowed_team_ids=declared_team_ids)
        for item in root_journals
    ]
    _unique_descriptors(journal_rows, keys=("label",), label="root journal label")
    _unique_descriptors(journal_rows, keys=("path",), label="root journal path")

    team_rows: list[dict[str, Any]] = []
    sealed_team_evidence_paths: set[str] = set()
    for team_id in sorted(team_by_id):
        contract = team_by_id[team_id]
        verified = verify_team_receipt(root, evidence_root, hierarchy, contract)
        contract_relative = f"teams/{team_id}/delegation-contract.json"
        _, contract_file_digest, contract_size = _read_readonly_file(
            root, contract_relative, label="team delegation contract"
        )
        receipt_relative = f"teams/{team_id}/team-receipt.json"
        _, receipt_file_digest, receipt_size = _read_readonly_file(
            root, receipt_relative, label="team receipt"
        )
        team_rows.append(
            {
                "team_id": team_id,
                "delegation_contract": {
                    "path": contract_relative,
                    "contract_sha256": contract["contract_sha256"],
                    "file_sha256": contract_file_digest,
                    "size": contract_size,
                },
                "team_receipt": {
                    "path": receipt_relative,
                    "receipt_sha256": verified["receipt_sha256"],
                    "file_sha256": receipt_file_digest,
                    "size": receipt_size,
                },
            }
        )
        team_evidence_paths = {
            artifact["path"]
            for worker in verified["workers"]
            for artifact in worker["artifacts"]
        } | {artifact["path"] for artifact in verified["review_evidence"]}
        overlap = sorted(sealed_team_evidence_paths & team_evidence_paths)
        if overlap:
            raise WorkflowError(
                "evidence path is sealed by more than one team receipt: " + ", ".join(overlap)
            )
        sealed_team_evidence_paths.update(team_evidence_paths)

    binding_rows = [_artifact_descriptor(evidence_root, item) for item in cross_team_bindings]
    approval_rows = [_artifact_descriptor(evidence_root, item) for item in approval_evidence]
    _unique_descriptors(binding_rows, keys=("kind",), label="cross-team binding kind")
    _unique_descriptors(binding_rows, keys=("path",), label="cross-team binding path")
    _unique_descriptors(approval_rows, keys=("kind",), label="approval evidence kind")
    _unique_descriptors(approval_rows, keys=("path",), label="approval evidence path")
    overlap = sorted(
        {item["path"] for item in binding_rows} & {item["path"] for item in approval_rows}
    )
    if overlap:
        raise WorkflowError(
            "cross-team binding evidence overlaps approval evidence: " + ", ".join(overlap)
        )
    external_overlap = sorted(
        sealed_team_evidence_paths
        & ({item["path"] for item in binding_rows} | {item["path"] for item in approval_rows})
    )
    if external_overlap:
        raise WorkflowError(
            "root evidence overlaps team-owned evidence: " + ", ".join(external_overlap)
        )
    required_approvals = {
        item for team in team_by_id.values() for item in team["required_approvals"]
    }
    _validate_required_evidence_kinds(
        approval_rows,
        required_approvals,
        label="root approval evidence",
    )
    issues = _validated_text_list(unresolved_issues, label="root receipt unresolved_issues")
    if outcome not in _ROOT_OUTCOMES:
        raise WorkflowError(f"invalid root outcome: {outcome!r}")

    receipt = {
        "schema": ROOT_RECEIPT_SCHEMA,
        "version": 1,
        "orchestration_id": hierarchy["orchestration_id"],
        "hierarchy_identity_sha256": hierarchy["identity_sha256"],
        "hierarchy_contract": {
            "path": "hierarchy.json",
            "schema": HIERARCHY_SCHEMA,
            "file_sha256": hierarchy_digest,
            "size": hierarchy_size,
        },
        "contract_set": {
            "path": "contract-set.json",
            "file_sha256": contract_set_digest,
            "size": contract_set_size,
        },
        "root_journals": sorted(journal_rows, key=lambda item: item["label"]),
        "teams": team_rows,
        "cross_team_bindings": sorted(binding_rows, key=lambda item: (item["kind"], item["path"])),
        "approval_evidence": sorted(approval_rows, key=lambda item: (item["kind"], item["path"])),
        "unresolved_issues": issues,
        "outcome": outcome,
        "created_at": created_at or utc_now(),
    }
    receipt["receipt_sha256"] = _identity_digest(receipt, omit="receipt_sha256")
    validate_instance(receipt, ROOT_RECEIPT_SCHEMA, artifact="root orchestration receipt")
    _install_receipt(root / "root-receipt.json", receipt)
    return verify_root_receipt(root, evidence_root)


def verify_root_receipt(
    orchestration_root: Path,
    evidence_root: Path,
) -> dict[str, Any]:
    """Verify the root receipt, all team receipts, and every sealed file."""
    root = require_directory(Path(orchestration_root), label="orchestration root")
    evidence_root = require_directory(Path(evidence_root), label="hierarchy evidence root")
    hierarchy, teams, manifest = read_contract_set(root)
    team_by_id = {item["team_id"]: item for item in teams}
    receipt = _read_readonly_json(root / "root-receipt.json", label="root receipt")
    validate_instance(receipt, ROOT_RECEIPT_SCHEMA, artifact="root-receipt.json")
    _validate_receipt_digest(receipt, field="receipt_sha256", label="root receipt")
    if (
        receipt["orchestration_id"] != hierarchy["orchestration_id"]
        or receipt["hierarchy_identity_sha256"] != hierarchy["identity_sha256"]
    ):
        raise WorkflowError("root receipt identity does not match hierarchy")

    for key, expected_value in (
        ("hierarchy_contract", hierarchy),
        ("contract_set", manifest),
    ):
        descriptor = receipt[key]
        data, digest, size = _read_readonly_file(root, descriptor["path"], label=key)
        try:
            actual_value = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"invalid {key} JSON") from exc
        if actual_value != expected_value or descriptor["file_sha256"] != digest or descriptor["size"] != size:
            raise WorkflowError(f"root receipt {key} digest mismatch")

    _unique_descriptors(receipt["root_journals"], keys=("label",), label="root journal label")
    _unique_descriptors(receipt["root_journals"], keys=("path",), label="root journal path")
    for descriptor in receipt["root_journals"]:
        validate_id(descriptor["label"], "journal label")
        validate_id(descriptor["journal_id"], "journal id")
        _verify_journal_descriptor(
            root,
            descriptor,
            allowed_team_ids=frozenset(team_by_id),
        )

    seen_teams: set[str] = set()
    sealed_team_evidence_paths: set[str] = set()
    for entry in receipt["teams"]:
        team_id = entry["team_id"]
        if team_id in seen_teams or team_id not in team_by_id:
            raise WorkflowError(f"duplicate or undeclared team in root receipt: {team_id}")
        seen_teams.add(team_id)
        contract = team_by_id[team_id]
        contract_descriptor = entry["delegation_contract"]
        expected_contract_path = f"teams/{team_id}/delegation-contract.json"
        expected_receipt_path = f"teams/{team_id}/team-receipt.json"
        if contract_descriptor["path"] != expected_contract_path:
            raise WorkflowError(f"unexpected team contract path in root receipt: {team_id}")
        if entry["team_receipt"]["path"] != expected_receipt_path:
            raise WorkflowError(f"unexpected team receipt path in root receipt: {team_id}")
        _, digest, size = _read_readonly_file(
            root, contract_descriptor["path"], label="team delegation contract"
        )
        if (
            contract_descriptor["contract_sha256"] != contract["contract_sha256"]
            or contract_descriptor["file_sha256"] != digest
            or contract_descriptor["size"] != size
        ):
            raise WorkflowError(f"root receipt team contract mismatch: {team_id}")
        verified = verify_team_receipt(
            root,
            evidence_root,
            hierarchy,
            contract,
            receipt_path=entry["team_receipt"]["path"],
        )
        _, receipt_file_digest, receipt_size = _read_readonly_file(
            root, entry["team_receipt"]["path"], label="team receipt"
        )
        if (
            entry["team_receipt"]["receipt_sha256"] != verified["receipt_sha256"]
            or entry["team_receipt"]["file_sha256"] != receipt_file_digest
            or entry["team_receipt"]["size"] != receipt_size
        ):
            raise WorkflowError(f"root receipt team receipt mismatch: {team_id}")
        team_evidence_paths = {
            artifact["path"]
            for worker in verified["workers"]
            for artifact in worker["artifacts"]
        } | {artifact["path"] for artifact in verified["review_evidence"]}
        overlap = sorted(sealed_team_evidence_paths & team_evidence_paths)
        if overlap:
            raise WorkflowError(
                "evidence path is sealed by more than one team receipt: " + ", ".join(overlap)
            )
        sealed_team_evidence_paths.update(team_evidence_paths)
    if seen_teams != set(team_by_id):
        raise WorkflowError("root receipt does not contain the exact declared team set")

    for descriptor in receipt["cross_team_bindings"]:
        _verify_artifact_descriptor(evidence_root, descriptor, label="cross-team binding")
    for descriptor in receipt["approval_evidence"]:
        _verify_artifact_descriptor(evidence_root, descriptor, label="approval evidence")
    _unique_descriptors(receipt["cross_team_bindings"], keys=("kind",), label="cross-team binding kind")
    _unique_descriptors(receipt["cross_team_bindings"], keys=("path",), label="cross-team binding path")
    _unique_descriptors(receipt["approval_evidence"], keys=("kind",), label="approval evidence kind")
    _unique_descriptors(receipt["approval_evidence"], keys=("path",), label="approval evidence path")
    _validate_required_evidence_kinds(
        receipt["approval_evidence"],
        {item for team in team_by_id.values() for item in team["required_approvals"]},
        label="root approval evidence",
    )
    overlap = sorted(
        {item["path"] for item in receipt["cross_team_bindings"]}
        & {item["path"] for item in receipt["approval_evidence"]}
    )
    if overlap:
        raise WorkflowError(
            "cross-team binding evidence overlaps approval evidence: " + ", ".join(overlap)
        )
    external_overlap = sorted(
        sealed_team_evidence_paths
        & (
            {item["path"] for item in receipt["cross_team_bindings"]}
            | {item["path"] for item in receipt["approval_evidence"]}
        )
    )
    if external_overlap:
        raise WorkflowError(
            "root evidence overlaps team-owned evidence: " + ", ".join(external_overlap)
        )
    if receipt["outcome"] not in _ROOT_OUTCOMES:
        raise WorkflowError("invalid root outcome")
    return receipt
