"""Immutable evidence records extracted from sealed evaluation runs."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..errors import WorkflowError
from ..receipts import verify_seal
from ..util import atomic_write_json, sha256_file

TRIAL_EVIDENCE_SCHEMA = "agent-workflow/trial-evidence/v1"


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read evidence input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"evidence input must be an object: {path}")
    return value


def _number(value: object) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else None


def _stage(metrics: dict[str, Any], name: str) -> dict[str, Any]:
    stages = metrics.get("stages")
    if not isinstance(stages, list):
        raise WorkflowError("execution metrics has no stages")
    for stage in stages:
        if isinstance(stage, dict) and stage.get("stage") == name:
            return stage
    raise WorkflowError(f"execution metrics is missing {name} stage")


def extract_trial(run_dir: Path) -> dict[str, Any]:
    """Extract one comparison-ready trial from a sealed run without mutation."""
    run_dir = run_dir.resolve()
    receipt_path = run_dir / "final-receipt.json"
    if not receipt_path.is_file():
        raise WorkflowError(f"final receipt is missing: {receipt_path}")
    receipt = verify_seal(run_dir, expected_sha256=sha256_file(receipt_path))
    provenance = _load(run_dir / "run-provenance.json")
    metrics = _load(run_dir / "execution-metrics.json")
    score = _load(run_dir / "scores" / "score-set.json")
    verdict = score.get("verdict")
    if verdict not in {"pass", "fail", "invalid"}:
        raise WorkflowError("score-set has no valid verdict")
    total = _stage(metrics, "total")
    runtime_path = run_dir / "evaluation-runtime.json"
    runtime = _load(runtime_path) if runtime_path.is_file() else {}
    input_tokens, output_tokens = _number(total.get("input_tokens")), _number(total.get("output_tokens"))
    tokens = input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None
    artifacts = {
        item["path"]: item["sha256"]
        for item in receipt.get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str) and isinstance(item.get("sha256"), str)
    }
    def field(name: str) -> Any:
        return runtime.get(name, provenance.get(name))
    return {
        "schema": TRIAL_EVIDENCE_SCHEMA,
        "trial_id": str(provenance.get("session_id") or run_dir.name),
        "run_path": str(run_dir),
        "final_receipt_sha256": sha256_file(receipt_path),
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
        "cached_input_tokens": _number(total.get("cached_input_tokens")),
        "output_tokens": output_tokens,
        "provider_total_tokens": _number(total.get("provider_total_tokens")),
        "tokens": tokens,
        "cost": _number(total.get("cost")),
        "currency": total.get("currency") if isinstance(total.get("currency"), str) else None,
        "retry_count": total.get("retry_count") if isinstance(total.get("retry_count"), int) else None,
        "errors": total.get("errors") if isinstance(total.get("errors"), list) else [],
        "steer_count": total.get("steer_count") if isinstance(total.get("steer_count"), int) else None,
        "steer_acknowledged_count": total.get("steer_acknowledged_count") if isinstance(total.get("steer_acknowledged_count"), int) else None,
        "source_artifacts": artifacts,
    }


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
    atomic_write_json(output, value)
    return value


def load_trials(path: Path) -> list[dict[str, Any]]:
    value = _load(path)
    if value.get("schema") != TRIAL_EVIDENCE_SCHEMA or not isinstance(value.get("trials"), list):
        raise WorkflowError(f"invalid trial evidence file: {path}")
    trials = value["trials"]
    if not all(isinstance(item, dict) and item.get("schema") == TRIAL_EVIDENCE_SCHEMA for item in trials):
        raise WorkflowError(f"invalid trial record in {path}")
    currencies = {item.get("currency") for item in trials if item.get("cost") is not None}
    if len(currencies) > 1:
        raise WorkflowError(f"multiple cost currencies in evidence file: {path}")
    return trials
