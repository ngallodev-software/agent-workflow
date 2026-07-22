from __future__ import annotations

import json
import os
import fcntl
from pathlib import Path
from typing import Any, Sequence

from .errors import WorkflowError
from .util import utc_now


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
    with path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.seek(0)
        sequence = 1 + sum(1 for line in stream if line.strip())
        event = {
            "schema": "agent-workflow/lifecycle-event/v1",
            "sequence": sequence,
            "timestamp": utc_now(),
            "dimension": dimension,
            "prior": prior,
            "new": new,
            "actor": actor,
            "reason": reason,
            "receipt_refs": list(receipt_refs),
        }
        stream.seek(0, os.SEEK_END)
        stream.write(
            json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
            + b"\n"
        )
        stream.flush()
        os.fsync(stream.fileno())
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    return event


def reconstruct_lifecycle(path: Path) -> dict[str, Any]:
    state: dict[str, Any] = {}
    expected = 1
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise WorkflowError(f"cannot read lifecycle events {path}: {exc}") from exc
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"invalid lifecycle event JSON: {exc}") from exc
        if not isinstance(event, dict) or event.get("sequence") != expected:
            raise WorkflowError(
                f"lifecycle event sequence mismatch: expected {expected}"
            )
        state[str(event.get("dimension"))] = event.get("new")
        expected += 1
    return {"event_count": expected - 1, "state": state}
