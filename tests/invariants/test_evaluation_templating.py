from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.evaluation import validate_evaluation
from agent_workflow.eval.templating import (
    TEMPLATE_KINDS,
    build_ledger_row,
    build_lifecycle_archive,
    load_template,
    write_template,
)
from agent_workflow.util import atomic_write_json


def test_all_templates_are_valid_and_repeatable(tmp_path: Path) -> None:
    for kind in TEMPLATE_KINDS:
        first = tmp_path / f"{kind}-1.json"
        second = tmp_path / f"{kind}-2.json"
        write_template(kind, first)
        write_template(kind, second)
        assert first.read_bytes() == second.read_bytes()
        assert json.loads(first.read_text(encoding="utf-8"))["schema"] == load_template(kind)["schema"]


def test_ledger_and_archive_keep_missing_evidence_explicit(tmp_path: Path) -> None:
    run = tmp_path / "run-1"
    run.mkdir()
    atomic_write_json(run / "status.json", {"status": "completed", "evaluation_path": "evaluation.json", "ticket_id": "T-1", "pack_id": "pack-1"})
    atomic_write_json(run / "run-provenance.json", {"source_revision": "abc", "pack_manifest_sha256": None})
    (run / "MANIFEST.sha256").write_text("ignored\n", encoding="utf-8")
    (run / "transfer.sha256").write_text("ignored\n", encoding="utf-8")

    row = build_ledger_row(run)
    assert row["receipt_verification"] == "unavailable"
    assert row["evaluation_state"] == "not_verified"
    assert row["evaluation_result"] is None
    assert row["failures"]

    first = build_lifecycle_archive(run, retention_class="standard")
    second = build_lifecycle_archive(run, retention_class="standard")
    assert first == second
    assert {item["path"] for item in first["export_contents"]} == {"run-provenance.json", "status.json"}
    assert first["transfer_checksum"]["required_in_repository"] is False


def test_archive_plan_excludes_its_own_output_on_repeat(tmp_path: Path) -> None:
    run = tmp_path / "run-1"
    run.mkdir()
    (run / "evidence.json").write_text("{}\n", encoding="utf-8")
    output = run / "archive-plan.json"

    first = build_lifecycle_archive(
        run, retention_class="standard", exclude_paths=(output,)
    )
    atomic_write_json(output, first)
    second = build_lifecycle_archive(
        run, retention_class="standard", exclude_paths=(output,)
    )
    assert first == second
    assert "archive-plan.json" not in {
        item["path"] for item in second["export_contents"]
    }


def test_rich_evaluation_plan_rejects_incoherent_controls(tmp_path: Path) -> None:
    path = tmp_path / "evaluation.json"
    value = load_template("evaluation-plan")
    value["stopping_rules"].update(minimum_cases=2, maximum_cases=1)
    atomic_write_json(path, value)
    with pytest.raises(WorkflowError, match="minimum_cases exceeds"):
        validate_evaluation(path)

    value["stopping_rules"].update(minimum_cases=1, maximum_cases=1)
    value["metrics"].append(dict(value["metrics"][0]))
    atomic_write_json(path, value)
    with pytest.raises(WorkflowError, match="duplicate metric IDs"):
        validate_evaluation(path)
