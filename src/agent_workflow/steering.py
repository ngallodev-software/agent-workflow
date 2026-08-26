"""Durable post-launch steering delivery for cooperative executor adapters.

The Agent Run message log remains the request authority.  This module records
adapter delivery outcomes in a separate append-only journal and exposes a
bounded file adapter for executors or wrappers that explicitly opt in.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .contracts import read_agent_run_contract
from .errors import WorkflowError
from .journal import JournalTransactionResult, read_jsonl, transact_jsonl
from .messages import message_digest, replay_messages
from .util import atomic_write_json, utc_now

STEERING_INBOX_ENV = "AGENT_WORKFLOW_STEERING_INBOX"
STEERING_JOURNAL_NAME = "steering-delivery.jsonl"
STEERING_SCHEMA = "agent-workflow/steering-delivery/v1"
STEERING_REQUEST_SCHEMA = "agent-workflow/steering-request/v1"
SUPPORTED_ADAPTERS = frozenset({"unsupported", "control-file-v1"})
ACK_TERMINAL_OUTCOMES = frozenset({"applied", "rejected", "expired"})
DELIVERY_STOP_OUTCOMES = frozenset({
    *ACK_TERMINAL_OUTCOMES, "unsupported", "failed",
})
OUTCOMES = frozenset({"queued", "delivered", *DELIVERY_STOP_OUTCOMES})
DEFAULT_DEADLINE_SECONDS = 300
DEFAULT_MAX_ATTEMPTS = 1


def _journal_path(run_dir: Path) -> Path:
    return run_dir / STEERING_JOURNAL_NAME


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise WorkflowError("steering timestamp must be non-empty")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorkflowError("invalid steering timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _policy(launch: dict[str, Any]) -> dict[str, Any]:
    runtime = launch.get("runtime_policy")
    raw = runtime.get("steering") if isinstance(runtime, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    adapter = raw.get("adapter", "unsupported")
    if adapter not in SUPPORTED_ADAPTERS:
        adapter = "unsupported"
    deadline = raw.get("deadline_seconds", DEFAULT_DEADLINE_SECONDS)
    attempts = raw.get("max_attempts", DEFAULT_MAX_ATTEMPTS)
    if not isinstance(deadline, int) or isinstance(deadline, bool) or deadline < 1:
        deadline = DEFAULT_DEADLINE_SECONDS
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
        attempts = DEFAULT_MAX_ATTEMPTS
    worker_plan = launch.get("worker_plan")
    argv = worker_plan.get("argv") if isinstance(worker_plan, dict) else None
    executable = argv[0] if isinstance(argv, list) and argv and isinstance(argv[0], str) else None
    return {
        "adapter": adapter,
        "deadline_seconds": deadline,
        "max_attempts": attempts,
        "executable": executable,
    }


def _validate_event(value: object, *, expected_sequence: int | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError("steering delivery record must be a JSON object")
    required = {
        "schema", "sequence", "event_id", "agent_run_id", "correlation_id",
        "message_sha256", "at", "adapter", "outcome", "attempt", "reason",
        "executor",
    }
    if set(value) != required:
        raise WorkflowError("invalid steering delivery record fields")
    if value["schema"] != STEERING_SCHEMA:
        raise WorkflowError("unsupported steering delivery schema")
    sequence = value["sequence"]
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise WorkflowError("steering delivery sequence must be positive")
    if expected_sequence is not None and sequence != expected_sequence:
        raise WorkflowError("steering delivery sequence mismatch")
    for field in ("event_id", "correlation_id"):
        try:
            parsed = uuid.UUID(str(value[field]))
        except ValueError as exc:
            raise WorkflowError(f"{field} must be a UUID") from exc
        if str(parsed) != str(value[field]).lower():
            raise WorkflowError(f"{field} must be canonical")
    if not isinstance(value["agent_run_id"], str) or not value["agent_run_id"]:
        raise WorkflowError("steering agent_run_id must be non-empty")
    if not isinstance(value["message_sha256"], str) or not value["message_sha256"].startswith("sha256:"):
        raise WorkflowError("invalid steering message digest")
    _parse_timestamp(value["at"])
    if value["adapter"] not in SUPPORTED_ADAPTERS:
        raise WorkflowError("invalid steering adapter")
    if value["outcome"] not in OUTCOMES:
        raise WorkflowError("invalid steering outcome")
    if not isinstance(value["attempt"], int) or isinstance(value["attempt"], bool) or value["attempt"] < 0:
        raise WorkflowError("invalid steering attempt")
    if not isinstance(value["reason"], str) or not value["reason"]:
        raise WorkflowError("steering reason must be non-empty")
    if value["executor"] is not None and not isinstance(value["executor"], str):
        raise WorkflowError("steering executor must be a string or null")
    return value


def _validate_delivery_record(value: object, line_number: int) -> dict[str, Any]:
    return _validate_event(value, expected_sequence=line_number)


def replay_delivery_events(run_dir: Path) -> list[dict[str, Any]]:
    path = _journal_path(run_dir)
    events = read_jsonl(path, validator=_validate_delivery_record, missing_ok=True, sequence_field="sequence")
    if events and any(event["agent_run_id"] != events[0]["agent_run_id"] for event in events):
        raise WorkflowError("steering journal contains mixed agent run IDs")
    return events

def append_delivery_event(
    run_dir: Path,
    *,
    agent_run_id: str,
    correlation_id: str,
    message_sha256: str,
    adapter: str,
    outcome: str,
    attempt: int,
    reason: str,
    executor: str | None,
) -> dict[str, Any]:
    if adapter not in SUPPORTED_ADAPTERS or outcome not in OUTCOMES:
        raise WorkflowError("invalid steering delivery event")
    path = _journal_path(run_dir)

    def decide(existing: list[dict[str, Any]]) -> JournalTransactionResult[dict[str, Any]]:
        if existing and any(item["agent_run_id"] != existing[0]["agent_run_id"] for item in existing):
            raise WorkflowError("steering journal contains mixed agent run IDs")
        current = [item for item in existing if item["correlation_id"] == correlation_id]
        if any(
            item["agent_run_id"] != agent_run_id
            or item["message_sha256"] != message_sha256
            or item["adapter"] != adapter
            for item in current
        ):
            raise WorkflowError("steering correlation identity conflicts with existing evidence")
        hard_terminal = next(
            (item for item in reversed(current) if item["outcome"] in ACK_TERMINAL_OUTCOMES),
            None,
        )
        if hard_terminal is not None:
            return JournalTransactionResult(value=hard_terminal)
        delivery_stop = next(
            (item for item in reversed(current) if item["outcome"] in DELIVERY_STOP_OUTCOMES),
            None,
        )
        if delivery_stop is not None and outcome not in {"applied", "rejected"}:
            return JournalTransactionResult(value=delivery_stop)
        duplicate = next(
            (
                item for item in reversed(current)
                if item["outcome"] == outcome and item["attempt"] == attempt
            ),
            None,
        )
        if duplicate is not None:
            return JournalTransactionResult(value=duplicate)
        event = {
            "schema": STEERING_SCHEMA,
            "sequence": len(existing) + 1,
            "event_id": str(uuid.uuid4()),
            "agent_run_id": agent_run_id,
            "correlation_id": correlation_id,
            "message_sha256": message_sha256,
            "at": utc_now(),
            "adapter": adapter,
            "outcome": outcome,
            "attempt": attempt,
            "reason": reason,
            "executor": executor,
        }
        event = _validate_event(event, expected_sequence=len(existing) + 1)
        return JournalTransactionResult(value=event, record=event)

    return transact_jsonl(path, validator=_validate_delivery_record, transaction=decide, sequence_field="sequence")

def current_delivery(run_dir: Path, correlation_id: str) -> dict[str, Any] | None:
    matches = [
        item for item in replay_delivery_events(run_dir)
        if item["correlation_id"] == correlation_id
    ]
    return matches[-1] if matches else None


def queue_request(run_dir: Path, message: dict[str, Any]) -> dict[str, Any]:
    launch = read_agent_run_contract(run_dir / "agent-run-contract.json")
    policy = _policy(launch)
    existing = current_delivery(run_dir, str(message["message_id"]))
    if existing is not None:
        # The runner may observe the authoritative message between its append
        # and this host-side delivery bookkeeping call. Never append a stale
        # queued record after delivered or terminal evidence.
        return existing
    queued = append_delivery_event(
        run_dir,
        agent_run_id=str(launch["agent_run"]["id"]),
        correlation_id=str(message["message_id"]),
        message_sha256=message_digest(message),
        adapter=str(policy["adapter"]),
        outcome="queued",
        attempt=0,
        reason="durable steer request queued for adapter delivery",
        executor=policy["executable"],
    )
    if policy["adapter"] == "unsupported":
        return append_delivery_event(
            run_dir,
            agent_run_id=str(launch["agent_run"]["id"]),
            correlation_id=str(message["message_id"]),
            message_sha256=message_digest(message),
            adapter="unsupported",
            outcome="unsupported",
            attempt=0,
            reason="executor has no configured evidence-capable late-steering adapter",
            executor=policy["executable"],
        )
    return queued


def _expired(message: dict[str, Any], deadline_seconds: int) -> bool:
    deadline = _parse_timestamp(message["timestamp"]) + timedelta(seconds=deadline_seconds)
    return datetime.now(timezone.utc) >= deadline


def deliver_pending(run_dir: Path, *, active: bool) -> list[dict[str, Any]]:
    """Deliver any undelivered steering requests through the bound adapter."""
    launch = read_agent_run_contract(run_dir / "agent-run-contract.json")
    agent_run_id = str(launch["agent_run"]["id"])
    policy = _policy(launch)
    handoff = Path(str(launch["paths"]["handoff_dir"]))
    inbox = handoff / "steering-inbox"
    results: list[dict[str, Any]] = []
    messages = replay_messages(run_dir)
    events = replay_delivery_events(run_dir)
    by_id: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_id.setdefault(str(event["correlation_id"]), []).append(event)
    for message in messages:
        if message.get("kind") != "steer":
            continue
        correlation_id = str(message["message_id"])
        current = by_id.get(correlation_id, [])
        if any(item["outcome"] in DELIVERY_STOP_OUTCOMES for item in current):
            continue
        if any(item["outcome"] == "delivered" for item in current):
            continue
        if policy["adapter"] == "unsupported":
            results.append(queue_request(run_dir, message))
            continue
        if _expired(message, int(policy["deadline_seconds"])):
            results.append(append_delivery_event(
                run_dir,
                agent_run_id=agent_run_id,
                correlation_id=correlation_id,
                message_sha256=message_digest(message),
                adapter=str(policy["adapter"]),
                outcome="expired",
                attempt=0,
                reason="steering delivery deadline elapsed before delivery",
                executor=policy["executable"],
            ))
            continue
        if not active:
            results.append(append_delivery_event(
                run_dir,
                agent_run_id=agent_run_id,
                correlation_id=correlation_id,
                message_sha256=message_digest(message),
                adapter=str(policy["adapter"]),
                outcome="failed",
                attempt=0,
                reason="executor exited before steering could be delivered",
                executor=policy["executable"],
            ))
            continue
        if policy["adapter"] != "control-file-v1":
            continue
        try:
            if inbox.is_symlink():
                raise WorkflowError("steering inbox must not be a symlink")
            inbox.mkdir(parents=True, exist_ok=True, mode=0o700)
            target = inbox / f"steer-{correlation_id}.json"
            payload = {
                "schema": STEERING_REQUEST_SCHEMA,
                "agent_run_id": agent_run_id,
                "message_id": correlation_id,
                "message_sha256": message_digest(message),
                "actor": message["actor"],
                "content": message["content"],
                "queued_at": message["timestamp"],
                "deadline_seconds": policy["deadline_seconds"],
            }
            if target.exists() or target.is_symlink():
                if target.is_symlink() or json.loads(target.read_text(encoding="utf-8")) != payload:
                    raise WorkflowError("existing steering request does not match immutable payload")
            else:
                atomic_write_json(target, payload, mode=0o444)
            results.append(append_delivery_event(
                run_dir,
                agent_run_id=agent_run_id,
                correlation_id=correlation_id,
                message_sha256=message_digest(message),
                adapter="control-file-v1",
                outcome="delivered",
                attempt=1,
                reason="immutable steering request published to cooperative executor inbox",
                executor=policy["executable"],
            ))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
            results.append(append_delivery_event(
                run_dir,
                agent_run_id=agent_run_id,
                correlation_id=correlation_id,
                message_sha256=message_digest(message),
                adapter="control-file-v1",
                outcome="failed",
                attempt=1,
                reason=str(exc),
                executor=policy["executable"],
            ))
    return results


def record_acknowledgement(
    run_dir: Path,
    *,
    correlation_id: str,
    outcome: str,
    reason: str,
) -> dict[str, Any]:
    if outcome not in {"applied", "rejected"}:
        raise WorkflowError("acknowledgement outcome must be applied or rejected")
    launch = read_agent_run_contract(run_dir / "agent-run-contract.json")
    policy = _policy(launch)
    steer = next(
        (item for item in replay_messages(run_dir) if item.get("message_id") == correlation_id),
        None,
    )
    if steer is None or steer.get("kind") != "steer":
        raise WorkflowError("acknowledgement must reference a durable steer request")
    return append_delivery_event(
        run_dir,
        agent_run_id=str(launch["agent_run"]["id"]),
        correlation_id=correlation_id,
        message_sha256=message_digest(steer),
        adapter=str(policy["adapter"]),
        outcome=outcome,
        attempt=1,
        reason=reason,
        executor=policy["executable"],
    )
