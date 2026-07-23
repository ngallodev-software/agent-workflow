"""Sealed, provider-neutral execution metrics and control evidence."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .contracts import validate_instance
from .errors import WorkflowError
from .messages import replay_messages
from .util import atomic_write_json

METRICS_SCHEMA = "agent-workflow/execution-metrics/v1"
CONTROL_SCHEMA = "agent-workflow/control-event/v1"


def _number(value: object) -> int | float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        return None
    return value


def normalize_usage(usage: object) -> dict[str, Any]:
    """Normalize provider usage without converting absent facts to zero."""
    source = usage if isinstance(usage, dict) else {}
    input_tokens = _number(source.get("input_tokens", source.get("prompt_tokens")))
    details = source.get("prompt_tokens_details")
    nested_cached = details.get("cached_tokens") if isinstance(details, dict) else None
    cached = _number(
        source.get(
            "cached_input_tokens",
            source.get("cache_read_input_tokens", source.get("cached_tokens", nested_cached)),
        )
    )
    output = _number(source.get("output_tokens", source.get("completion_tokens")))
    provider_total = _number(source.get("total_tokens"))
    cost = _number(source.get("cost", source.get("total_cost")))
    currency = source.get("currency") if isinstance(source.get("currency"), str) else None
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached,
        "output_tokens": output,
        "provider_total_tokens": provider_total,
        "cost": cost,
        "currency": currency,
    }


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _latency_seconds(started: object, first: object) -> float | None:
    left, right = _parse_timestamp(started), _parse_timestamp(first)
    if left is None or right is None:
        return None
    return round(max(0.0, (right - left).total_seconds()), 6)


def _empty_stage(name: str) -> dict[str, Any]:
    return {
        "stage": name,
        **normalize_usage(None),
        "elapsed_seconds": None,
        "first_output_latency_seconds": None,
        "retry_count": 0,
        "errors": [],
        "steer_count": 0,
        "steer_acknowledged_count": 0,
        "steer_pending_count": 0,
    }


def _verification_duration(run_dir: Path) -> float | None:
    """Return only explicitly recorded post-command durations."""
    path = run_dir / "collections" / "commands-post.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read command collection {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("commands"), list):
        raise WorkflowError(f"invalid command collection {path}")
    durations = [
        _number(item.get("duration_seconds"))
        for item in value["commands"]
        if isinstance(item, dict)
    ]
    known = [duration for duration in durations if duration is not None]
    return round(sum(known), 6) if known else None


def build_execution_metrics(run_dir: Path, *, elapsed_seconds: float | None = None) -> dict[str, Any]:
    try:
        provenance = json.loads((run_dir / "run-provenance.json").read_text(encoding="utf-8"))
        status = json.loads((run_dir / "final-status.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot build execution metrics for {run_dir}: {exc}") from exc
    if not isinstance(provenance, dict) or not isinstance(status, dict):
        raise WorkflowError("execution metrics inputs must be JSON objects")

    messages = replay_messages(run_dir)
    steer_ids = {m["message_id"] for m in messages if m["kind"] == "steer"}
    acked = {
        m["correlation_id"] for m in messages
        if m["kind"] == "ack" and m["correlation_id"] in steer_ids
    }
    errors = [
        {"category": status.get("failure_category"), "detail": item}
        for item in status.get("pump_errors", []) if isinstance(item, str)
    ]
    if status.get("status") == "failed" and not errors:
        errors.append({"category": status.get("failure_category"), "detail": None})

    orchestrator = _empty_stage("orchestrator")
    orchestrator.update({
        **normalize_usage(provenance.get("usage")),
        "elapsed_seconds": round(elapsed_seconds, 6) if elapsed_seconds is not None else _number(status.get("wall_seconds")),
        "first_output_latency_seconds": _latency_seconds(provenance.get("started_at"), provenance.get("first_output_at")),
        "errors": errors,
        "steer_count": len(steer_ids),
        "steer_acknowledged_count": len(acked),
        "steer_pending_count": len(steer_ids - acked),
    })
    child_stages = []
    for actor in sorted({m["actor"] for m in messages if m["direction"] == "child_to_parent"}):
        child = _empty_stage(f"child:{actor}")
        actor_errors = [m for m in messages if m["actor"] == actor and m["kind"] == "error"]
        child["errors"] = [{"category": "child_message", "detail": m["content"]} for m in actor_errors]
        child_stages.append(child)
    verification = _empty_stage("verification")
    verification["elapsed_seconds"] = _verification_duration(run_dir)
    total = {**orchestrator, "stage": "total"}
    value = {
        "schema": METRICS_SCHEMA,
        "session_id": provenance.get("session_id"),
        "stages": [orchestrator, *child_stages, verification, total],
    }
    validate_instance(value, METRICS_SCHEMA, artifact=str(run_dir / "execution-metrics.json"))
    return value


def _atomic_write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            for record in records:
                stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def write_control_events(run_dir: Path) -> list[dict[str, Any]]:
    records = []
    for message in replay_messages(run_dir):
        record = {"schema": CONTROL_SCHEMA, **{k: v for k, v in message.items() if k != "schema"}}
        validate_instance(record, CONTROL_SCHEMA, artifact=str(run_dir / "control-events.jsonl"))
        records.append(record)
    _atomic_write_jsonl(run_dir / "control-events.jsonl", records)
    return records


def write_execution_evidence(run_dir: Path, *, elapsed_seconds: float | None = None) -> dict[str, Any]:
    write_control_events(run_dir)
    metrics = build_execution_metrics(run_dir, elapsed_seconds=elapsed_seconds)
    atomic_write_json(run_dir / "execution-metrics.json", metrics)
    return metrics
