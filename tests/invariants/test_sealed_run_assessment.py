from __future__ import annotations

import json
from pathlib import Path

from agent_workflow.eval.assessment import assess_exported_run, assess_exported_runs
from agent_workflow.util import sha256_file


def _export(root: Path, *, plan: bool = False, score: bool = False) -> Path:
    run = root / "run-1"
    run.mkdir()
    completion = {"schema": "agent-workflow/completion/v1", "session_id": "run-1", "result": "completed"}
    (run / "completion.json").write_text(json.dumps(completion), encoding="utf-8")
    artifacts = [{"path": "completion.json", "sha256": sha256_file(run / "completion.json"), "size": (run / "completion.json").stat().st_size},
                 {"path": "prompt.md", "sha256": "0" * 64, "size": 1}]
    if plan:
        artifacts.append({"path": "evaluation-runtime.json", "sha256": "1" * 64, "size": 1})
    if score:
        artifacts.append({"path": "scores/score-set.json", "sha256": "2" * 64, "size": 1})
    receipt = {"schema": "agent-workflow/final-receipt/v1", "session_id": "run-1", "sealed_at": "2026-07-26T00:00:00+00:00", "artifacts": artifacts}
    (run / "final-receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return run


def test_missing_plan_remains_missing_and_not_comparable(tmp_path: Path) -> None:
    row = assess_exported_run(_export(tmp_path))
    assert row["completion"]["valid"] is True
    assert row["evaluation"]["state"] == "missing-plan"
    assert row["evaluation"]["score_set_present"] is False
    assert row["comparable"] is False


def test_partial_score_evidence_is_not_promoted_to_complete(tmp_path: Path) -> None:
    run = _export(tmp_path, plan=True, score=True)
    (run / "evaluation-runtime.json").write_text("{}", encoding="utf-8")
    (run / "scores").mkdir()
    (run / "scores" / "score-set.json").write_text("{}", encoding="utf-8")
    row = assess_exported_run(run)
    assert row["evaluation"]["state"] == "incomplete-report"
    assert row["comparable"] is False


def test_receipt_listed_but_unexported_evaluation_files_remain_missing(tmp_path: Path) -> None:
    row = assess_exported_run(_export(tmp_path, plan=True, score=True))
    assert row["evaluation"]["plan_present"] is False
    assert row["evaluation"]["score_set_present"] is False
    assert row["evaluation"]["state"] == "missing-plan"


def test_completion_without_receipt_digest_is_not_valid(tmp_path: Path) -> None:
    run = _export(tmp_path)
    receipt = json.loads((run / "final-receipt.json").read_text(encoding="utf-8"))
    receipt["artifacts"] = []
    (run / "final-receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    row = assess_exported_run(run)
    assert row["completion"]["valid"] is False
    assert row["completion"]["matches_final_receipt"] is None


def test_exported_receipt_distinguishes_structure_from_portable_verification(tmp_path: Path) -> None:
    row = assess_exported_run(_export(tmp_path))
    assert row["lifecycle_seal"]["receipt_structurally_valid"] is True
    assert row["lifecycle_seal"]["portable_verification"] == "unavailable"
    assert "prompt.md" in row["lifecycle_seal"]["missing_artifacts"]


def test_collection_preserves_environment_limitations(tmp_path: Path) -> None:
    _export(tmp_path)
    result = assess_exported_runs(tmp_path)
    assert result["summary"] == {"run_count": 1, "completion_valid_count": 1, "portable_seal_verified_count": 0, "comparable_count": 0}
