"""Evidence-first assessment for exported sealed-run summaries."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..util import sha256_file


def _load(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    return (value, None) if isinstance(value, dict) else (None, "JSON value is not an object")


def assess_exported_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    completion_path = run_dir / "completion.json"
    receipt_path = run_dir / "final-receipt.json"
    completion, completion_error = _load(completion_path)
    receipt, receipt_error = _load(receipt_path)
    artifacts = {
        item.get("path"): item
        for item in (receipt or {}).get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    completion_item = artifacts.get("completion.json")
    completion_digest_matches = None
    if completion and isinstance(completion_item, dict) and isinstance(completion_item.get("sha256"), str):
        completion_digest_matches = sha256_file(completion_path) == completion_item["sha256"]

    missing_sealed_artifacts = sorted(
        path for path in artifacts if not (run_dir / path).is_file()
    )
    score_path = run_dir / "scores" / "score-set.json"
    report_path = run_dir / "reports" / "evaluation.md"
    collection_path = run_dir / "trials.json"
    evaluation_plan_present = (run_dir / "evaluation-runtime.json").is_file()
    score_present = score_path.is_file()
    report_present = report_path.is_file()
    collection_present = collection_path.is_file()

    completion_valid = bool(
        completion
        and completion.get("schema") == "agent-workflow/completion/v1"
        and isinstance(completion.get("session_id"), str)
        and completion_digest_matches is True
    )
    receipt_structurally_valid = bool(
        receipt
        and receipt.get("schema") == "agent-workflow/final-receipt/v1"
        and isinstance(receipt.get("session_id"), str)
        and isinstance(receipt.get("artifacts"), list)
        and (
            completion is None
            or receipt.get("session_id") == completion.get("session_id")
        )
    )
    lifecycle_portably_verifiable = receipt_structurally_valid and not missing_sealed_artifacts
    evaluation_state = (
        "missing-plan" if not evaluation_plan_present else
        "missing-score-set" if not score_present else
        "incomplete-report" if not report_present else
        "incomplete-collection" if not collection_present else
        "complete"
    )
    comparable = lifecycle_portably_verifiable and evaluation_state == "complete"
    limitations = []
    if missing_sealed_artifacts:
        limitations.append("export omits artifacts required to verify the complete lifecycle seal")
    if not evaluation_plan_present:
        limitations.append("evaluation plan/runtime evidence is unavailable; no score may be inferred")
    if not score_present:
        limitations.append("score-set evidence is unavailable")
    if not report_present:
        limitations.append("evaluation report evidence is unavailable")
    if not collection_present:
        limitations.append("trial collection evidence is unavailable")

    return {
        "schema": "agent-workflow/sealed-run-assessment/v1",
        "run_id": run_dir.name,
        "completion": {
            "present": completion_path.is_file(),
            "valid": completion_valid,
            "result": completion.get("result") if completion else None,
            "error": completion_error,
            "sha256": sha256_file(completion_path) if completion_path.is_file() else None,
            "matches_final_receipt": completion_digest_matches,
        },
        "lifecycle_seal": {
            "final_receipt_present": receipt_path.is_file(),
            "receipt_structurally_valid": receipt_structurally_valid,
            "portable_verification": "verified" if lifecycle_portably_verifiable else "unavailable",
            "missing_artifacts": missing_sealed_artifacts,
            "error": receipt_error,
        },
        "evaluation": {
            "plan_present": evaluation_plan_present,
            "score_set_present": score_present,
            "report_present": report_present,
            "collection_present": collection_present,
            "state": evaluation_state,
        },
        "phase_acceptance": "not-exported",
        "comparable": comparable,
        "limitations": limitations,
    }


def assess_exported_runs(root: Path) -> dict[str, Any]:
    rows = [assess_exported_run(path) for path in sorted(root.iterdir()) if path.is_dir()]
    return {
        "schema": "agent-workflow/sealed-run-assessment-collection/v1",
        "root": str(root.resolve()),
        "runs": rows,
        "summary": {
            "run_count": len(rows),
            "completion_valid_count": sum(bool(row["completion"]["valid"]) for row in rows),
            "portable_seal_verified_count": sum(row["lifecycle_seal"]["portable_verification"] == "verified" for row in rows),
            "comparable_count": sum(bool(row["comparable"]) for row in rows),
        },
    }
