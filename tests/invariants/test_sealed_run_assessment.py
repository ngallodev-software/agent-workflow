from __future__ import annotations

import json
from pathlib import Path

from agent_workflow.eval.assessment import (
    _verify_trial_collection,
    assess_exported_run,
    assess_exported_runs,
)
from agent_workflow.util import atomic_write_json, sha256_file
from tests.support import trial


def _export(root: Path, *, plan: bool = False, score: bool = False) -> Path:
    run = root / "run-1"
    run.mkdir()
    completion = {
        "schema": "agent-workflow/completion/v1",
        "agent_run_id": "run-1",
        "ticket_id": "T-1",
        "pack_id": "pack-1",
        "result": "completed",
        "base_revision": "base",
        "head_revision": "head",
        "changed_files": [],
        "criteria": [],
        "commands": [],
        "unresolved": [],
    }
    (run / "completion.json").write_text(json.dumps(completion), encoding="utf-8")
    artifacts = [{"path": "completion.json", "sha256": sha256_file(run / "completion.json"), "size": (run / "completion.json").stat().st_size},
                 {"path": "prompt.md", "sha256": "0" * 64, "size": 1}]
    if plan:
        artifacts.append({"path": "evaluation-runtime.json", "sha256": "1" * 64, "size": 1})
    if score:
        artifacts.append({"path": "scores/score-set.json", "sha256": "2" * 64, "size": 1})
    receipt = {"schema": "agent-workflow/final-receipt/v1", "agent_run_id": "run-1", "sealed_at": "2026-07-26T00:00:00+00:00", "artifacts": artifacts}
    (run / "final-receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return run


def test_missing_plan_remains_missing_and_not_comparable(tmp_path: Path) -> None:
    row = assess_exported_run(_export(tmp_path))
    assert row["completion"]["valid"] is True
    assert row["evaluation"]["state"] == "missing-plan"
    assert row["evaluation"]["score_set_present"] is False
    assert row["comparable"] is False


def test_invalid_plan_stops_evaluation_before_partial_score_is_promoted(tmp_path: Path) -> None:
    run = _export(tmp_path, plan=True, score=True)
    (run / "evaluation-runtime.json").write_text("{}", encoding="utf-8")
    (run / "scores").mkdir()
    (run / "scores" / "score-set.json").write_text("{}", encoding="utf-8")
    row = assess_exported_run(run)
    assert row["evaluation"]["state"] == "invalid-plan"
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


def test_tampered_sealed_artifact_is_not_verified(tmp_path: Path) -> None:
    run = _export(tmp_path)
    completion = json.loads((run / "completion.json").read_text(encoding="utf-8"))
    completion["result"] = "failed"
    (run / "completion.json").write_text(json.dumps(completion), encoding="utf-8")

    row = assess_exported_run(run)
    assert row["completion"]["valid"] is False
    assert row["lifecycle_seal"]["portable_verification"] == "not_verified"
    assert "sealed artifact checksum mismatch: completion.json" in row["unresolved_contradictions"]
    assert row["comparable"] is False


def test_scope_drift_and_malformed_provider_stream_are_not_verified(tmp_path: Path) -> None:
    run = _export(tmp_path)
    raw = b'{"type":"usage"}\n'
    (run / "executor-events.jsonl").write_bytes(raw)
    usage = {
        "input_tokens": 1,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 1,
        "reasoning_output_tokens": 0,
        "provider_total_tokens": 2,
        "provider_billed_cost": None,
        "local_estimated_cost": None,
        "currency": None,
        "price_catalog_id": None,
    }
    provider = {
        "schema": "agent-workflow/provider-evidence/v1",
        "agent_run_id": "run-1",
        "executor": "fixture",
        "stream_format": "jsonl",
        "created_at": "2026-07-27T00:00:00+00:00",
        "raw_events_path": "executor-events.jsonl",
        "raw_events_sha256": "f" * 64,
        "raw_event_bytes": len(raw),
        "capture_limit_bytes": 1024,
        "capture_complete": True,
        "malformed_event_count": 1,
        "classified_usage_count": 1,
        "retry_of_agent_run_id": None,
        "usage_complete": True,
        "incomplete_reasons": [],
        "usage_events": [],
        "aggregate": usage,
    }
    (run / "provider-evidence.json").write_text(json.dumps(provider), encoding="utf-8")
    scope = run / "scope"
    scope.mkdir()
    policy = {
        "authorized_root": str(run),
        "writable_paths": [],
        "writable_trees": [],
        "disposable_trees": [],
    }
    baseline = {
        "schema": "agent-workflow/scope-snapshot/v1",
        "phase": "baseline",
        "root": str(run),
        "captured_at": "2026-07-27T00:00:00+00:00",
        "policy": policy,
        "repositories": [],
        "inventory": [],
        "excluded": [],
    }
    post = {
        **baseline,
        "phase": "post",
        "inventory": [
            {
                "path": "outside.txt",
                "mode": 420,
                "size": 1,
                "kind": "file",
                "sha256": "a" * 64,
            }
        ],
    }
    (scope / "scope-baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
    (scope / "scope-post.json").write_text(json.dumps(post), encoding="utf-8")

    row = assess_exported_run(run)
    assert row["structured_stream"]["state"] == "not_verified"
    assert row["scope_audit"]["state"] == "not_verified"
    assert row["scope_audit"]["violations"] == ["outside.txt"]
    assert any("raw-events digest mismatch" in item for item in row["unresolved_contradictions"])
    assert any("malformed events" in item for item in row["failures"])


def test_trial_collection_is_bound_to_run_and_sealed_evidence(tmp_path: Path) -> None:
    run = tmp_path / "run-1"
    run.mkdir()
    collection = run / "trials.json"
    value = trial("run-1", "pass")
    atomic_write_json(
        collection,
        {
            "schema": "agent-workflow/trial-evidence/v2",
            "collected_at": "2026-07-27T00:00:00+00:00",
            "trials": [value],
        },
    )
    failures: list[str] = []
    contradictions: list[str] = []
    assert _verify_trial_collection(
        run,
        collection,
        final_receipt_sha256="1" * 64,
        sealed_artifacts={"provider-evidence.json": {"sha256": "2" * 64}},
        provider={"raw_events_sha256": "3" * 64},
        score_verdict="pass",
        failures=failures,
        contradictions=contradictions,
    )
    assert failures == []
    assert contradictions == []

    value["final_receipt_sha256"] = "f" * 64
    value["verdict"] = "fail"
    atomic_write_json(
        collection,
        {
            "schema": "agent-workflow/trial-evidence/v2",
            "collected_at": "2026-07-27T00:00:00+00:00",
            "trials": [value],
        },
    )
    contradictions = []
    assert not _verify_trial_collection(
        run,
        collection,
        final_receipt_sha256="1" * 64,
        sealed_artifacts={"provider-evidence.json": {"sha256": "2" * 64}},
        provider={"raw_events_sha256": "3" * 64},
        score_verdict="pass",
        failures=[],
        contradictions=contradictions,
    )
    assert contradictions == [
        "trial collection final-receipt digest mismatch",
        "trial collection score verdict mismatch",
    ]
