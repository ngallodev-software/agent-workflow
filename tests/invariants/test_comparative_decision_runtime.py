from __future__ import annotations
from dataclasses import replace
from pathlib import Path

import pytest
from agent_workflow.config import defaults
from agent_workflow.comparative_eval_runtime import EvidenceStore
from agent_workflow.scheduler import SchedulerService


def _semantic(
    semantic_type: str,
    value,
    *,
    probability=None,
    confidence=None,
    distribution=None,
):
    return {
        "status": "success",
        "semantic_type": semantic_type,
        "confidence": confidence,
        "probability": probability,
        "distribution": distribution or {},
        "model": "jev-test",
        "question_set_version": "routing/v2",
        "projector_version": "routing-state/v2",
        "request_sha256": "a" * 64,
        "request_id": "req-routing-1",
        "usage": {
            "input_tokens": 120,
            "output_tokens": 3,
            "provider_total_tokens": 123,
            "token_evidence_complete": True,
            "cost_evidence_complete": False,
        },
        "source_refs": ["T1"],
        "error_class": None,
    }


def test_scheduler_persists_lossless_per_seam_comparative_evidence_without_raw_text(
    tmp_path: Path,
) -> None:
    pytest.importorskip("agent_workflow_comparative_eval")
    settings = replace(defaults(tmp_path / "missing.toml"), decision_mode="comparative")
    service = SchedulerService(settings=settings, run_dir=tmp_path / "workflow", workdir=tmp_path)

    advice = {
        "decision_receipts": {
            "routing.task_class": {
                "control_result": "implementation",
                "evidence_result": "review",
                "policy_candidate_result": "review",
                "applied_result": "implementation",
                "fallback": {"used": False, "reason": None},
                "semantic": _semantic(
                    "choice",
                    "review",
                    confidence=0.91,
                    distribution={
                        "implementation": 0.03,
                        "diagnosis": 0.02,
                        "review": 0.91,
                        "documentation": 0.02,
                        "other": 0.02,
                    },
                ),
            },
            "routing.interaction_required": {
                "control_result": False,
                "evidence_result": 0.87,
                "policy_candidate_result": True,
                "applied_result": False,
                "fallback": {"used": False, "reason": None},
                "semantic": _semantic("noul", 0.87, probability=0.87),
            },
            "routing.semantic_risk": {
                "control_result": 1,
                "evidence_result": 1.6,
                "policy_candidate_result": None,
                "applied_result": 1,
                "fallback": {"used": True, "reason": "semantic_uncertainty"},
                "semantic": _semantic(
                    "score",
                    1.6,
                    confidence=0.7,
                    distribution={"0": 0.05, "1": 0.3, "2": 0.65},
                ),
            },
        },
        "decision_timing": {
            "control_seconds": 0.001,
            "provider_elapsed_seconds": 0.02,
            "candidate_policy_seconds": 0.001,
        },
    }
    node = {"workflow_id": "wf", "node_id": "node", "workflow_attempt": 1, "ticket_id": "T1"}

    capture = service._capture_routing_comparison(
        node,
        "run-1",
        {"task_type": "implementation"},
        "secret-ish task text",
        advice,
    )
    assert capture is not None
    assert len(capture["observation_ids"]) == 3
    assert capture["request_id"] == "req-routing-1"

    db = tmp_path / "workflow" / "comparative-eval.sqlite"
    assert db.is_file()
    assert "secret-ish task text" not in db.read_bytes().decode("utf-8", errors="ignore")

    service._join_comparative_outcomes(
        capture["observation_ids"],
        {
            "child_completion_result": "completed",
            "child_completion_validation_status": "valid",
            "child_status": "completed",
        },
    )

    store = EvidenceStore(db)
    try:
        observations = store.observations()
        assert len(observations) == 3
        by_feature = {item["feature_id"]: item for item in observations}

        task = by_feature["routing.task-class/v1"]
        assert task["comparison"]["normalized_candidate"] == "review"
        assert task["candidate"]["result"]["confidence"] == 0.91
        assert task["candidate"]["result"]["probabilities"]["review"] == 0.91

        interaction = by_feature["routing.interaction-required/v1"]
        assert interaction["comparison"]["normalized_candidate"] is True
        assert interaction["candidate"]["result"]["probability"] == 0.87

        risk = by_feature["routing.semantic-risk/v1"]
        assert risk["candidate"]["result"]["decision"] == 1.6
        assert risk["candidate"]["result"]["fallback"]["reason"] == "semantic_uncertainty"

        requests = store.provider_requests()
        assert len(requests) == 1
        assert requests[0]["request_id"] == "req-routing-1"
        assert requests[0]["duration_seconds"] == 0.02
        assert requests[0]["usage"]["input_tokens"] == 120

        assert len(store.outcomes()) == 3
    finally:
        store.close()
