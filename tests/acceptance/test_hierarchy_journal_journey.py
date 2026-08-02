from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.conftest import InstalledProduct
from tests.invariants.test_hierarchy_contracts import valid_contracts


def test_installed_product_appends_imports_and_replays_hierarchy_journals(
    installed_product: InstalledProduct,
    tmp_path: Path,
) -> None:
    hierarchy, teams = valid_contracts()
    hierarchy_path = tmp_path / "hierarchy.json"
    teams_path = tmp_path / "teams.json"
    hierarchy_path.write_text(json.dumps(hierarchy), encoding="utf-8")
    teams_path.write_text(json.dumps(teams), encoding="utf-8")
    journal_root = tmp_path / "journals"
    journal_root.mkdir()

    script = r'''
import json
import sys
from pathlib import Path
from agent_workflow.hierarchy import append_journal_record, read_journal, replay_authority_state

hierarchy = json.loads(Path(sys.argv[1]).read_text())
teams = json.loads(Path(sys.argv[2]).read_text())
root = Path(sys.argv[3])
events = root / "events.jsonl"
inbox = root / "inbox.jsonl"
append_journal_record(
    events,
    journal_id="root-events",
    record_type="lifecycle",
    actor="orchestrator-001",
    team_id="implementation",
    message_id="event-1",
    payload={"state": "ready"},
)
first = append_journal_record(
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
second = append_journal_record(
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
state = replay_authority_state(
    hierarchy,
    teams,
    {"root-events": events, "root-inbox": inbox},
)
print(json.dumps({
    "idempotent": first == second,
    "inbox_records": len(read_journal(inbox, expected_journal_id="root-inbox")),
    "team_state": state["teams"]["implementation"]["state"],
    "import_count": state["teams"]["implementation"]["import_count"],
}, sort_keys=True))
'''
    result = subprocess.run(
        [
            str(installed_product.python),
            "-c",
            script,
            str(hierarchy_path),
            str(teams_path),
            str(journal_root),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "idempotent": True,
        "import_count": 1,
        "inbox_records": 1,
        "team_state": "ready",
    }
