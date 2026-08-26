from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.journal import (
    JournalTransactionResult,
    read_jsonl,
    transact_jsonl,
)


def _record(value: object, _line_number: int) -> dict[str, object]:
    if not isinstance(value, dict):
        raise WorkflowError("journal test record must be an object")
    return value


def _append_worker(path_text: str, worker: int, count: int) -> None:
    path = Path(path_text)
    for item in range(count):
        def decide(existing: list[dict[str, object]]) -> JournalTransactionResult[dict[str, object]]:
            value: dict[str, object] = {
                "sequence": len(existing) + 1,
                "worker": worker,
                "item": item,
            }
            return JournalTransactionResult(value=value, record=value)

        transact_jsonl(
            path,
            validator=_record,
            transaction=decide,
            sequence_field="sequence",
        )


def test_concurrent_append_allocates_one_monotonic_sequence(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    context = multiprocessing.get_context("spawn")
    processes = [
        context.Process(target=_append_worker, args=(str(path), worker, 8))
        for worker in range(4)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    rows = read_jsonl(path, validator=_record, sequence_field="sequence")
    assert [row["sequence"] for row in rows] == list(range(1, 33))
    assert len({(row["worker"], row["item"]) for row in rows}) == 32


def test_truncated_final_record_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"sequence":1}')
    with pytest.raises(WorkflowError, match="truncated"):
        read_jsonl(path, validator=_record, sequence_field="sequence")


def test_malformed_record_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"sequence":1}\nnot-json\n')
    with pytest.raises(WorkflowError, match="invalid journal JSON"):
        read_jsonl(path, validator=_record, sequence_field="sequence")


def test_sequence_violation_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps({"sequence": 2}) + "\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="sequence mismatch"):
        read_jsonl(path, validator=_record, sequence_field="sequence")


def test_empty_record_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"sequence":1}\n\n')
    with pytest.raises(WorkflowError, match="empty record"):
        read_jsonl(path, validator=_record, sequence_field="sequence")
