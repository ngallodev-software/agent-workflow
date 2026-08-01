from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from ..contracts import validate_instance
from ..util import utc_now
from .contracts import BENCHMARK_PHASE_EVENT_SCHEMA

_EVENT_LOCK = threading.Lock()


def append_event(
    run_dir: Path,
    *,
    event_type: str,
    run_id: str,
    pair_id: str | None = None,
    arm: str | None = None,
    phase_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = run_dir / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with _EVENT_LOCK:
        event = {
            "schema": BENCHMARK_PHASE_EVENT_SCHEMA,
            "sequence": _next_sequence(path),
            "recorded_at": utc_now(),
            "event_type": event_type,
            "run_id": run_id,
            "pair_id": pair_id,
            "arm": arm,
            "phase_id": phase_id,
            "payload": payload or {},
        }
        validate_instance(event, BENCHMARK_PHASE_EVENT_SCHEMA, artifact="benchmark event")
        with path.open("ab") as stream:
            stream.write((json.dumps(event, sort_keys=True) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
    return event


def _next_sequence(path: Path) -> int:
    if not path.is_file():
        return 1
    with path.open("rb") as stream:
        return sum(1 for line in stream if line.strip()) + 1


def read_events(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "events.jsonl"
    if not path.is_file():
        return []
    result: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                result.append(value)
    return result
