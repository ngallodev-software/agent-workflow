from __future__ import annotations

import hashlib
import json
import math
import os
import stat
from pathlib import Path
from typing import Any, Mapping

from .contracts import validate_instance
from .errors import WorkflowError
from .util import atomic_write_json, utc_now

PROVIDER_EVIDENCE_SCHEMA = "agent-workflow/provider-evidence/v1"
MAX_PROVIDER_EVENT_BYTES = 16 * 1024 * 1024
USAGE_MODES = {"delta", "cumulative", "terminal"}


def _number(value: object) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0 or not math.isfinite(float(value)):
        return None
    return value


def _capture_raw_events(path: Path) -> tuple[bytes, int, str | None]:
    """Read and hash one stable regular raw-event file without following symlinks."""
    try:
        inspected = path.lstat()
    except FileNotFoundError:
        return b"", 0, None
    except OSError as exc:
        raise WorkflowError(f"cannot inspect provider event file {path}: {exc}") from exc
    if stat.S_ISLNK(inspected.st_mode) or not stat.S_ISREG(inspected.st_mode):
        raise WorkflowError(f"provider event file must be a regular non-symlink file: {path}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WorkflowError(f"cannot open provider event file {path}: {exc}") from exc
    captured = bytearray()
    digest = hashlib.sha256()
    total = 0
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or (before.st_dev, before.st_ino) != (
            inspected.st_dev,
            inspected.st_ino,
        ):
            raise WorkflowError(f"provider event file changed before capture: {path}")
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
            remaining = MAX_PROVIDER_EVENT_BYTES + 1 - len(captured)
            if remaining > 0:
                captured.extend(chunk[:remaining])
        after = os.fstat(stream.fileno())
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ctime_ns != after.st_ctime_ns
        or total != after.st_size
    ):
        raise WorkflowError(f"provider event file changed during capture: {path}")
    return bytes(captured), total, digest.hexdigest()


def _usage_payload(event: Mapping[str, Any]) -> dict[str, Any] | None:
    usage = event.get("usage")
    if isinstance(usage, Mapping):
        return dict(usage)
    message = event.get("message")
    if isinstance(message, Mapping) and isinstance(message.get("usage"), Mapping):
        return dict(message["usage"])
    item = event.get("item")
    if isinstance(item, Mapping) and isinstance(item.get("usage"), Mapping):
        return dict(item["usage"])
    return None


def classify_usage_event(
    event: Mapping[str, Any], stream_format: str
) -> tuple[dict[str, Any], str] | None:
    """Classify only provider surfaces with an explicit or documented boundary."""
    usage = _usage_payload(event)
    explicit = event.get("usage_mode", event.get("usage_type"))
    if usage is not None:
        embedded = usage.pop("mode", None)
        mode = embedded if embedded in USAGE_MODES else explicit
        if mode in USAGE_MODES:
            return usage, str(mode)
    event_type = str(event.get("type", ""))
    if stream_format == "codex-jsonl" and event_type == "turn.completed":
        return (usage or {}), "terminal"
    if stream_format == "claude-stream-json":
        if event_type == "result":
            payload = usage or {}
            billed = event.get("total_cost_usd")
            if _number(billed) is not None:
                payload["provider_billed_cost"] = billed
                payload["currency"] = "USD"
            return payload, "terminal"
        if event_type == "assistant" and usage is not None:
            # Claude Code assistant records correspond to individual Messages API
            # responses; they are deltas within the enclosing CLI run.
            return usage, "delta"
    return None


def normalize_provider_usage(usage: Mapping[str, Any]) -> dict[str, Any]:
    details = usage.get("input_tokens_details")
    if not isinstance(details, Mapping):
        details = usage.get("prompt_tokens_details")
    if not isinstance(details, Mapping):
        details = {}
    output_details = usage.get("output_tokens_details")
    if not isinstance(output_details, Mapping):
        output_details = {}

    def first(*names: str) -> int | float | None:
        for name in names:
            if name in usage:
                value = _number(usage[name])
                if value is not None:
                    return value
        return None

    cached = first(
        "cached_input_tokens", "cache_read_input_tokens", "cached_tokens"
    )
    if cached is None:
        cached = _number(details.get("cached_tokens"))
    reasoning = first("reasoning_output_tokens", "reasoning_tokens")
    if reasoning is None:
        reasoning = _number(output_details.get("reasoning_tokens"))
    billed = first("provider_billed_cost", "total_cost_usd")
    untyped_cost = first("cost", "total_cost")
    if billed is None and untyped_cost is not None and usage.get("cost_source") == "provider":
        billed = untyped_cost
    estimated = first("local_estimated_cost")
    if estimated is None and untyped_cost is not None and usage.get("cost_source") == "local_estimate":
        estimated = untyped_cost
    currency = usage.get("currency")
    return {
        "input_tokens": first("input_tokens", "prompt_tokens"),
        "cached_input_tokens": cached,
        "cache_write_input_tokens": first(
            "cache_write_input_tokens", "cache_creation_input_tokens"
        ),
        "output_tokens": first("output_tokens", "completion_tokens"),
        "reasoning_output_tokens": reasoning,
        "provider_total_tokens": first("total_tokens", "provider_total_tokens"),
        "provider_billed_cost": billed,
        "local_estimated_cost": estimated,
        "currency": currency if isinstance(currency, str) and currency else None,
        "price_catalog_id": (
            usage.get("price_catalog_id")
            if isinstance(usage.get("price_catalog_id"), str)
            and usage.get("price_catalog_id")
            else None
        ),
    }


def _merge(records: list[dict[str, Any]]) -> tuple[dict[str, Any], bool, list[str]]:
    modes = [str(item["mode"]) for item in records]
    reasons: list[str] = []
    fields = (
        "input_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "provider_total_tokens",
        "provider_billed_cost",
        "local_estimated_cost",
    )

    def empty() -> dict[str, Any]:
        aggregate = {name: None for name in fields}
        aggregate.update(currency=None, price_catalog_id=None)
        return aggregate

    def cost_metadata_complete(usage: Mapping[str, Any]) -> bool:
        currency = usage.get("currency")
        catalog = usage.get("price_catalog_id")
        if usage.get("provider_billed_cost") is not None and currency is None:
            reasons.append("PROVIDER_COST_MISSING_CURRENCY")
            return False
        if usage.get("local_estimated_cost") is not None and (
            currency is None or catalog is None
        ):
            reasons.append("LOCAL_ESTIMATE_MISSING_PRICE_METADATA")
            return False
        return True

    aggregate = empty()
    if not records:
        reasons.append("NO_CLASSIFIED_USAGE")
        return aggregate, False, reasons

    terminals = [item for item in records if item["mode"] == "terminal"]
    if terminals:
        normalized = [item["usage"] for item in terminals]
        if any(item != normalized[0] for item in normalized[1:]):
            reasons.append("CONFLICTING_TERMINAL_UPDATES")
            return empty(), False, reasons
        selected = normalized[0]
        aggregate.update(selected)
        if len(terminals) > 1:
            reasons.append("MULTIPLE_EQUIVALENT_TERMINAL_UPDATES")
        if len(set(modes)) > 1:
            reasons.append("MIXED_MODES_TERMINAL_AUTHORITATIVE")
        if not any(_number(selected.get(field)) is not None for field in fields):
            reasons.append("TERMINAL_USAGE_EMPTY")
            return aggregate, False, reasons
        return aggregate, cost_metadata_complete(aggregate), reasons

    unique_modes = set(modes)
    if unique_modes == {"delta"}:
        for field in fields:
            values = [item["usage"].get(field) for item in records]
            known = [value for value in values if _number(value) is not None]
            aggregate[field] = sum(known) if known else None
        currencies = {
            item["usage"].get("currency")
            for item in records
            if item["usage"].get("currency") is not None
        }
        catalogs = {
            item["usage"].get("price_catalog_id")
            for item in records
            if item["usage"].get("price_catalog_id") is not None
        }
        if len(currencies) > 1 or len(catalogs) > 1:
            reasons.append("INCONSISTENT_DELTA_COST_METADATA")
            return aggregate, False, reasons
        aggregate["currency"] = next(iter(currencies), None)
        aggregate["price_catalog_id"] = next(iter(catalogs), None)
        if not any(_number(aggregate.get(field)) is not None for field in fields):
            reasons.append("DELTA_USAGE_EMPTY")
            return aggregate, False, reasons
        return aggregate, cost_metadata_complete(aggregate), reasons

    if unique_modes == {"cumulative"}:
        usages = [item["usage"] for item in records]
        for field in fields:
            previous: int | float | None = None
            for usage in usages:
                value = _number(usage.get(field))
                if value is None:
                    continue
                if previous is not None and value < previous:
                    reasons.append("NONMONOTONIC_CUMULATIVE_USAGE")
                    return empty(), False, reasons
                previous = value
        currencies = {usage.get("currency") for usage in usages if usage.get("currency") is not None}
        catalogs = {
            usage.get("price_catalog_id")
            for usage in usages
            if usage.get("price_catalog_id") is not None
        }
        if len(currencies) > 1 or len(catalogs) > 1:
            reasons.append("INCONSISTENT_CUMULATIVE_COST_METADATA")
            return empty(), False, reasons
        if not all(cost_metadata_complete(usage) for usage in usages):
            return empty(), False, reasons
        aggregate.update(usages[-1])
        if not any(_number(aggregate.get(field)) is not None for field in fields):
            reasons.append("CUMULATIVE_USAGE_EMPTY")
            return aggregate, False, reasons
        return aggregate, True, reasons

    reasons.append("MIXED_NONTERMINAL_USAGE_MODES")
    return aggregate, False, reasons


def build_provider_evidence(
    *,
    events_path: Path,
    stream_format: str,
    executor: str | None,
    agent_run_id: str,
    retry_of: str | None = None,
    capture_exceeded: bool = False,
) -> dict[str, Any]:
    events_path = Path(events_path)
    captured, raw_size, raw_events_sha256 = _capture_raw_events(events_path)
    if raw_size > MAX_PROVIDER_EVENT_BYTES:
        capture_exceeded = True
    classified: list[dict[str, Any]] = []
    seen_event_ids: dict[str, str] = {}
    seen_unidentified_raw: set[str] = set()
    sequence = 0
    malformed = 0
    ambiguous_delta_duplicates = 0
    conflicting_event_ids = 0
    if captured:
        if len(captured) > MAX_PROVIDER_EVENT_BYTES:
            capture_exceeded = True
            captured = captured[:MAX_PROVIDER_EVENT_BYTES]
        for raw in captured.splitlines():
            if not raw:
                continue
            sequence += 1
            digest = hashlib.sha256(raw).hexdigest()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(event, Mapping):
                malformed += 1
                continue
            update = classify_usage_event(event, stream_format)
            event_identity = event.get("event_id", event.get("id"))
            if isinstance(event_identity, (str, int)) and not isinstance(event_identity, bool):
                request_identity = event.get(
                    "request_id", event.get("response_id", event.get("turn_id", ""))
                )
                identity = (
                    f"{stream_format}:{event.get('type', 'unknown')}:"
                    f"{request_identity}:{event_identity}"
                )
                prior_digest = seen_event_ids.get(identity)
                if prior_digest is not None:
                    if prior_digest != digest:
                        conflicting_event_ids += 1
                    continue
                seen_event_ids[identity] = digest
            else:
                if digest in seen_unidentified_raw:
                    if update is not None and update[1] == "delta":
                        ambiguous_delta_duplicates += 1
                    continue
                seen_unidentified_raw.add(digest)
            if update is None:
                continue
            usage, mode = update
            classified.append(
                {
                    "sequence": sequence,
                    "event_sha256": digest,
                    "event_type": str(event.get("type", "unknown")),
                    "mode": mode,
                    "usage": normalize_provider_usage(usage),
                }
            )
    aggregate, usage_complete, reasons = _merge(classified)
    if ambiguous_delta_duplicates:
        reasons.append("AMBIGUOUS_DUPLICATE_DELTA_EVENTS")
    if conflicting_event_ids:
        reasons.append("CONFLICTING_PROVIDER_EVENT_ID")
    if malformed:
        reasons.append("MALFORMED_RAW_EVENTS_PRESENT")
    if capture_exceeded:
        reasons.append("RAW_EVENT_CAPTURE_LIMIT_EXCEEDED")
    evidence = {
        "schema": PROVIDER_EVIDENCE_SCHEMA,
        "agent_run_id": agent_run_id,
        "executor": executor,
        "stream_format": stream_format,
        "created_at": utc_now(),
        "raw_events_path": events_path.name,
        "raw_events_sha256": raw_events_sha256,
        "raw_event_bytes": raw_size,
        "capture_limit_bytes": MAX_PROVIDER_EVENT_BYTES,
        "capture_complete": not capture_exceeded,
        "malformed_event_count": malformed,
        "classified_usage_count": len(classified),
        "retry_of_agent_run_id": retry_of,
        "usage_complete": (
            usage_complete
            and not capture_exceeded
            and malformed == 0
            and ambiguous_delta_duplicates == 0
            and conflicting_event_ids == 0
        ),
        "incomplete_reasons": sorted(set(reasons)),
        "usage_events": classified,
        "aggregate": aggregate,
    }
    validate_instance(evidence, PROVIDER_EVIDENCE_SCHEMA, artifact="provider evidence")
    return evidence


def write_provider_evidence(
    run_dir: Path,
    *,
    capture_exceeded: bool = False,
    stream_format: str | None = None,
    executor: str | None = None,
) -> dict[str, Any]:
    from .contracts import read_contract

    run_dir = Path(run_dir)
    provenance = read_contract(
        run_dir / "run-provenance.json", "agent-workflow/run-provenance/v1"
    )
    evidence = build_provider_evidence(
        events_path=run_dir / "executor-events.jsonl",
        stream_format=stream_format or str(provenance.get("stream_format") or "text"),
        executor=(
            executor
            if executor is not None
            else (str(provenance["executor"]) if provenance.get("executor") else None)
        ),
        agent_run_id=str(provenance["agent_run_id"]),
        retry_of=(
            str(provenance["retry_of_agent_run_id"])
            if provenance.get("retry_of_agent_run_id")
            else None
        ),
        capture_exceeded=capture_exceeded,
    )
    path = run_dir / "provider-evidence.json"
    atomic_write_json(path, evidence)
    return evidence
