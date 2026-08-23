from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.hierarchy import (
    append_journal_record,
    read_journal,
    replay_authority_state,
)
from tests.invariants.test_hierarchy_contracts import valid_contracts


def test_duplicate_local_message_id_fails(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    append_journal_record(
        path,
        journal_id="hierarchy-events",
        record_type="lifecycle",
        actor="orchestrator-001",
        team_id="implementation",
        message_id="event-1",
        payload={"state": "ready"},
    )

    with pytest.raises(WorkflowError, match="duplicate hierarchy journal message_id"):
        append_journal_record(
            path,
            journal_id="hierarchy-events",
            record_type="lifecycle",
            actor="orchestrator-001",
            team_id="implementation",
            message_id="event-1",
            payload={"state": "running"},
        )


def test_truncation_sequence_identity_and_duplicate_import_tamper_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    append_journal_record(
        path,
        journal_id="hierarchy-events",
        record_type="lifecycle",
        actor="orchestrator-001",
        team_id="implementation",
        message_id="event-1",
        payload={"state": "ready"},
    )
    original = path.read_bytes()

    path.write_bytes(original[:-1])
    with pytest.raises(WorkflowError, match="truncated"):
        read_journal(path, expected_journal_id="hierarchy-events")

    record = json.loads(original)
    record["sequence"] = 2
    path.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(WorkflowError, match="sequence mismatch"):
        read_journal(path, expected_journal_id="hierarchy-events")

    record["sequence"] = 1
    record["journal_id"] = "other-journal"
    path.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(WorkflowError, match="identity mismatch"):
        read_journal(path, expected_journal_id="hierarchy-events")

    source = {"journal_id": "source-journal", "message_id": "source-message"}
    record["journal_id"] = "hierarchy-events"
    record["source"] = source
    duplicate = dict(record)
    duplicate["sequence"] = 2
    duplicate["message_id"] = "event-2"
    path.write_text(
        "\n".join(
            json.dumps(item, sort_keys=True, separators=(",", ":"))
            for item in (record, duplicate)
        )
        + "\n"
    )
    with pytest.raises(WorkflowError, match="duplicate imported hierarchy message"):
        read_journal(path, expected_journal_id="hierarchy-events")


def test_symlink_and_hardlink_journals_fail_closed(tmp_path: Path) -> None:
    target = tmp_path / "target.jsonl"
    target.write_text("")
    link = tmp_path / "link.jsonl"
    link.symlink_to(target)
    with pytest.raises(WorkflowError, match="without following links"):
        append_journal_record(
            link,
            journal_id="linked-journal",
            record_type="diagnostic",
            actor="orchestrator-001",
            message_id="message-1",
            payload={"status": "bad"},
        )

    hard = tmp_path / "hard.jsonl"
    os.link(target, hard)
    with pytest.raises(WorkflowError, match="must not be hard linked"):
        append_journal_record(
            hard,
            journal_id="hard-journal",
            record_type="diagnostic",
            actor="orchestrator-001",
            message_id="message-2",
            payload={"status": "bad"},
        )


def test_replay_rejects_mixed_undeclared_team_identity(tmp_path: Path) -> None:
    hierarchy, teams = valid_contracts()
    path = tmp_path / "events.jsonl"
    append_journal_record(
        path,
        journal_id="root-events",
        record_type="lifecycle",
        actor="orchestrator-001",
        team_id="other-team",
        message_id="event-1",
        payload={"state": "ready"},
    )

    with pytest.raises(WorkflowError, match="undeclared team"):
        replay_authority_state(hierarchy, teams, {"root-events": path})


def test_read_without_expected_id_still_rejects_mixed_journal_identity(tmp_path: Path) -> None:
    path = tmp_path / "mixed.jsonl"
    first = {
        "schema": "agent-workflow/hierarchy-journal-record/v1",
        "journal_id": "journal-one",
        "sequence": 1,
        "message_id": "message-one",
        "timestamp": "2026-08-01T00:00:00+00:00",
        "record_type": "diagnostic",
        "actor": "root:orchestrator",
        "team_id": None,
        "correlation_id": None,
        "causation_id": None,
        "source": None,
        "payload": {"status": "one"},
    }
    second = {**first, "journal_id": "journal-two", "sequence": 2, "message_id": "message-two"}
    path.write_text(
        "\n".join(json.dumps(item, sort_keys=True, separators=(",", ":")) for item in (first, second))
        + "\n"
    )
    with pytest.raises(WorkflowError, match="identity mismatch"):
        read_journal(path)
