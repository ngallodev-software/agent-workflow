from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.conftest import InstalledProduct


def test_installed_hierarchy_lifecycle_installs_replays_and_seals_authority(
    installed_product: InstalledProduct,
    tmp_path: Path,
) -> None:
    root = tmp_path / "orchestration"
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    script = r'''
import json
import sys
from pathlib import Path
from agent_workflow.hierarchy import (
    EvidenceReference,
    JournalReference,
    append_journal_record,
    create_root_receipt,
    create_team_receipt,
    install_contract_set,
    read_contract_set,
    read_journal,
    replay_authority_state,
    seal_hierarchy_contract,
    seal_team_delegation_contract,
    validate_hierarchy_contract,
    validate_team_delegation_contract,
    verify_root_receipt,
)

root = Path(sys.argv[1])
evidence = Path(sys.argv[2])
digest = "sha256:" + "a" * 64
hierarchy = seal_hierarchy_contract({
    "schema": "agent-workflow/orchestration-hierarchy/v1",
    "version": 1,
    "orchestration_id": "root-001",
    "root_orchestrator_id": "orchestrator-001",
    "workflow_id": "workflow-001",
    "allowed_depth": 2,
    "tmux_session_name": "aw-root-001",
    "budgets": {
        "max_teams": 2,
        "max_total_workers": 8,
        "max_concurrent_workers": 4,
        "max_interactive_panes": 10,
        "max_retries_per_worker": 2,
        "max_wall_seconds": 7200,
    },
    "terminal_policy": {"allowed_modes": ["current"], "external_argv_prefixes": []},
    "allowed": {
        "executors": ["codex", "claude"],
        "models": ["gpt-5.6", "claude-opus"],
        "agent_classes": ["implementation", "review"],
        "permissions": ["workspace-write", "read-only"],
        "commands": ["run", "status", "message"],
    },
    "allowed_routes": ["root-to-team", "team-to-root", "team-to-worker", "worker-to-team"],
    "teams": [
        {"team_id": "implementation", "team_lead_session_id": "lead-implementation", "parent_principal": "root"},
        {"team_id": "review", "team_lead_session_id": "lead-review", "parent_principal": "root"},
    ],
    "source": {
        "repository": "file:///workspace/project",
        "revision": "abc123",
        "snapshot_sha256": digest,
        "prompt_pack_id": "hierarchical-multi-team-orchestration",
        "prompt_pack_sha256": digest,
    },
    "created_at": "2026-08-01T20:00:00+00:00",
})

def team(team_id, lead_id):
    return seal_team_delegation_contract({
        "schema": "agent-workflow/team-delegation/v1",
        "version": 1,
        "orchestration_id": "root-001",
        "root_orchestrator_id": "orchestrator-001",
        "team_id": team_id,
        "team_lead_session_id": lead_id,
        "objective": f"Complete bounded work for {team_id}",
        "deliverables": [f"reports/{team_id}.json"],
        "writable_scope": [f"work/{team_id}"],
        "no_go_scope": ["secrets"],
        "stop_conditions": ["authority mismatch", "budget exhausted"],
        "dependencies": [],
        "required_outputs": ["agent-workflow/task-result/v1"],
        "budgets": {
            "max_workers": 3,
            "max_concurrent_workers": 2,
            "max_interactive_panes": 4,
            "max_retries": 1,
            "max_wall_seconds": 3600,
        },
        "allowed": {
            "executors": ["codex"],
            "models": ["gpt-5.6"],
            "agent_classes": ["implementation"],
            "permissions": ["workspace-write"],
            "commands": ["run", "status"],
        },
        "message_routes": ["team-to-root", "team-to-worker", "worker-to-team"],
        "required_reviews": ["independent"],
        "required_approvals": ["root-final"],
        "parent_action_cursor": 0,
    }, hierarchy)

teams = (
    team("implementation", "lead-implementation"),
    team("review", "lead-review"),
)
validate_hierarchy_contract(hierarchy)
for item in teams:
    validate_team_delegation_contract(item, hierarchy)
manifest = install_contract_set(root, hierarchy, teams)
second_manifest = install_contract_set(root, hierarchy, teams)
loaded_hierarchy, loaded_teams, loaded_manifest = read_contract_set(root)

replay_root = root / "replay"
replay_root.mkdir()
events = replay_root / "events.jsonl"
inbox = replay_root / "inbox.jsonl"
append_journal_record(
    events,
    journal_id="root-events",
    record_type="lifecycle",
    actor="orchestrator-001",
    team_id="implementation",
    message_id="event-1",
    payload={"state": "ready"},
)
first_import = append_journal_record(
    inbox,
    journal_id="root-inbox",
    record_type="import",
    actor="orchestrator-001",
    team_id="implementation",
    message_id="import-1",
    source_journal_id="team-outbox",
    source_message_id="team-message-1",
    payload={"summary": "ready"},
)
second_import = append_journal_record(
    inbox,
    journal_id="root-inbox",
    record_type="import",
    actor="orchestrator-001",
    team_id="implementation",
    message_id="import-2",
    source_journal_id="team-outbox",
    source_message_id="team-message-1",
    payload={"summary": "ready"},
)
replayed = replay_authority_state(
    hierarchy,
    teams,
    {"root-events": events, "root-inbox": inbox},
)

def write_readonly(relative, value):
    path = evidence / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    path.chmod(0o400)

for item in teams:
    team_id = item["team_id"]
    journal = root / f"teams/{team_id}/events.jsonl"
    append_journal_record(
        journal,
        journal_id=f"{team_id}-events",
        record_type="lifecycle",
        actor=f"lead-{team_id}",
        team_id=team_id,
        message_id=f"{team_id}-done",
        payload={"state": "completed"},
    )
    write_readonly(
        f"workers/{team_id}/result.json",
        {"schema": "agent-workflow/task-result/v1", "team_id": team_id},
    )
    write_readonly(f"reviews/{team_id}.json", {"review": "independent"})
    create_team_receipt(
        root,
        evidence,
        hierarchy,
        item,
        journals=(JournalReference("events", f"{team_id}-events", f"teams/{team_id}/events.jsonl"),),
        workers={team_id: (EvidenceReference("agent-workflow/task-result/v1", f"workers/{team_id}/result.json"),)},
        review_evidence=(EvidenceReference("independent", f"reviews/{team_id}.json"),),
        budget_usage={
            "workers_started": 1,
            "peak_concurrent_workers": 1,
            "peak_interactive_panes": 2,
            "retries": 0,
            "wall_seconds": 10,
        },
        terminal_disposition="completed",
    )
append_journal_record(
    root / "root-events.jsonl",
    journal_id="root-events",
    record_type="lifecycle",
    actor="orchestrator-001",
    message_id="root-done",
    payload={"state": "completed"},
)
write_readonly("bindings/summary.json", {"bound": True})
write_readonly("approvals/root-final.json", {"approved": True})
created_receipt = create_root_receipt(
    root,
    evidence,
    root_journals=(JournalReference("events", "root-events", "root-events.jsonl"),),
    cross_team_bindings=(EvidenceReference("cross-team-summary", "bindings/summary.json"),),
    approval_evidence=(EvidenceReference("root-final", "approvals/root-final.json"),),
    outcome="completed",
)
verified_receipt = verify_root_receipt(root, evidence)
print(json.dumps({
    "contract_identity_bound": all(
        item["hierarchy_identity_sha256"] == loaded_hierarchy["identity_sha256"]
        for item in loaded_teams
    ),
    "contract_manifest_idempotent": manifest == second_manifest == loaded_manifest,
    "contract_mode": oct((root / "hierarchy.json").stat().st_mode & 0o777),
    "team_ids": [item["team_id"] for item in loaded_teams],
    "journal_import_idempotent": first_import == second_import,
    "journal_records": len(read_journal(inbox, expected_journal_id="root-inbox")),
    "replayed_state": replayed["teams"]["implementation"]["state"],
    "replayed_import_count": replayed["teams"]["implementation"]["import_count"],
    "receipt_schema": verified_receipt["schema"],
    "receipt_outcome": verified_receipt["outcome"],
    "receipt_teams": [item["team_id"] for item in verified_receipt["teams"]],
    "receipt_round_trip": created_receipt == verified_receipt,
    "receipt_mode": oct((root / "root-receipt.json").stat().st_mode & 0o777),
}, sort_keys=True))
'''
    result = subprocess.run(
        [str(installed_product.python), "-c", script, str(root), str(evidence)],
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "contract_identity_bound": True,
        "contract_manifest_idempotent": True,
        "contract_mode": "0o400",
        "journal_import_idempotent": True,
        "journal_records": 1,
        "receipt_mode": "0o400",
        "receipt_outcome": "completed",
        "receipt_round_trip": True,
        "receipt_schema": "agent-workflow/root-orchestration-receipt/v1",
        "receipt_teams": ["implementation", "review"],
        "replayed_import_count": 1,
        "replayed_state": "ready",
        "team_ids": ["implementation", "review"],
    }
