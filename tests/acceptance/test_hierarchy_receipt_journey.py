from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.conftest import InstalledProduct
from tests.invariants.test_hierarchy_contracts import valid_contracts


def test_installed_product_seals_and_verifies_hierarchy_receipts(
    installed_product: InstalledProduct,
    tmp_path: Path,
) -> None:
    hierarchy, teams = valid_contracts()
    hierarchy_path = tmp_path / "hierarchy.json"
    teams_path = tmp_path / "teams.json"
    hierarchy_path.write_text(json.dumps(hierarchy), encoding="utf-8")
    teams_path.write_text(json.dumps(teams), encoding="utf-8")
    root = tmp_path / "orchestration"
    evidence = tmp_path / "evidence"
    evidence.mkdir()

    script = r'''
import json
import os
import sys
from pathlib import Path
from agent_workflow.hierarchy import (
    EvidenceReference,
    JournalReference,
    append_journal_record,
    create_root_receipt,
    create_team_receipt,
    install_contract_set,
    verify_root_receipt,
)

hierarchy = json.loads(Path(sys.argv[1]).read_text())
teams = json.loads(Path(sys.argv[2]).read_text())
root = Path(sys.argv[3])
evidence = Path(sys.argv[4])
install_contract_set(root, hierarchy, teams)

def write_readonly(relative, value):
    path = evidence / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    path.chmod(0o400)

for team in teams:
    team_id = team["team_id"]
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
        team,
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
created = create_root_receipt(
    root,
    evidence,
    root_journals=(JournalReference("events", "root-events", "root-events.jsonl"),),
    cross_team_bindings=(EvidenceReference("cross-team-summary", "bindings/summary.json"),),
    approval_evidence=(EvidenceReference("root-final", "approvals/root-final.json"),),
    outcome="completed",
)
verified = verify_root_receipt(root, evidence)
print(json.dumps({
    "schema": verified["schema"],
    "outcome": verified["outcome"],
    "teams": [item["team_id"] for item in verified["teams"]],
    "same": created == verified,
    "mode": oct((root / "root-receipt.json").stat().st_mode & 0o777),
}, sort_keys=True))
'''
    result = subprocess.run(
        [
            str(installed_product.python),
            "-c",
            script,
            str(hierarchy_path),
            str(teams_path),
            str(root),
            str(evidence),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "mode": "0o400",
        "outcome": "completed",
        "same": True,
        "schema": "agent-workflow/root-orchestration-receipt/v1",
        "teams": ["implementation", "review"],
    }
