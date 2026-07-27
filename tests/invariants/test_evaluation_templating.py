from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.evaluation import validate_evaluation
from agent_workflow.eval.templating import (
    TEMPLATE_KINDS,
    build_benchmark_report,
    build_ledger_row,
    build_lifecycle_archive,
    load_template,
    validate_benchmark_manifest,
    write_template,
)
from agent_workflow.util import atomic_write_json
from tests.support import trial


def _collection(path: Path, *values: dict) -> None:
    atomic_write_json(
        path,
        {
            "schema": "agent-workflow/trial-evidence/v2",
            "collected_at": "2026-07-27T00:00:00+00:00",
            "trials": list(values),
        },
    )


def _manifest(path: Path) -> dict:
    value = load_template("benchmark-manifest")
    value["cohorts"]["baseline"].update(
        source_revision="source-v1",
        model="fixture-model",
        executor="codex",
        executor_version="fixture-v1",
    )
    value["cohorts"]["candidate"].update(
        source_revision="source-v1",
        model="fixture-model",
        executor="codex",
        executor_version="fixture-v1",
    )
    value["cases"][0].update(case_id="case-001", task_id="task-1", repetition=0)
    atomic_write_json(path, value)
    return value


def test_all_templates_are_valid_and_repeatable(tmp_path: Path) -> None:
    for kind in TEMPLATE_KINDS:
        first = tmp_path / f"{kind}-1.json"
        second = tmp_path / f"{kind}-2.json"
        write_template(kind, first)
        write_template(kind, second)
        assert first.read_bytes() == second.read_bytes()
        assert json.loads(first.read_text(encoding="utf-8"))["schema"] == load_template(kind)["schema"]


def test_benchmark_report_preserves_unavailable_cases_and_rejects_identity_drift(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest = _manifest(manifest_path)
    manifest["cases"].append(
        {
            **manifest["cases"][0],
            "case_id": "case-unavailable",
            "task_id": "task-unavailable",
            "expected_evidence_class": "unavailable",
            "availability": {"state": "unavailable", "reason": "external oracle was not supplied"},
        }
    )
    atomic_write_json(manifest_path, manifest)
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    _collection(baseline_path, trial("baseline", "pass"))
    _collection(candidate_path, trial("candidate", "pass"))

    report = build_benchmark_report(manifest_path, baseline_path, candidate_path)
    unavailable = next(case for case in report["cases"] if case["case_id"] == "case-unavailable")
    assert unavailable["state"] == "unavailable"
    assert unavailable["baseline"] is None
    assert unavailable["candidate"] is None
    assert report["missingness"]["unavailable_case_count"] == 1

    manifest["cohorts"]["candidate"]["source_revision"] = "different-source"
    atomic_write_json(manifest_path, manifest)
    with pytest.raises(WorkflowError, match="source_revision mismatch"):
        build_benchmark_report(manifest_path, baseline_path, candidate_path)


def test_manifest_rejects_duplicate_cases_and_scope_escape(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    value = _manifest(manifest_path)
    value["cases"].append(dict(value["cases"][0]))
    atomic_write_json(manifest_path, value)
    with pytest.raises(WorkflowError, match="duplicate case IDs"):
        validate_benchmark_manifest(manifest_path)

    value["cases"][1]["case_id"] = "case-002"
    value["cases"][1]["task_id"] = "task-2"
    value["cases"][1]["allowed_writable_scope"]["writable_trees"] = ["../escape/"]
    atomic_write_json(manifest_path, value)
    with pytest.raises(WorkflowError, match="normalized relative path"):
        validate_benchmark_manifest(manifest_path)

    value["cases"][1]["allowed_writable_scope"]["writable_trees"] = ["src\\escape/"]
    atomic_write_json(manifest_path, value)
    with pytest.raises(WorkflowError, match="normalized relative path"):
        validate_benchmark_manifest(manifest_path)


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


def test_benchmark_report_preserves_missing_trials_without_fabricating_a_score(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    _manifest(manifest_path)
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    _collection(baseline_path, trial("baseline", "pass"))
    atomic_write_json(
        candidate_path,
        {
            "schema": "agent-workflow/trial-evidence/v2",
            "collected_at": "2026-07-27T00:00:00+00:00",
            "trials": [],
        },
    )

    first = build_benchmark_report(manifest_path, baseline_path, candidate_path)
    second = build_benchmark_report(manifest_path, baseline_path, candidate_path)
    assert first == second
    assert first["aggregate_metrics"]["paired_n"] == 0
    assert first["cases"][0]["state"] == "not_verified"
    assert first["cases"][0]["missing_evidence"]["candidate"] == ["trial"]
    assert first["candidate"]["identity_verification"]["state"] == "not_verified"


def test_benchmark_report_rejects_prompt_digest_mismatch(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    _manifest(manifest_path)
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    bad = trial("baseline", "pass")
    bad["prompt_sha256"] = "a" * 64
    _collection(baseline_path, bad)
    _collection(candidate_path, trial("candidate", "pass"))

    with pytest.raises(WorkflowError, match="prompt_sha256 mismatch"):
        build_benchmark_report(manifest_path, baseline_path, candidate_path)


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


def test_benchmark_report_marks_declared_reference_and_fixture_digests_unverified(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    value = _manifest(manifest_path)
    value["cases"][0]["reference"] = {"id": "reference-v1", "sha256": "a" * 64}
    value["cases"][0]["fixture_provenance"]["sha256"] = "b" * 64
    atomic_write_json(manifest_path, value)
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    _collection(baseline_path, trial("baseline", "pass"))
    _collection(candidate_path, trial("candidate", "pass"))

    report = build_benchmark_report(manifest_path, baseline_path, candidate_path)
    assert report["aggregate_metrics"]["paired_n"] == 0
    assert report["cases"][0]["state"] == "not_verified"
    assert report["cases"][0]["missing_evidence"] == {
        "baseline": ["fixture_sha256", "reference_sha256"],
        "candidate": ["fixture_sha256", "reference_sha256"],
    }


def test_benchmark_report_counts_trials_outside_the_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    _manifest(manifest_path)
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    _collection(
        baseline_path,
        trial("baseline", "pass"),
        trial("baseline-extra", "pass", task_id="extra"),
    )
    _collection(
        candidate_path,
        trial("candidate", "pass"),
        trial("candidate-extra", "pass", task_id="extra"),
    )

    report = build_benchmark_report(manifest_path, baseline_path, candidate_path)
    assert report["aggregate_metrics"]["paired_n"] == 1
    assert report["missingness"]["unmatched_baseline_count"] == 1
    assert report["missingness"]["unmatched_candidate_count"] == 1
    assert report["unmatched_trials"] == {
        "baseline": ["baseline-extra"],
        "candidate": ["candidate-extra"],
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

