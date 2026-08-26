from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .errors import WorkflowError
from .journal import JournalTransactionResult, read_jsonl, transact_jsonl
from .util import utc_now

LIFECYCLE_SCHEMA = "agent-workflow/lifecycle-event/v1"


def _validate_lifecycle_event(value: object, expected_sequence: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError("lifecycle event must be a JSON object")
    required = {
        "schema",
        "sequence",
        "timestamp",
        "dimension",
        "prior",
        "new",
        "actor",
        "reason",
        "receipt_refs",
    }
    if set(value) != required or value.get("schema") != LIFECYCLE_SCHEMA:
        raise WorkflowError("invalid lifecycle event")
    if value.get("sequence") != expected_sequence:
        raise WorkflowError(
            f"lifecycle event sequence mismatch: expected {expected_sequence}"
        )
    refs = value.get("receipt_refs")
    if not isinstance(refs, list) or not all(isinstance(item, str) for item in refs):
        raise WorkflowError("invalid lifecycle event receipt references")
    return value


def append_lifecycle_event(
    run_dir: Path,
    *,
    dimension: str,
    prior: Any,
    new: Any,
    actor: str,
    reason: str,
    receipt_refs: Sequence[str] = (),
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "events.jsonl"

    def decide(existing: list[dict[str, Any]]) -> JournalTransactionResult[dict[str, Any]]:
        sequence = len(existing) + 1
        event = {
            "schema": LIFECYCLE_SCHEMA,
            "sequence": sequence,
            "timestamp": utc_now(),
            "dimension": dimension,
            "prior": prior,
            "new": new,
            "actor": actor,
            "reason": reason,
            "receipt_refs": list(receipt_refs),
        }
        event = _validate_lifecycle_event(event, sequence)
        return JournalTransactionResult(value=event, record=event)

    return transact_jsonl(path, validator=_validate_lifecycle_event, transaction=decide, sequence_field="sequence")


def reconstruct_lifecycle(path: Path) -> dict[str, Any]:
    state: dict[str, Any] = {}
    events = read_jsonl(path, validator=_validate_lifecycle_event, sequence_field="sequence")
    for event in events:
        state[str(event.get("dimension"))] = event.get("new")
    return {"event_count": len(events), "state": state}
