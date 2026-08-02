from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.hierarchy import (
    EvidenceReference,
    JournalReference,
    append_journal_record,
    create_root_receipt,
    create_team_receipt,
    install_contract_set,
    verify_root_receipt,
    verify_team_receipt,
)
from tests.invariants.test_hierarchy_contracts import valid_contracts


def _write_readonly(root: Path, relative: str, value: object) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o400)
    return path


def _append_team_journal(root: Path, team_id: str, *, suffix: str = "1") -> Path:
    path = root / f"teams/{team_id}/events.jsonl"
    append_journal_record(
        path,
        journal_id=f"{team_id}-events",
        record_type="lifecycle",
        actor=f"lead-{team_id}",
        team_id=team_id,
        message_id=f"{team_id}-event-{suffix}",
        payload={"state": "completed"},
    )
    return path


def _create_team(
    root: Path,
    evidence: Path,
    hierarchy: dict,
    contract: dict,
) -> dict:
    team_id = contract["team_id"]
    _append_team_journal(root, team_id)
    _write_readonly(
        evidence,
        f"workers/{team_id}-worker/task-result.json",
        {"schema": "agent-workflow/task-result/v1", "team_id": team_id},
    )
    _write_readonly(
        evidence,
        f"reviews/{team_id}-independent.json",
        {"review": "independent", "team_id": team_id, "outcome": "accepted"},
    )
    return create_team_receipt(
        root,
        evidence,
        hierarchy,
        contract,
        journals=(
            JournalReference(
                label="events",
                journal_id=f"{team_id}-events",
                path=f"teams/{team_id}/events.jsonl",
            ),
        ),
        workers={
            f"{team_id}-worker": (
                EvidenceReference(
                    kind="agent-workflow/task-result/v1",
                    path=f"workers/{team_id}-worker/task-result.json",
                ),
            )
        },
        review_evidence=(
            EvidenceReference(
                kind="independent",
                path=f"reviews/{team_id}-independent.json",
            ),
        ),
        budget_usage={
            "workers_started": 1,
            "peak_concurrent_workers": 1,
            "peak_interactive_panes": 2,
            "retries": 0,
            "wall_seconds": 30,
        },
        terminal_disposition="completed",
        created_at="2026-08-02T00:00:00+00:00",
    )


def _prepared_authority(tmp_path: Path) -> tuple[Path, Path, dict, tuple[dict, dict]]:
    hierarchy, teams = valid_contracts()
    root = tmp_path / "orchestration"
    evidence = tmp_path / "evidence"
    evidence.mkdir(parents=True)
    install_contract_set(root, hierarchy, teams)
    for contract in teams:
        _create_team(root, evidence, hierarchy, contract)
    append_journal_record(
        root / "root-events.jsonl",
        journal_id="root-events",
        record_type="lifecycle",
        actor="orchestrator-001",
        message_id="root-event-1",
        payload={"state": "completed"},
    )
    _write_readonly(
        evidence,
        "bindings/cross-team-summary.json",
        {"implementation": "accepted", "review": "accepted"},
    )
    _write_readonly(
        evidence,
        "approvals/root-final.json",
        {"approval": "root-final", "outcome": "accepted"},
    )
    return root, evidence, hierarchy, teams


def _create_root(root: Path, evidence: Path) -> dict:
    return create_root_receipt(
        root,
        evidence,
        root_journals=(
            JournalReference(
                label="events",
                journal_id="root-events",
                path="root-events.jsonl",
            ),
        ),
        cross_team_bindings=(
            EvidenceReference(
                kind="cross-team-summary",
                path="bindings/cross-team-summary.json",
            ),
        ),
        approval_evidence=(
            EvidenceReference(kind="root-final", path="approvals/root-final.json"),
        ),
        outcome="completed",
        created_at="2026-08-02T00:01:00+00:00",
    )


def test_team_and_root_receipts_bind_complete_authority_evidence(tmp_path: Path) -> None:
    root, evidence, hierarchy, teams = _prepared_authority(tmp_path)
    root_receipt = _create_root(root, evidence)

    assert verify_root_receipt(root, evidence) == root_receipt
    for contract in teams:
        receipt = verify_team_receipt(root, evidence, hierarchy, contract)
        assert receipt["team_id"] == contract["team_id"]
        assert receipt["budget_usage"]["workers_started"] == 1
        assert receipt["workers"][0]["artifacts"][0]["kind"] in contract["required_outputs"]
    for path in (
        root / "root-receipt.json",
        root / "teams/implementation/team-receipt.json",
        root / "teams/review/team-receipt.json",
    ):
        assert stat.S_IMODE(path.stat().st_mode) == 0o400


def test_later_team_or_root_journal_append_invalidates_receipts(tmp_path: Path) -> None:
    root, evidence, hierarchy, teams = _prepared_authority(tmp_path)
    _create_root(root, evidence)

    _append_team_journal(root, "implementation", suffix="2")
    with pytest.raises(WorkflowError, match="changed after receipt sealing"):
        verify_team_receipt(root, evidence, hierarchy, teams[0])
    with pytest.raises(WorkflowError, match="changed after receipt sealing"):
        verify_root_receipt(root, evidence)

    fresh_root, fresh_evidence, _, _ = _prepared_authority(tmp_path / "fresh")
    _create_root(fresh_root, fresh_evidence)
    append_journal_record(
        fresh_root / "root-events.jsonl",
        journal_id="root-events",
        record_type="diagnostic",
        actor="orchestrator-001",
        message_id="root-event-2",
        payload={"state": "late"},
    )
    with pytest.raises(WorkflowError, match="changed after receipt sealing"):
        verify_root_receipt(fresh_root, fresh_evidence)


def test_artifact_and_receipt_tamper_invalidate_verification(tmp_path: Path) -> None:
    root, evidence, hierarchy, teams = _prepared_authority(tmp_path)
    _create_root(root, evidence)

    artifact = evidence / "workers/implementation-worker/task-result.json"
    artifact.chmod(0o600)
    artifact.write_text('{"tampered": true}\n', encoding="utf-8")
    artifact.chmod(0o400)
    with pytest.raises(WorkflowError, match="digest or size mismatch"):
        verify_team_receipt(root, evidence, hierarchy, teams[0])

    fresh_root, fresh_evidence, _, _ = _prepared_authority(tmp_path / "fresh")
    _create_root(fresh_root, fresh_evidence)
    receipt_path = fresh_root / "root-receipt.json"
    value = json.loads(receipt_path.read_text(encoding="utf-8"))
    value["outcome"] = "failed"
    receipt_path.chmod(0o600)
    receipt_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt_path.chmod(0o400)
    with pytest.raises(WorkflowError, match="digest mismatch"):
        verify_root_receipt(fresh_root, fresh_evidence)


def test_required_outputs_reviews_approvals_and_budgets_fail_closed(tmp_path: Path) -> None:
    hierarchy, teams = valid_contracts()
    root = tmp_path / "orchestration"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    install_contract_set(root, hierarchy, teams)
    _append_team_journal(root, "implementation")
    _write_readonly(evidence, "workers/worker-1/other.json", {"wrong": True})
    _write_readonly(evidence, "reviews/independent.json", {"accepted": True})

    base = {
        "journals": (
            JournalReference(
                label="events",
                journal_id="implementation-events",
                path="teams/implementation/events.jsonl",
            ),
        ),
        "workers": {
            "worker-1": (EvidenceReference(kind="other", path="workers/worker-1/other.json"),)
        },
        "review_evidence": (
            EvidenceReference(kind="independent", path="reviews/independent.json"),
        ),
        "budget_usage": {
            "workers_started": 1,
            "peak_concurrent_workers": 1,
            "peak_interactive_panes": 1,
            "retries": 0,
            "wall_seconds": 1,
        },
        "terminal_disposition": "completed",
    }
    with pytest.raises(WorkflowError, match="missing required outputs"):
        create_team_receipt(root, evidence, hierarchy, teams[0], **base)

    _write_readonly(
        evidence,
        "workers/worker-1/task-result.json",
        {"schema": "agent-workflow/task-result/v1"},
    )
    base["workers"] = {
        "worker-1": (
            EvidenceReference(
                kind="agent-workflow/task-result/v1",
                path="workers/worker-1/task-result.json",
            ),
        )
    }
    base["review_evidence"] = ()
    with pytest.raises(WorkflowError, match="missing required kinds"):
        create_team_receipt(root, evidence, hierarchy, teams[0], **base)

    base["review_evidence"] = (
        EvidenceReference(kind="independent", path="reviews/independent.json"),
    )
    base["budget_usage"] = {**base["budget_usage"], "workers_started": 2}
    with pytest.raises(WorkflowError, match="workers_started must equal"):
        create_team_receipt(root, evidence, hierarchy, teams[0], **base)

    prepared_root, prepared_evidence, _, _ = _prepared_authority(tmp_path / "prepared")
    with pytest.raises(WorkflowError, match="missing required kinds"):
        create_root_receipt(
            prepared_root,
            prepared_evidence,
            root_journals=(
                JournalReference(label="events", journal_id="root-events", path="root-events.jsonl"),
            ),
            outcome="completed",
        )


def test_symlink_hardlink_and_writable_evidence_fail_closed(tmp_path: Path) -> None:
    hierarchy, teams = valid_contracts()
    root = tmp_path / "orchestration"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    install_contract_set(root, hierarchy, teams)
    _append_team_journal(root, "implementation")
    target = _write_readonly(
        evidence,
        "target.json",
        {"schema": "agent-workflow/task-result/v1"},
    )
    symlink = evidence / "linked.json"
    symlink.symlink_to(target)
    hardlink = evidence / "hard.json"
    os.link(target, hardlink)
    review = _write_readonly(evidence, "review.json", {"accepted": True})

    def attempt(path: str) -> None:
        create_team_receipt(
            root,
            evidence,
            hierarchy,
            teams[0],
            journals=(
                JournalReference(
                    label="events",
                    journal_id="implementation-events",
                    path="teams/implementation/events.jsonl",
                ),
            ),
            workers={
                "worker-1": (
                    EvidenceReference(kind="agent-workflow/task-result/v1", path=path),
                )
            },
            review_evidence=(EvidenceReference(kind="independent", path="review.json"),),
            budget_usage={
                "workers_started": 1,
                "peak_concurrent_workers": 1,
                "peak_interactive_panes": 1,
                "retries": 0,
                "wall_seconds": 1,
            },
            terminal_disposition="completed",
        )

    with pytest.raises(WorkflowError, match="without following links"):
        attempt("linked.json")
    with pytest.raises(WorkflowError, match="hard-linked"):
        attempt("hard.json")

    hardlink.unlink()
    target.chmod(0o600)
    with pytest.raises(WorkflowError, match="must be read-only"):
        attempt("target.json")
    assert stat.S_IMODE(review.stat().st_mode) == 0o400
