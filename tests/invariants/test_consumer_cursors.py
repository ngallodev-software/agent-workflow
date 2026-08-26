from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent_workflow.consumer_cursors import (
    CursorIntegrityError,
    CursorStore,
    ConsumerBinding,
    DurableEffectReceipt,
    build_disposition_evidence,
    reconstruct_cursor,
    validate_source_records,
)
from agent_workflow.errors import WorkflowError
from agent_workflow.messages import append_message, message_digest


def _binding(name: str, *, journal: str = "a" * 64) -> ConsumerBinding:
    return ConsumerBinding(
        consumer_id=name,
        principal="child",
        source_journal_id=f"sha256:{journal}",
    )


def _records(tmp_path: Path) -> list[dict]:
    return [
        append_message(
            tmp_path,
            agent_run_id="source-run",
            direction="child_to_parent",
            kind="progress",
            actor="child",
            content="one",
        ),
        append_message(
            tmp_path,
            agent_run_id="source-run",
            direction="child_to_parent",
            kind="progress",
            actor="child",
            content="two",
        ),
    ]


def _effect_store(tmp_path: Path):
    effects: dict[str, dict] = {}
    path = tmp_path / "target.jsonl"

    def commit(record: dict, source_id: str, digest: str) -> dict:
        prior = effects.get(source_id)
        if prior is not None:
            if prior["source_message_digest"] != digest:
                raise CursorIntegrityError("target ID conflict")
            return prior
        receipt = {
            "committed": True,
            "receipt_id": f"target-{len(effects) + 1}",
            "source_message_id": source_id,
            "source_message_digest": digest,
        }
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        effects[source_id] = receipt
        return receipt

    return effects, commit


def test_cursor_advances_after_target_commit_and_retries_crash_windows(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    records = _records(source)
    store = CursorStore(tmp_path / "state", _binding("consumer-a"))
    effects, commit = _effect_store(tmp_path)

    with pytest.raises(RuntimeError, match="before target"):
        store.process(
            records[0],
            disposition="applied",
            commit_effect=lambda *_: (_ for _ in ()).throw(RuntimeError("before target")),
        )
    assert store.read() is None

    with pytest.raises(RuntimeError, match="after target"):
        store.process(
            records[0],
            disposition="applied",
            commit_effect=commit,
            after_target_commit=lambda _: (_ for _ in ()).throw(RuntimeError("after target")),
        )
    assert store.read() is None
    assert len(effects) == 1

    result = store.process(records[0], disposition="applied", commit_effect=commit)
    assert result["status"] == "advanced"
    assert store.process(records[0], disposition="applied", commit_effect=commit)["status"] == "duplicate"
    assert len(effects) == 1

    second = store.process(records[1], disposition="ignored", commit_effect=commit)
    assert second["cursor"]["last_committed_source_sequence"] == 2


def test_corrupt_cursor_reconstructs_contiguous_prefix_and_preserves_replay(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    records = _records(source)
    binding = _binding("consumer-rebuild")
    store = CursorStore(tmp_path / "state", binding)
    effects, commit = _effect_store(tmp_path)
    first = store.process(records[0], disposition="applied", commit_effect=commit)
    receipt = DurableEffectReceipt.from_value(
        effects[records[0]["message_id"]],
        source_message_id=records[0]["message_id"],
        source_message_digest=message_digest(records[0]),
    )
    evidence = [
        build_disposition_evidence(
            binding=binding,
            source_record=records[0],
            disposition="applied",
            target_receipt=receipt,
        )
    ]
    store.path.write_text("{truncated", encoding="utf-8")
    rebuilt = store.read_or_reconstruct(records, evidence)
    assert rebuilt["last_committed_source_sequence"] == 1
    assert rebuilt["last_committed_source_message_id"] == records[0]["message_id"]
    assert store.process(records[1], disposition="applied", commit_effect=commit)["status"] == "advanced"


def test_deleted_cursor_reconstructs_from_target_evidence_without_duplicate_effect(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    records = _records(source)
    binding = _binding("consumer-deleted")
    store = CursorStore(tmp_path / "state", binding)
    effects, commit = _effect_store(tmp_path)
    store.process(records[0], disposition="applied", commit_effect=commit)
    first_receipt = DurableEffectReceipt.from_value(
        effects[records[0]["message_id"]],
        source_message_id=records[0]["message_id"],
        source_message_digest=message_digest(records[0]),
    )
    evidence = [
        build_disposition_evidence(
            binding=binding,
            source_record=records[0],
            disposition="applied",
            target_receipt=first_receipt,
        )
    ]

    store.path.unlink()
    rebuilt = store.read_or_reconstruct(records, evidence)
    assert rebuilt["last_committed_source_sequence"] == 1
    assert store.process(records[0], disposition="applied", commit_effect=commit)["status"] == "duplicate"
    assert len(effects) == 1
    assert store.process(records[1], disposition="applied", commit_effect=commit)["status"] == "advanced"
    assert len(effects) == 2


def test_consumers_are_independent_and_source_id_conflicts_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    records = _records(source)
    first = CursorStore(tmp_path / "state", _binding("consumer-one"))
    second = CursorStore(tmp_path / "state", _binding("consumer-two"))
    one_dir = tmp_path / "one"
    two_dir = tmp_path / "two"
    one_dir.mkdir()
    two_dir.mkdir()
    _, commit_one = _effect_store(one_dir)
    _, commit_two = _effect_store(two_dir)
    first.process(records[0], disposition="applied", commit_effect=commit_one)
    assert second.read() is None
    first.process(records[1], disposition="applied", commit_effect=commit_one)
    second.process(records[0], disposition="deferred", commit_effect=commit_two)
    assert first.read()["last_committed_source_sequence"] == 2
    assert second.read()["last_committed_source_sequence"] == 1

    conflicting = dict(records[0], sequence=3, content="different")
    with pytest.raises(CursorIntegrityError):
        validate_source_records([records[0], records[1], conflicting])


def test_integrity_and_cursor_errors_redact_source_message_content(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    records = _records(source)
    secret = "sensitive-message-content-must-not-appear"
    conflicting = dict(records[0], sequence=3, content=secret)

    with pytest.raises(CursorIntegrityError) as source_error:
        validate_source_records([records[0], records[1], conflicting])
    assert secret not in str(source_error.value)

    store = CursorStore(tmp_path / "state", _binding("redacted"))
    target_root = tmp_path / "target"
    target_root.mkdir()
    effects, commit = _effect_store(target_root)
    store.process(records[0], disposition="applied", commit_effect=commit)
    tampered = dict(records[0], content=secret)
    with pytest.raises(CursorIntegrityError) as cursor_error:
        store.process(tampered, disposition="applied", commit_effect=commit)
    assert secret not in str(cursor_error.value)


def test_security_boundaries_reject_symlink_cursor_and_untrusted_orchestrator(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    records = _records(source)
    binding = _binding("secure")
    store = CursorStore(tmp_path / "state", binding)
    outside = tmp_path / "outside.json"
    outside.write_text("outside", encoding="utf-8")
    store.path.symlink_to(outside)
    with pytest.raises(CursorIntegrityError):
        store.read()
    with pytest.raises(CursorIntegrityError):
        ConsumerBinding(
            consumer_id="orchestrator",
            principal="orchestrator",
            source_journal_id="sha256:" + "b" * 64,
        )


def test_compare_and_update_requires_committed_receipt(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    record = _records(source)[0]
    store = CursorStore(tmp_path / "state", _binding("compare"))
    receipt = DurableEffectReceipt(
        receipt_id="receipt-1",
        source_message_id=record["message_id"],
        source_message_digest=message_digest(record),
    )
    assert store.compare_and_update(
        expected_sequence=0,
        source_record=record,
        disposition="rejected",
        target_receipt=receipt,
    )["disposition"] == "rejected"
    with pytest.raises(WorkflowError):
        store.compare_and_update(
            expected_sequence=1,
            source_record=dict(record, sequence=2),
            disposition="unknown",
            target_receipt=receipt,
        )
