"""Deterministic evaluation and benchmark template contracts and renderers."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from ..contracts import read_contract, validate_instance
from ..errors import WorkflowError
from ..evidence_repair import supplemental_repairs_for_run
from ..lifecycle import lifecycle_receipts
from ..path import inventory_tree, read_regular_file, require_directory
from ..receipts import read_sealed_artifact_bytes, read_sealed_contract, verify_seal_details
from ..repository_closeout import (
    repository_closeout_summary,
    validate_repository_closeout_payload,
)
from ..util import atomic_write_json, sha256_file
from .compare import compare_trials
from .outcomes import classify_attempt
from .scoring import evaluation_policy_for_run, validate_score_set
from .trials import load_trials

BENCHMARK_MANIFEST_SCHEMA = "agent-workflow/benchmark-manifest/v1"
BENCHMARK_REPORT_SCHEMA = "agent-workflow/benchmark-report/v1"
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
    "benchmark-manifest": TemplateSpec(
        "benchmark-manifest.json", BENCHMARK_MANIFEST_SCHEMA
    ),
    "sealed-run-assessment": TemplateSpec(
        "sealed-run-assessment.json", "agent-workflow/sealed-run-assessment/v1"
    ),
    "benchmark-report": TemplateSpec("benchmark-report.json", BENCHMARK_REPORT_SCHEMA),
    "ledger-row": TemplateSpec("ledger-row.json", LEDGER_ROW_SCHEMA),
    "lifecycle-archive": TemplateSpec(
        "lifecycle-archive.json", LIFECYCLE_ARCHIVE_SCHEMA
    ),
}
TEMPLATE_KINDS = tuple(TEMPLATE_SPECS)


IDENTITY_FIELDS: tuple[tuple[str, str], ...] = (
    ("provider", "provider"),
    ("source_revision", "source_revision"),
    ("pack_manifest_sha256", "pack_manifest_sha256"),
    ("model", "model"),
    ("executor", "executor"),
    ("executor_version", "executor_version"),
)


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


def _safe_relative(value: str, label: str) -> None:
    path = PurePosixPath(value)
    normalized = path.as_posix()
    if value.endswith("/"):
        normalized += "/"
    if (
        path.is_absolute()
        or not value
        or "\\" in value
        or value != normalized
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise WorkflowError(
            f"{label} must be a normalized relative path: {value!r}"
        )


def validate_benchmark_manifest(
    path: Path, *, pack_root: Path | None = None
) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if pack_root is not None:
        root = pack_root.expanduser().resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise WorkflowError(f"benchmark manifest escapes pack root: {path}") from exc
    value = read_contract(path, BENCHMARK_MANIFEST_SCHEMA)
    cases = value["cases"]
    case_ids = [str(item["case_id"]) for item in cases]
    if len(case_ids) != len(set(case_ids)):
        raise WorkflowError("benchmark manifest contains duplicate case IDs")
    trial_keys = [
        (str(item["task_id"]), int(item["repetition"])) for item in cases
    ]
    if len(trial_keys) != len(set(trial_keys)):
        raise WorkflowError(
            "benchmark manifest contains duplicate task/repetition identities"
        )
    for case in cases:
        case_id = str(case["case_id"])
        for key in ("writable_paths", "writable_trees", "disposable_trees"):
            for relative in case["allowed_writable_scope"].get(key, []):
                _safe_relative(str(relative), f"case {case_id} {key}")
        availability = case["availability"]
        expected_class = case["expected_evidence_class"]
        if availability["state"] == "available":
            if availability.get("reason") is not None:
                raise WorkflowError(
                    f"available benchmark case {case_id} must not declare an unavailable reason"
                )
            if expected_class == "unavailable":
                raise WorkflowError(
                    f"available benchmark case {case_id} cannot expect unavailable evidence"
                )
        else:
            if not availability.get("reason"):
                raise WorkflowError(
                    f"unavailable benchmark case {case_id} requires a reason"
                )
            if expected_class != "unavailable":
                raise WorkflowError(
                    f"unavailable benchmark case {case_id} must use expected evidence class 'unavailable'"
                )
    return value


def _trial_summary(trial: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if trial is None:
        return None
    return {
        "trial_id": trial.get("trial_id"),
        "verdict": trial.get("verdict"),
        "duration_seconds": trial.get("duration_seconds"),
        "tokens": trial.get("tokens"),
        "input_tokens": trial.get("input_tokens"),
        "cached_input_tokens": trial.get("cached_input_tokens"),
        "output_tokens": trial.get("output_tokens"),
        "provider_billed_cost": trial.get("provider_billed_cost"),
        "local_estimated_cost": trial.get("local_estimated_cost"),
        "currency": trial.get("currency"),
        "price_catalog_id": trial.get("price_catalog_id"),
        "final_receipt_sha256": trial.get("final_receipt_sha256"),
        "errors": trial.get("errors", []),
    }


def _index_trials(
    role: str, trials: Sequence[dict[str, Any]]
) -> dict[tuple[str, int], dict[str, Any]]:
    result: dict[tuple[str, int], dict[str, Any]] = {}
    for trial in trials:
        key = (str(trial.get("task_id")), int(trial.get("repetition") or 0))
        if key in result:
            raise WorkflowError(f"duplicate {role} benchmark trial identity: {key}")
        result[key] = trial
    return result


def _cohort_identity(
    role: str,
    expected: Mapping[str, Any],
    trials: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    verified: list[str] = []
    unverified: list[str] = []
    for manifest_field, trial_field in IDENTITY_FIELDS:
        expected_value = expected.get(manifest_field)
        actual_values = [trial.get(trial_field) for trial in trials]
        non_null = {item for item in actual_values if item is not None}
        if len(non_null) > 1:
            raise WorkflowError(
                f"{role} cohort {manifest_field} is not homogeneous: "
                f"{sorted(str(item) for item in non_null)}"
            )
        if expected_value is None:
            unverified.append(manifest_field)
            continue
        contradictions = sorted(
            str(item) for item in non_null if item != expected_value
        )
        if contradictions:
            raise WorkflowError(
                f"{role} cohort {manifest_field} mismatch: "
                f"expected {expected_value!r}, observed {contradictions}"
            )
        if not actual_values or any(item is None for item in actual_values):
            unverified.append(manifest_field)
        else:
            verified.append(manifest_field)
    return {
        "state": "verified" if not unverified else "not_verified",
        "verified_fields": sorted(verified),
        "unverified_fields": sorted(unverified),
    }


def _require_match(
    *,
    role: str,
    case_id: str,
    field: str,
    expected: Any,
    actual: Any,
    missing: list[str],
) -> None:
    if expected is None:
        return
    if actual is None:
        missing.append(field)
        return
    if actual != expected:
        raise WorkflowError(
            f"{role} case {case_id} {field} mismatch: "
            f"expected {expected!r}, observed {actual!r}"
        )


def _validate_case_trial(
    role: str, case: Mapping[str, Any], trial: Mapping[str, Any]
) -> list[str]:
    case_id = str(case["case_id"])
    missing: list[str] = []
    _require_match(
        role=role,
        case_id=case_id,
        field="prompt_sha256",
        expected=case.get("prompt_sha256"),
        actual=trial.get("prompt_sha256"),
        missing=missing,
    )
    source_artifacts = trial.get("source_artifacts")
    artifacts = source_artifacts if isinstance(source_artifacts, Mapping) else {}
    _require_match(
        role=role,
        case_id=case_id,
        field="input_sha256",
        expected=case.get("input_sha256"),
        actual=artifacts.get("workflow-inputs.json"),
        missing=missing,
    )
    fixture = case.get("fixture_provenance")
    if isinstance(fixture, Mapping):
        _require_match(
            role=role,
            case_id=case_id,
            field="fixture_revision",
            expected=fixture.get("revision"),
            actual=trial.get("fixture_revision"),
            missing=missing,
        )
        _require_match(
            role=role,
            case_id=case_id,
            field="fixture_sha256",
            expected=fixture.get("sha256"),
            actual=trial.get("fixture_sha256"),
            missing=missing,
        )
    oracle = case.get("oracle")
    if isinstance(oracle, Mapping):
        _require_match(
            role=role,
            case_id=case_id,
            field="oracle_sha256",
            expected=oracle.get("sha256"),
            actual=trial.get("oracle_sha256"),
            missing=missing,
        )
    reference = case.get("reference")
    if isinstance(reference, Mapping):
        _require_match(
            role=role,
            case_id=case_id,
            field="reference_sha256",
            expected=reference.get("sha256"),
            actual=trial.get("reference_sha256"),
            missing=missing,
        )
    for manifest_field, trial_field in IDENTITY_FIELDS:
        expected = case.get("_cohort", {}).get(manifest_field)
        _require_match(
            role=role,
            case_id=case_id,
            field=manifest_field,
            expected=expected,
            actual=trial.get(trial_field),
            missing=missing,
        )
    return sorted(set(missing))


def build_benchmark_report(
    manifest_path: Path,
    baseline_path: Path,
    candidate_path: Path,
) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve()
    baseline_path = baseline_path.expanduser().resolve()
    candidate_path = candidate_path.expanduser().resolve()
    manifest = validate_benchmark_manifest(manifest_path)
    baseline = load_trials(baseline_path)
    candidate = load_trials(candidate_path)

    baseline_identity = _cohort_identity(
        "baseline", manifest["cohorts"]["baseline"], baseline
    )
    candidate_identity = _cohort_identity(
        "candidate", manifest["cohorts"]["candidate"], candidate
    )
    left = _index_trials("baseline", baseline)
    right = _index_trials("candidate", candidate)

    case_rows: list[dict[str, Any]] = []
    complete_baseline: list[dict[str, Any]] = []
    complete_candidate: list[dict[str, Any]] = []
    missing_baseline = 0
    missing_candidate = 0
    unverified_baseline = 0
    unverified_candidate = 0
    unavailable = 0
    regressions: list[str] = []
    manifest_keys: set[tuple[str, int]] = set()

    for original_case in sorted(manifest["cases"], key=lambda item: item["case_id"]):
        role_expectations = manifest["cohorts"]
        case = dict(original_case)
        key = (str(case["task_id"]), int(case["repetition"]))
        manifest_keys.add(key)
        before = left.get(key)
        after = right.get(key)
        if case["availability"]["state"] == "unavailable":
            if before is not None or after is not None:
                raise WorkflowError(
                    f"unavailable benchmark case {case['case_id']} has trial evidence"
                )
            unavailable += 1
            case_rows.append(
                {
                    "case_id": case["case_id"],
                    "task_id": case["task_id"],
                    "repetition": case["repetition"],
                    "expected_evidence_class": case["expected_evidence_class"],
                    "state": "unavailable",
                    "unavailable_reason": case["availability"].get("reason"),
                    "baseline": None,
                    "candidate": None,
                    "missing_evidence": {"baseline": [], "candidate": []},
                    "regression": False,
                }
            )
            continue

        baseline_missing: list[str] = []
        candidate_missing: list[str] = []
        if before is None:
            missing_baseline += 1
            baseline_missing.append("trial")
        else:
            case["_cohort"] = role_expectations["baseline"]
            baseline_missing.extend(_validate_case_trial("baseline", case, before))
        if after is None:
            missing_candidate += 1
            candidate_missing.append("trial")
        else:
            case["_cohort"] = role_expectations["candidate"]
            candidate_missing.extend(_validate_case_trial("candidate", case, after))
        baseline_missing = sorted(set(baseline_missing))
        candidate_missing = sorted(set(candidate_missing))
        if before is not None and baseline_missing:
            unverified_baseline += 1
        if after is not None and candidate_missing:
            unverified_candidate += 1
        complete = bool(
            before is not None
            and after is not None
            and not baseline_missing
            and not candidate_missing
        )
        if complete:
            complete_baseline.append(before)
            complete_candidate.append(after)
        regression = bool(
            complete
            and before.get("verdict") == "pass"
            and after.get("verdict") != "pass"
        )
        if regression:
            regressions.append(str(case["case_id"]))
        case_rows.append(
            {
                "case_id": case["case_id"],
                "task_id": case["task_id"],
                "repetition": case["repetition"],
                "expected_evidence_class": case["expected_evidence_class"],
                "state": "complete" if complete else "not_verified",
                "unavailable_reason": None,
                "baseline": _trial_summary(before),
                "candidate": _trial_summary(after),
                "missing_evidence": {
                    "baseline": baseline_missing,
                    "candidate": candidate_missing,
                },
                "regression": regression,
            }
        )

    unmatched_baseline = sorted(
        str(trial.get("trial_id"))
        for key, trial in left.items()
        if key not in manifest_keys
    )
    unmatched_candidate = sorted(
        str(trial.get("trial_id"))
        for key, trial in right.items()
        if key not in manifest_keys
    )
    comparison = compare_trials(complete_baseline, complete_candidate)
    report = {
        "schema": BENCHMARK_REPORT_SCHEMA,
        "benchmark_id": manifest["benchmark_id"],
        "manifest_sha256": sha256_file(manifest_path),
        "baseline": {
            **manifest["cohorts"]["baseline"],
            "trial_collection_sha256": sha256_file(baseline_path),
            "trial_count": len(baseline),
            "selected_trial_count": len(complete_baseline),
            "identity_verification": baseline_identity,
        },
        "candidate": {
            **manifest["cohorts"]["candidate"],
            "trial_collection_sha256": sha256_file(candidate_path),
            "trial_count": len(candidate),
            "selected_trial_count": len(complete_candidate),
            "identity_verification": candidate_identity,
        },
        "cases": case_rows,
        "aggregate_metrics": comparison,
        "missingness": {
            "unavailable_case_count": unavailable,
            "missing_baseline_count": missing_baseline,
            "missing_candidate_count": missing_candidate,
            "unverified_baseline_count": unverified_baseline,
            "unverified_candidate_count": unverified_candidate,
            "unmatched_baseline_count": len(unmatched_baseline),
            "unmatched_candidate_count": len(unmatched_candidate),
            "null_metric_policy": "preserve-null",
        },
        "unmatched_trials": {
            "baseline": unmatched_baseline,
            "candidate": unmatched_candidate,
        },
        "regressions": sorted(regressions),
        "reproducible_commands": [
            "agent-workflow eval validate-benchmark <manifest.json>",
            "agent-workflow eval benchmark-report <manifest.json> <baseline.json> <candidate.json> --output <report.json>",
        ],
    }
    validate_instance(report, BENCHMARK_REPORT_SCHEMA, artifact="benchmark report")
    return report


def render_benchmark_markdown(report: Mapping[str, Any]) -> str:
    aggregate = report["aggregate_metrics"]
    lines = [
        f"# Benchmark report: {report['benchmark_id']}",
        "",
        f"- Baseline cohort: `{report['baseline']['cohort_id']}`",
        f"- Candidate cohort: `{report['candidate']['cohort_id']}`",
        f"- Paired verified cases: {aggregate['paired_n']}",
        f"- Winner: `{aggregate['winner'] or 'not-established'}`",
        f"- Unavailable cases: {report['missingness']['unavailable_case_count']}",
        f"- Not-verified baseline cases: {report['missingness']['missing_baseline_count'] + report['missingness']['unverified_baseline_count']}",
        f"- Not-verified candidate cases: {report['missingness']['missing_candidate_count'] + report['missingness']['unverified_candidate_count']}",
        f"- Unmatched baseline trials: {report['missingness']['unmatched_baseline_count']}",
        f"- Unmatched candidate trials: {report['missingness']['unmatched_candidate_count']}",
        f"- Regressions: {len(report['regressions'])}",
        "",
        "## Case results",
        "",
        "| Case | State | Baseline | Candidate | Missing evidence | Regression |",
        "|---|---|---|---|---|---|",
    ]
    for case in report["cases"]:
        before = case["baseline"]["verdict"] if case["baseline"] else "unavailable"
        after = case["candidate"]["verdict"] if case["candidate"] else "unavailable"
        missing = case["missing_evidence"]
        missing_text = "; ".join(
            f"{role}: {', '.join(values)}"
            for role, values in (("baseline", missing["baseline"]), ("candidate", missing["candidate"]))
            if values
        ) or "none"
        lines.append(
            f"| {case['case_id']} | {case['state']} | {before} | {after} | "
            f"{missing_text} | {'yes' if case['regression'] else 'no'} |"
        )
    lines.extend(["", "## Reproducible commands", ""])
    lines.extend(f"- `{command}`" for command in report["reproducible_commands"])
    return "\n".join(lines) + "\n"


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
            ("final-status.json", "agent-workflow/session-status/v2", "status"),
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
    supplemental_repairs = (
        supplemental_repairs_for_run(run_dir, receipt_digest)
        if receipt_verified and receipt_digest is not None
        else []
    )
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
        "supplemental_repairs": supplemental_repairs,
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
