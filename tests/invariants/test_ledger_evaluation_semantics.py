from pathlib import Path
import json

from agent_workflow.ledger import build_ledger


def test_ledger_keeps_task_row_when_evaluation_was_not_planned(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    phase = pack / "phase-0"
    phase.mkdir(parents=True)
    (phase / "task-manifest.yaml").write_text(
        'phase: "0"\ntasks:\n  - id: T-1\n    session: run-1\n    prompt: ticket.md\n', encoding="utf-8"
    )
    runs = tmp_path / "runs"
    run = runs / "run-1"
    run.mkdir(parents=True)
    (run / "status.json").write_text(json.dumps({"status": "completed", "evaluation_path": None}), encoding="utf-8")

    row = build_ledger(pack, runs)["rows"][0]
    assert row["ticket"] == "T-1"
    assert row["evaluation_required"] is False
    assert row["evaluation_state"] == "not-planned"
    assert "eval score" not in row["next_action"]
