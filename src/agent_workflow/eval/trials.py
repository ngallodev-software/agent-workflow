"""Immutable evidence records extracted from sealed evaluation runs."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..contracts import read_contract, validate_instance
from ..errors import WorkflowError
from ..receipts import read_sealed_contract, verify_seal_details
from ..util import atomic_write_json, sha256_file
from .scoring import validate_score_set

TRIAL_EVIDENCE_SCHEMA = "agent-workflow/trial-evidence/v2"


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read evidence input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"evidence input must be an object: {path}")
    return value


def _number(value: object) -> int | float | None:
    return (
        value
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value >= 0
        else None
    )


def _stage(metrics: dict[str, Any], name: str) -> dict[str, Any]:
    stages = metrics.get("stages")
    if not isinstance(stages, list):
        raise WorkflowError("execution metrics has no stages")
    for stage in stages:
        if isinstance(stage, dict) and stage.get("stage") == name:
            return stage
    raise WorkflowError(f"execution metrics is missing {name} stage")


def extract_trial(run_dir: Path) -> dict[str, Any]:
    """Extract one comparison-ready trial from a sealed, complete evidence run."""
    run_dir = run_dir.resolve()
    receipt_path = run_dir / "final-receipt.json"
    if not receipt_path.is_file():
        raise WorkflowError(f"final receipt is missing: {receipt_path}")
    receipt, final_receipt_sha256 = verify_seal_details(run_dir)
    provenance, _ = read_sealed_contract(
        run_dir,
        receipt,
        "run-provenance.json",
        "agent-workflow/run-provenance/v1",
    )
    metrics, _ = read_sealed_contract(
        run_dir,
        receipt,
        "execution-metrics.json",
        "agent-workflow/execution-metrics/v1",
    )
    provider, _ = read_sealed_contract(
        run_dir,
        receipt,
        "provider-evidence.json",
        "agent-workflow/provider-evidence/v1",
    )
    if not provider["capture_complete"]:
        raise WorkflowError("provider evidence capture is incomplete")
    if provider["malformed_event_count"]:
        raise WorkflowError("provider evidence contains malformed raw events")
    if not provider["usage_complete"]:
        raise WorkflowError(
            "provider usage evidence is incomplete: "
            + ", ".join(provider["incomplete_reasons"])
        )
    score = validate_score_set(
        run_dir,
        _load(run_dir / "scores" / "score-set.json"),
        final_receipt=receipt,
        expected_final_receipt_sha256=final_receipt_sha256,
    )
    verdict = score.get("verdict")
    if verdict not in {"pass", "fail", "invalid"}:
        raise WorkflowError("score-set has no valid verdict")
    total = _stage(metrics, "total")
    aggregate = provider["aggregate"]
    sealed_paths = {
        item.get("path")
        for item in receipt.get("artifacts", [])
        if isinstance(item, dict)
    }
    runtime = (
        read_sealed_contract(
            run_dir,
            receipt,
            "evaluation-runtime.json",
            "agent-workflow/evaluation-runtime/v1",
        )[0]
        if "evaluation-runtime.json" in sealed_paths
        else {}
    )
    input_tokens = _number(aggregate.get("input_tokens"))
    output_tokens = _number(aggregate.get("output_tokens"))
    tokens = (
        input_tokens + output_tokens
        if input_tokens is not None and output_tokens is not None
        else None
    )
    provider_cost = _number(aggregate.get("provider_billed_cost"))
    local_cost = _number(aggregate.get("local_estimated_cost"))
    currency = aggregate.get("currency") if isinstance(aggregate.get("currency"), str) else None
    catalog = (
        aggregate.get("price_catalog_id")
        if isinstance(aggregate.get("price_catalog_id"), str)
        else None
    )
    if provider_cost is not None and currency is None:
        raise WorkflowError("provider-billed cost requires a currency")
    if local_cost is not None and (currency is None or catalog is None):
        raise WorkflowError("local cost estimate requires currency and price_catalog_id")
    artifacts = {
        item["path"]: item["sha256"]
        for item in receipt.get("artifacts", [])
        if isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and isinstance(item.get("sha256"), str)
    }

    def field(name: str) -> Any:
        return runtime.get(name, provenance.get(name))

    result = {
        "schema": TRIAL_EVIDENCE_SCHEMA,
        "trial_id": str(provenance.get("session_id") or run_dir.name),
        "run_path": str(run_dir),
        "final_receipt_sha256": final_receipt_sha256,
        "provider_evidence_sha256": artifacts.get("provider-evidence.json"),
        "raw_events_sha256": provider["raw_events_sha256"],
        "verdict": verdict,
        "fixture_revision": field("fixture_revision"),
        "task_id": field("ticket_id") or field("task_id"),
        "base_revision": field("base_revision"),
        "prompt_sha256": artifacts.get("prompt.md"),
        "oracle_sha256": field("oracle_sha256"),
        "acceptance_commands_sha256": artifacts.get("collections/commands-post.json"),
        "scope_policy_sha256": field("scope_policy_sha256"),
        "scorer_versions_sha256": field("scorer_versions_sha256"),
        "sandbox": field("sandbox"),
        "budget_sha256": field("budget_sha256"),
        "repetition": field("repetition"),
        "duration_seconds": _number(total.get("elapsed_seconds")),
        "input_tokens": input_tokens,
        "cached_input_tokens": _number(aggregate.get("cached_input_tokens")),
        "cache_write_input_tokens": _number(aggregate.get("cache_write_input_tokens")),
        "output_tokens": output_tokens,
        "reasoning_output_tokens": _number(aggregate.get("reasoning_output_tokens")),
        "provider_total_tokens": _number(aggregate.get("provider_total_tokens")),
        "tokens": tokens,
        "provider_billed_cost": provider_cost,
        "local_estimated_cost": local_cost,
        "currency": currency,
        "price_catalog_id": catalog,
        "retry_of_run_id": provider.get("retry_of_run_id"),
        "retry_count": total.get("retry_count") if isinstance(total.get("retry_count"), int) else None,
        "errors": total.get("errors") if isinstance(total.get("errors"), list) else [],
        "steer_count": total.get("steer_count") if isinstance(total.get("steer_count"), int) else None,
        "steer_acknowledged_count": total.get("steer_acknowledged_count") if isinstance(total.get("steer_acknowledged_count"), int) else None,
        "source_artifacts": artifacts,
    }
    validate_instance(result, TRIAL_EVIDENCE_SCHEMA, artifact="trial evidence")
    return result


def collect_trials(run_dirs: Iterable[Path], output: Path) -> dict[str, Any]:
    trials = [extract_trial(path) for path in run_dirs]
    ids = [trial["trial_id"] for trial in trials]
    if len(ids) != len(set(ids)):
        raise WorkflowError("duplicate trial IDs")
    value = {
        "schema": TRIAL_EVIDENCE_SCHEMA,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "trials": trials,
    }
    validate_instance(value, TRIAL_EVIDENCE_SCHEMA, artifact="trial evidence collection")
    atomic_write_json(output, value)
    return value


def load_trials(path: Path) -> list[dict[str, Any]]:
    value = read_contract(path, TRIAL_EVIDENCE_SCHEMA)
    trials = value.get("trials")
    if not isinstance(trials, list):
        raise WorkflowError(f"trial evidence collection expected: {path}")
    provider_currencies = {
        item.get("currency")
        for item in trials
        if item.get("provider_billed_cost") is not None
    }
    if len(provider_currencies) > 1:
        raise WorkflowError(f"multiple provider cost currencies in evidence file: {path}")
    local_keys = {
        (item.get("currency"), item.get("price_catalog_id"))
        for item in trials
        if item.get("local_estimated_cost") is not None
    }
    if len(local_keys) > 1:
        raise WorkflowError(f"multiple local price catalogs/currencies in evidence file: {path}")
    return trials
