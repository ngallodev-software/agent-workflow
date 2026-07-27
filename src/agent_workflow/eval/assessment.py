"""Evidence-first assessment for exported sealed-run summaries."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from ..contracts import validate_instance
from ..errors import WorkflowError
from ..lifecycle import lifecycle_receipts
from ..path import read_regular_file
from .scope import ScopePolicy, compare_scope
from .scoring import validate_score_set
from .trials import load_trials


def _load(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        read = read_regular_file(path)
        value = json.loads(read.data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
        return None, str(exc)
    return (
        (value, None)
        if isinstance(value, dict)
        else (None, "JSON value is not an object")
    )


def _validate(
    value: dict[str, Any] | None,
    schema: str,
    label: str,
    failures: list[str],
) -> bool:
    if value is None:
        return False
    try:
        validate_instance(value, schema, artifact=label)
    except WorkflowError as exc:
        failures.append(str(exc))
        return False
    return True


def _safe_artifact_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(
        value
        and not path.is_absolute()
        and path.as_posix() == value
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _portable_seal(
    run_dir: Path,
    receipt: dict[str, Any] | None,
    *,
    structurally_valid: bool,
    failures: list[str],
    contradictions: list[str],
) -> tuple[str, list[str]]:
    if receipt is None or not structurally_valid:
        return (
            "not_verified" if (run_dir / "final-receipt.json").exists() else "unavailable",
            [],
        )
    missing: list[str] = []
    invalid = False
    seen: set[str] = set()
    for item in receipt["artifacts"]:
        relative = item["path"]
        if relative in seen:
            failures.append(f"final receipt contains duplicate artifact path: {relative}")
            invalid = True
            continue
        seen.add(relative)
        if not _safe_artifact_path(relative):
            failures.append(f"final receipt contains unsafe artifact path: {relative}")
            invalid = True
            continue
        path = run_dir / relative
        if not path.exists() and not path.is_symlink():
            missing.append(relative)
            continue
        try:
            read = read_regular_file(path)
        except WorkflowError as exc:
            failures.append(str(exc))
            invalid = True
            continue
        if read.size != item["size"]:
            contradictions.append(f"sealed artifact size mismatch: {relative}")
            invalid = True
        if read.sha256 != item["sha256"]:
            contradictions.append(f"sealed artifact checksum mismatch: {relative}")
            invalid = True
    if invalid:
        return "not_verified", sorted(missing)
    if missing:
        return "unavailable", sorted(missing)
    return "verified", []


def _structured_stream(
    run_dir: Path, failures: list[str], contradictions: list[str]
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    provider_path = run_dir / "provider-evidence.json"
    raw_path = run_dir / "executor-events.jsonl"
    provider_present = provider_path.is_file()
    raw_present = raw_path.is_file()
    if not provider_present and not raw_present:
        return {
            "provider_evidence_present": False,
            "raw_events_present": False,
            "state": "unavailable",
        }, None
    provider, error = _load(provider_path) if provider_present else (None, None)
    if error:
        failures.append(error)
    provider_valid = _validate(
        provider,
        "agent-workflow/provider-evidence/v1",
        "provider evidence",
        failures,
    )
    valid = provider_valid and raw_present
    if provider_valid and provider is not None and raw_present:
        try:
            raw = read_regular_file(raw_path)
            if provider.get("raw_events_path") != "executor-events.jsonl":
                contradictions.append("provider evidence raw-events path is inconsistent")
                valid = False
            if provider.get("raw_events_sha256") != raw.sha256:
                contradictions.append("provider evidence raw-events digest mismatch")
                valid = False
            if provider.get("raw_event_bytes") != raw.size:
                contradictions.append("provider evidence raw-events size mismatch")
                valid = False
        except WorkflowError as exc:
            failures.append(str(exc))
            valid = False
        if provider.get("capture_complete") is not True:
            failures.append("provider evidence capture is incomplete")
            valid = False
        if provider.get("usage_complete") is not True:
            failures.append("provider usage evidence is incomplete")
            valid = False
        if provider.get("malformed_event_count") != 0:
            failures.append("provider evidence contains malformed events")
            valid = False
    return {
        "provider_evidence_present": provider_present,
        "raw_events_present": raw_present,
        "state": "verified" if valid else "not_verified",
    }, provider


def _scope_audit(
    run_dir: Path, failures: list[str]
) -> tuple[dict[str, Any], dict[str, str | None]]:
    baseline_path = run_dir / "scope" / "scope-baseline.json"
    post_path = run_dir / "scope" / "scope-post.json"
    paths = {
        "scope_baseline": "scope/scope-baseline.json" if baseline_path.is_file() else None,
        "scope_audit": "scope/scope-post.json" if post_path.is_file() else None,
    }
    if not baseline_path.is_file() and not post_path.is_file():
        return {"present": False, "state": "unavailable", "violations": []}, paths
    if not baseline_path.is_file() or not post_path.is_file():
        failures.append("scope audit requires both baseline and post snapshots")
        return {"present": False, "state": "not_verified", "violations": []}, paths
    baseline, baseline_error = _load(baseline_path)
    post, post_error = _load(post_path)
    for error in (baseline_error, post_error):
        if error:
            failures.append(error)
    valid = _validate(
        baseline,
        "agent-workflow/scope-snapshot/v1",
        "scope baseline",
        failures,
    ) and _validate(
        post,
        "agent-workflow/scope-snapshot/v1",
        "scope post snapshot",
        failures,
    )
    violations: list[str] = []
    if valid and baseline is not None and post is not None:
        source = baseline.get("policy", {})
        policy = ScopePolicy(
            authorized_root=Path(str(source.get("authorized_root", run_dir))),
            writable_paths=tuple(source.get("writable_paths", ())),
            writable_trees=tuple(source.get("writable_trees", ())),
            disposable_trees=tuple(source.get("disposable_trees", ())),
        )
        violations = compare_scope(baseline, post, policy)["violations"]
    return {
        "present": True,
        "state": "verified" if valid and not violations else "not_verified",
        "violations": violations,
    }, paths


def _disposition(
    run_dir: Path,
    final_receipt_sha256: str | None,
    failures: list[str],
    contradictions: list[str],
) -> dict[str, Any]:
    root = run_dir / "receipts"
    if not root.exists() and not root.is_symlink():
        return {"value": None, "evidence_path": None, "state": "unavailable"}
    try:
        chain = lifecycle_receipts(
            run_dir,
            expected_final_receipt_sha256=final_receipt_sha256,
        )
    except WorkflowError as exc:
        failures.append(str(exc))
        return {"value": None, "evidence_path": None, "state": "not_verified"}
    if not chain:
        return {"value": None, "evidence_path": None, "state": "unavailable"}
    last = chain[-1]
    return {
        "value": last["receipt"].get("action"),
        "evidence_path": last["path"].relative_to(run_dir).as_posix(),
        "state": "verified",
    }


def _verify_trial_collection(
    run_dir: Path,
    collection_path: Path,
    *,
    final_receipt_sha256: str | None,
    sealed_artifacts: Mapping[str, Mapping[str, Any]],
    provider: Mapping[str, Any] | None,
    score_verdict: str | None,
    failures: list[str],
    contradictions: list[str],
) -> bool:
    try:
        trials = load_trials(collection_path)
    except WorkflowError as exc:
        failures.append(str(exc))
        return False
    if len(trials) != 1:
        failures.append(
            "per-run trial collection must contain exactly one trial: "
            f"observed {len(trials)}"
        )
        return False
    trial = trials[0]
    valid = True
    trial_path = trial.get("run_path")
    if trial.get("trial_id") != run_dir.name or not isinstance(trial_path, str):
        contradictions.append("trial collection belongs to another run")
        valid = False
    elif Path(trial_path).name != run_dir.name:
        contradictions.append("trial collection run path belongs to another run")
        valid = False
    if (
        final_receipt_sha256 is None
        or trial.get("final_receipt_sha256") != final_receipt_sha256
    ):
        contradictions.append("trial collection final-receipt digest mismatch")
        valid = False
    provider_item = sealed_artifacts.get("provider-evidence.json")
    provider_sha256 = (
        provider_item.get("sha256") if isinstance(provider_item, Mapping) else None
    )
    if provider_sha256 is None or trial.get("provider_evidence_sha256") != provider_sha256:
        contradictions.append("trial collection provider-evidence digest mismatch")
        valid = False
    raw_sha256 = provider.get("raw_events_sha256") if provider is not None else None
    if raw_sha256 is None or trial.get("raw_events_sha256") != raw_sha256:
        contradictions.append("trial collection raw-events digest mismatch")
        valid = False
    if score_verdict is None or trial.get("verdict") != score_verdict:
        contradictions.append("trial collection score verdict mismatch")
        valid = False
    return valid


def assess_exported_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    completion_path = run_dir / "completion.json"
    receipt_path = run_dir / "final-receipt.json"
    failures: list[str] = []
    contradictions: list[str] = []
    completion, completion_error = _load(completion_path)
    receipt, receipt_error = _load(receipt_path)
    for error in (completion_error, receipt_error):
        if error:
            failures.append(error)
    completion_schema_valid = _validate(
        completion,
        "agent-workflow/completion/v1",
        "completion handoff",
        failures,
    )
    receipt_structurally_valid = _validate(
        receipt,
        "agent-workflow/final-receipt/v1",
        "final receipt",
        failures,
    )
    artifacts = {
        item.get("path"): item
        for item in (receipt or {}).get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    completion_item = artifacts.get("completion.json")
    completion_sha256 = None
    if completion is not None and completion_error is None:
        try:
            completion_sha256 = read_regular_file(completion_path).sha256
        except WorkflowError as exc:
            failures.append(str(exc))
    completion_digest_matches = None
    if (
        completion_sha256 is not None
        and isinstance(completion_item, dict)
        and isinstance(completion_item.get("sha256"), str)
    ):
        completion_digest_matches = completion_sha256 == completion_item["sha256"]
    session_matches = bool(
        completion
        and receipt
        and completion.get("session_id") == receipt.get("session_id") == run_dir.name
    )
    if completion and receipt and not session_matches:
        contradictions.append("completion/final-receipt session identity mismatch")
    completion_valid = bool(
        completion_schema_valid
        and receipt_structurally_valid
        and completion_digest_matches is True
        and session_matches
    )
    portable_state, missing_sealed_artifacts = _portable_seal(
        run_dir,
        receipt,
        structurally_valid=receipt_structurally_valid,
        failures=failures,
        contradictions=contradictions,
    )
    final_receipt_sha256 = None
    if receipt is not None and receipt_error is None:
        try:
            final_receipt_sha256 = read_regular_file(receipt_path).sha256
        except WorkflowError as exc:
            failures.append(str(exc))

    structured_stream, provider = _structured_stream(
        run_dir, failures, contradictions
    )
    scope_audit, scope_paths = _scope_audit(run_dir, failures)

    plan_path = run_dir / "evaluation-runtime.json"
    score_path = run_dir / "scores" / "score-set.json"
    report_path = run_dir / "reports" / "evaluation.md"
    collection_path = run_dir / "trials.json"
    evaluation_plan_present = plan_path.exists() or plan_path.is_symlink()
    evaluation_plan_verified = False
    if evaluation_plan_present:
        plan, plan_error = _load(plan_path)
        if plan_error:
            failures.append(plan_error)
        else:
            evaluation_plan_verified = _validate(
                plan,
                "agent-workflow/evaluation-runtime/v1",
                "evaluation runtime",
                failures,
            )
    score_present = score_path.is_file()
    report_present = report_path.is_file()
    report_verified = False
    if report_present:
        try:
            report_verified = bool(read_regular_file(report_path).data)
            if not report_verified:
                failures.append("evaluation report is empty")
        except WorkflowError as exc:
            failures.append(str(exc))
    collection_present = collection_path.is_file()
    score_verified = False
    score_verdict = None
    if score_present and receipt_structurally_valid and receipt is not None and final_receipt_sha256:
        score, score_error = _load(score_path)
        if score_error:
            failures.append(score_error)
        elif score is not None:
            try:
                validate_score_set(
                    run_dir,
                    score,
                    final_receipt=receipt,
                    expected_final_receipt_sha256=final_receipt_sha256,
                )
                score_verified = True
                score_verdict = score.get("verdict")
            except WorkflowError as exc:
                failures.append(str(exc))
    collection_verified = False
    if collection_present:
        collection_verified = _verify_trial_collection(
            run_dir,
            collection_path,
            final_receipt_sha256=final_receipt_sha256,
            sealed_artifacts=artifacts,
            provider=provider,
            score_verdict=score_verdict,
            failures=failures,
            contradictions=contradictions,
        )
    evaluation_state = (
        "missing-plan"
        if not evaluation_plan_present
        else "invalid-plan"
        if not evaluation_plan_verified
        else "missing-score-set"
        if not score_present
        else "invalid-score-set"
        if not score_verified
        else "incomplete-report"
        if not report_present or not report_verified
        else "incomplete-collection"
        if not collection_present or not collection_verified
        else "complete"
    )

    disposition = _disposition(
        run_dir, final_receipt_sha256, failures, contradictions
    )

    ledger_path = run_dir / "ledger-row.json"
    ledger_value, ledger_error = _load(ledger_path) if ledger_path.is_file() else (None, None)
    if ledger_error:
        failures.append(ledger_error)
    ledger_valid = _validate(
        ledger_value,
        "agent-workflow/evaluation-ledger-row/v1",
        "evaluation ledger row",
        failures,
    )
    if ledger_valid and ledger_value is not None:
        if ledger_value.get("run_id") != run_dir.name:
            contradictions.append("ledger row belongs to another run")
            ledger_valid = False
        if (
            final_receipt_sha256 is not None
            and ledger_value.get("run_receipt_sha256") != final_receipt_sha256
        ):
            contradictions.append("ledger row final-receipt digest mismatch")
            ledger_valid = False
        if score_verdict is not None and ledger_value.get("evaluation_result") != score_verdict:
            contradictions.append("ledger row evaluation result mismatch")
            ledger_valid = False
        if portable_state == "verified" and ledger_value.get("receipt_verification") != "verified":
            contradictions.append("ledger row receipt verification mismatch")
            ledger_valid = False
        if (
            disposition["state"] == "verified"
            and ledger_value.get("disposition") != disposition["value"]
        ):
            contradictions.append("ledger row lifecycle disposition mismatch")
            ledger_valid = False
    ledger_state = (
        "verified"
        if ledger_valid
        else "not_verified"
        if ledger_path.exists()
        else "unavailable"
    )

    phase_acceptance = (
        disposition["value"]
        if disposition["state"] == "verified"
        and disposition["value"] in {"accepted", "rejected"}
        else "not-exported"
    )
    comparable = bool(
        completion_valid
        and portable_state == "verified"
        and structured_stream["state"] == "verified"
        and scope_audit["state"] == "verified"
        and evaluation_state == "complete"
        and ledger_state == "verified"
        and disposition["state"] == "verified"
    )
    limitations: list[str] = []
    if missing_sealed_artifacts:
        limitations.append(
            "export omits artifacts required to verify the complete lifecycle seal"
        )
    if portable_state == "not_verified":
        limitations.append("sealed artifact verification failed")
    if structured_stream["state"] != "verified":
        limitations.append("structured provider stream is unavailable or not verified")
    if scope_audit["state"] != "verified":
        limitations.append("writable-scope audit is unavailable or not verified")
    if not evaluation_plan_present:
        limitations.append(
            "evaluation plan/runtime evidence is unavailable; no score may be inferred"
        )
    elif not evaluation_plan_verified:
        limitations.append("evaluation plan/runtime evidence is not verified")
    if not score_present:
        limitations.append("score-set evidence is unavailable")
    elif not score_verified:
        limitations.append("score-set evidence is not verified")
    if not report_present:
        limitations.append("evaluation report evidence is unavailable")
    elif not report_verified:
        limitations.append("evaluation report evidence is not verified")
    if not collection_present:
        limitations.append("trial collection evidence is unavailable")
    elif not collection_verified:
        limitations.append("trial collection evidence is not verified")
    if ledger_state != "verified":
        limitations.append("evaluation ledger row is unavailable or not verified")
    if disposition["state"] != "verified":
        limitations.append("lifecycle disposition is unavailable or not verified")

    value = {
        "schema": "agent-workflow/sealed-run-assessment/v1",
        "run_id": run_dir.name,
        "completion": {
            "present": completion_path.exists() or completion_path.is_symlink(),
            "valid": completion_valid,
            "result": completion.get("result") if completion else None,
            "error": completion_error,
            "sha256": completion_sha256,
            "matches_final_receipt": completion_digest_matches,
        },
        "lifecycle_seal": {
            "final_receipt_present": receipt_path.exists() or receipt_path.is_symlink(),
            "receipt_structurally_valid": receipt_structurally_valid,
            "portable_verification": portable_state,
            "missing_artifacts": missing_sealed_artifacts,
            "error": receipt_error,
        },
        "evaluation": {
            "plan_present": evaluation_plan_present,
            "plan_verified": evaluation_plan_verified,
            "score_set_present": score_present,
            "score_set_verified": score_verified,
            "report_present": report_present,
            "report_verified": report_verified,
            "collection_present": collection_present,
            "collection_verified": collection_verified,
            "state": evaluation_state,
        },
        "phase_acceptance": phase_acceptance,
        "comparable": comparable,
        "limitations": sorted(set(limitations)),
        "evidence_paths": {
            "completion": "completion.json" if completion_path.exists() or completion_path.is_symlink() else None,
            "final_receipt": "final-receipt.json" if receipt_path.exists() or receipt_path.is_symlink() else None,
            "provider_evidence": "provider-evidence.json" if (run_dir / "provider-evidence.json").is_file() else None,
            "raw_events": "executor-events.jsonl" if (run_dir / "executor-events.jsonl").is_file() else None,
            "score_set": "scores/score-set.json" if score_present else None,
            "evaluation_report": "reports/evaluation.md" if report_present else None,
            "trial_collection": "trials.json" if collection_present else None,
            **scope_paths,
            "ledger_row": "ledger-row.json" if ledger_path.is_file() else None,
        },
        "structured_stream": structured_stream,
        "scope_audit": scope_audit,
        "ledger": {
            "row_present": ledger_path.is_file(),
            "path": "ledger-row.json" if ledger_path.is_file() else None,
            "state": ledger_state,
        },
        "failures": sorted(set(failures)),
        "unresolved_contradictions": sorted(set(contradictions)),
        "disposition": disposition,
    }
    validate_instance(
        value,
        "agent-workflow/sealed-run-assessment/v1",
        artifact="sealed-run assessment",
    )
    return value


def assess_exported_runs(root: Path) -> dict[str, Any]:
    rows = [
        assess_exported_run(path)
        for path in sorted(root.iterdir())
        if path.is_dir()
    ]
    return {
        "schema": "agent-workflow/sealed-run-assessment-collection/v1",
        "root": str(root.resolve()),
        "runs": rows,
        "summary": {
            "run_count": len(rows),
            "completion_valid_count": sum(
                bool(row["completion"]["valid"]) for row in rows
            ),
            "portable_seal_verified_count": sum(
                row["lifecycle_seal"]["portable_verification"] == "verified"
                for row in rows
            ),
            "comparable_count": sum(bool(row["comparable"]) for row in rows),
        },
    }
