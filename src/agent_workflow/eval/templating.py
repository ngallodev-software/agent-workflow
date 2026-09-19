"""Deterministic sealed-run evaluation template contracts and renderers."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..contracts import read_contract, validate_instance
from ..cli_contract import EVALUATION_TEMPLATE_KINDS
from ..errors import WorkflowError
from ..lifecycle import lifecycle_receipts
from ..path import inventory_tree, read_regular_file, require_directory
from ..receipts import read_sealed_artifact_bytes, read_sealed_contract, verify_seal_details
from ..repository_closeout import (
    repository_closeout_summary,
    validate_repository_closeout_payload,
)
from ..util import atomic_write_json, sha256_file
from .outcomes import classify_attempt
from .scoring import evaluation_policy_for_run, validate_score_set

LEDGER_ROW_SCHEMA = "agent-workflow/evaluation-ledger-row/v1"
LIFECYCLE_ARCHIVE_SCHEMA = "agent-workflow/lifecycle-archive/v1"


@dataclass(frozen=True)
class TemplateSpec:
    filename: str
    schema: str


TEMPLATE_SPECS: dict[str, TemplateSpec] = {
    "evaluation-plan": TemplateSpec(
        "evaluation-plan.json", "agent-workflow/evaluation-plan/v1"
    ),
    "sealed-run-assessment": TemplateSpec(
        "sealed-run-assessment.json", "agent-workflow/sealed-run-assessment/v1"
    ),
    "ledger-row": TemplateSpec("ledger-row.json", LEDGER_ROW_SCHEMA),
    "lifecycle-archive": TemplateSpec(
        "lifecycle-archive.json", LIFECYCLE_ARCHIVE_SCHEMA
    ),
}
TEMPLATE_KINDS = EVALUATION_TEMPLATE_KINDS



def _template_root() -> Path:
    source_root = Path(__file__).resolve().parents[3] / "templates" / "evaluation"
    installed_root = (
        Path(sys.prefix) / "share" / "agent-workflow" / "templates" / "evaluation"
    )
    # Source and installed execution are separate authority modes. Match the
    # contract schema loader and never merge both roots into one catalog.
    if source_root.is_dir():
        return source_root
    if installed_root.is_dir():
        return installed_root
    raise WorkflowError("packaged evaluation template directory is missing")


def load_template(kind: str) -> dict[str, Any]:
    spec = TEMPLATE_SPECS.get(kind)
    if spec is None:
        raise WorkflowError(f"unknown evaluation template kind: {kind}")
    return read_contract(_template_root() / spec.filename, spec.schema)


def write_template(kind: str, output: Path) -> dict[str, Any]:
    value = load_template(kind)
    atomic_write_json(output, value)
    return {"template": kind, "schema": value["schema"], "output": str(output)}




















def _read_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(read_regular_file(path).data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
        return None, str(exc)
    return (
        (value, None)
        if isinstance(value, dict)
        else (None, "JSON value is not an object")
    )


def build_ledger_row(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    mutable_status, status_error = _read_object(run_dir / "status.json")
    failures = [status_error] if status_error and (run_dir / "status.json").exists() else []
    receipt_digest = None
    receipt_verified = False
    final_receipt: dict[str, Any] | None = None
    final_status: dict[str, Any] = {}
    completion: dict[str, Any] = {}
    completion_collection: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    runtime: dict[str, Any] = {}
    repository_closeout: dict[str, Any] | None = None
    sealed_paths: set[str] = set()

    try:
        final_receipt, receipt_digest = verify_seal_details(run_dir)
        receipt_verified = True
        sealed_paths = {
            str(item.get("path"))
            for item in final_receipt.get("artifacts", [])
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }
    except WorkflowError as exc:
        failures.append(str(exc))

    if receipt_verified and final_receipt is not None:
        contracts = (
            ("final-status.json", "agent-workflow/agent-run-status/v1", "status"),
            ("completion.json", "agent-workflow/completion/v1", "completion"),
            ("collections/completion.json", "agent-workflow/completion-collection/v1", "collection"),
            ("run-provenance.json", "agent-workflow/run-provenance/v1", "provenance"),
        )
        for relative_path, schema, target in contracts:
            try:
                value, _ = read_sealed_contract(run_dir, final_receipt, relative_path, schema)
            except WorkflowError as exc:
                failures.append(str(exc))
                continue
            if target == "status":
                final_status = value
            elif target == "completion":
                completion = value
            elif target == "collection":
                completion_collection = value
            else:
                provenance = value
        if "evaluation-runtime.json" in sealed_paths:
            try:
                runtime, _ = read_sealed_contract(
                    run_dir,
                    final_receipt,
                    "evaluation-runtime.json",
                    "agent-workflow/evaluation-runtime/v1",
                )
            except WorkflowError as exc:
                failures.append(str(exc))
        if "repository-closeout.json" in sealed_paths:
            try:
                closeout_data, _ = read_sealed_artifact_bytes(
                    run_dir,
                    final_receipt,
                    "repository-closeout.json",
                )
                closeout_receipt = validate_repository_closeout_payload(
                    closeout_data,
                    artifact=str(run_dir / "repository-closeout.json"),
                )
                repository_closeout = repository_closeout_summary(closeout_receipt)
            except WorkflowError as exc:
                failures.append(str(exc))

    score, score_error = _read_object(run_dir / "scores" / "score-set.json")
    if score_error and (run_dir / "scores" / "score-set.json").exists():
        failures.append(score_error)
    effective_status = final_status or mutable_status or {}
    evaluation_required = bool(
        runtime
        or effective_status.get("evaluation_path")
        or (run_dir / "evaluation-runtime.json").is_file()
        or (isinstance(final_receipt, dict) and bool(evaluation_policy_for_run(run_dir, final_receipt)))
    )
    score_verdict = None
    if score is not None and receipt_verified and final_receipt is not None and receipt_digest is not None:
        try:
            validated_score = validate_score_set(
                run_dir,
                score,
                final_receipt=final_receipt,
                expected_final_receipt_sha256=receipt_digest,
            )
            if validated_score.get("verdict") in {"pass", "fail", "invalid"}:
                score_verdict = validated_score["verdict"]
        except WorkflowError as exc:
            failures.append(str(exc))
    evaluation_state = (
        "not_planned"
        if not evaluation_required
        else "verified"
        if score_verdict is not None
        else "not_verified"
    )
    disposition = None
    disposition_path = None
    if receipt_verified:
        try:
            chain = lifecycle_receipts(run_dir, expected_final_receipt_sha256=receipt_digest)
            if chain:
                disposition = chain[-1]["receipt"].get("action")
                disposition_path = chain[-1]["path"].relative_to(run_dir).as_posix()
            override_path = run_dir / "force-accept-receipt.json"
            if override_path.is_file():
                override = json.loads(override_path.read_text(encoding="utf-8"))
                disposition = "force-accepted" if override.get("schema") == "agent-workflow/force-accept-receipt/v1" else disposition
                disposition_path = override_path.relative_to(run_dir).as_posix()
        except WorkflowError as exc:
            failures.append(str(exc))
    workflow = provenance.get("workflow")
    case_id = workflow.get("node_id") if isinstance(workflow, Mapping) else None
    completion_result = completion_collection.get("validation_status") or effective_status.get("completion_result")
    executor_result = effective_status.get("executor_result")
    policy_result = effective_status.get("policy_result") or "not_evaluated"
    acceptance_eligible = bool(effective_status.get("acceptance_eligible", False))
    attempt_classification = classify_attempt(
        effective_status,
        receipt_verified=receipt_verified,
        completion_result=completion_result if isinstance(completion_result, str) else None,
    )
    evidence_paths = {
        "status": "status.json" if (run_dir / "status.json").is_file() else None,
        "completion": "completion.json" if (run_dir / "completion.json").is_file() else None,
        "completion_collection": "collections/completion.json" if (run_dir / "collections" / "completion.json").is_file() else None,
        "run_provenance": "run-provenance.json" if (run_dir / "run-provenance.json").is_file() else None,
        "final_receipt": "final-receipt.json" if (run_dir / "final-receipt.json").is_file() else None,
        "evaluation_runtime": "evaluation-runtime.json" if (run_dir / "evaluation-runtime.json").is_file() else None,
        "score_set": "scores/score-set.json" if (run_dir / "scores" / "score-set.json").is_file() else None,
        "evaluation_report": "reports/evaluation.md" if (run_dir / "reports" / "evaluation.md").is_file() else None,
        "trial_collection": "trials.json" if (run_dir / "trials.json").is_file() else None,
        "repository_closeout": "repository-closeout.json" if (run_dir / "repository-closeout.json").is_file() else None,
        "lifecycle_disposition": disposition_path,
    }
    row = {
        "schema": LEDGER_ROW_SCHEMA,
        "run_id": run_dir.name,
        "ticket_id": completion.get("ticket_id") or runtime.get("ticket_id") or effective_status.get("ticket_id"),
        "case_id": case_id,
        "source_revision": provenance.get("source_revision"),
        "pack_id": completion.get("pack_id") or effective_status.get("pack_id"),
        "pack_checksum_reference": provenance.get("pack_manifest_sha256"),
        "run_receipt_sha256": receipt_digest,
        "receipt_verification": "verified" if receipt_verified else "not_verified" if (run_dir / "final-receipt.json").exists() else "unavailable",
        "executor_result": executor_result,
        "completion_result": completion_result,
        "policy_result": policy_result,
        "acceptance_eligible": acceptance_eligible,
        "attempt_classification": attempt_classification,
        "repository_closeout": repository_closeout,
        "evaluation_state": evaluation_state,
        "evaluation_result": score_verdict,
        "disposition": disposition,
        "evidence_paths": evidence_paths,
        "failures": sorted(set(item for item in failures if item)),
    }
    validate_instance(row, LEDGER_ROW_SCHEMA, artifact="evaluation ledger row")
    return row


def build_lifecycle_archive(
    run_dir: Path,
    *,
    retention_class: str,
    exclude_paths: Sequence[Path] = (),
) -> dict[str, Any]:
    run_dir = require_directory(run_dir.resolve(), label="run directory")
    if retention_class not in {"transient", "standard", "release", "legal-hold"}:
        raise WorkflowError(f"unsupported retention class: {retention_class}")
    excluded: set[str] = set()
    for path in exclude_paths:
        candidate = path.expanduser()
        candidate = candidate if candidate.is_absolute() else Path.cwd() / candidate
        try:
            relative = candidate.resolve().relative_to(run_dir).as_posix()
        except ValueError:
            continue
        excluded.add(relative)
    contents = []
    for entry in inventory_tree(run_dir):
        if entry.kind != "file":
            continue
        relative = entry.path
        if (
            relative in excluded
            or relative == "MANIFEST.sha256"
            or relative.endswith(".sha256")
            or relative.endswith(".lock")
        ):
            continue
        if entry.sha256 is None:
            raise WorkflowError(f"archive input has no digest: {relative}")
        contents.append(
            {"path": relative, "sha256": entry.sha256, "size": entry.size}
        )
    value = {
        "schema": LIFECYCLE_ARCHIVE_SCHEMA,
        "run_id": run_dir.name,
        "retention_class": retention_class,
        "export_contents": contents,
        "transfer_checksum": {
            "required_in_repository": False,
            "instruction": "Generate <archive>.sha256 beside the completed transfer archive and verify it at the destination; do not add it to the repository.",
        },
        "archive_status": "prepared",
        "cleanup_status": "not_started",
    }
    validate_instance(value, LIFECYCLE_ARCHIVE_SCHEMA, artifact="lifecycle archive plan")
    return value
