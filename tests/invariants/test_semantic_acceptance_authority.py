from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.eval.scoring import (
    _has_file_backed_evidence,
    _semantic_criterion_ids,
)
from agent_workflow.lifecycle import _check_acceptance_gates


def test_semantic_evidence_requires_host_hashed_file_reference() -> None:
    assert _has_file_backed_evidence(
        {
            "evidence": [
                "file:src/example.py#sha256=" + ("a" * 64) + ";bytes=42"
            ]
        }
    )
    assert not _has_file_backed_evidence({"evidence": ["I inspected src/example.py"]})
    assert not _has_file_backed_evidence(
        {
            "evidence": [
                "file:../secret#sha256=" + ("b" * 64) + ";bytes=10"
            ]
        }
    )


def test_semantic_criteria_are_derived_from_precommitted_job_binding(
    tmp_path: Path,
) -> None:
    final = {
        "artifacts": [
            {"path": "job-binding.json", "sha256": "a" * 64}
        ]
    }
    binding = {
        "criteria": [
            {"id": "semantic", "acceptance_command_ids": []},
            {"id": "deterministic", "acceptance_command_ids": ["tests"]},
        ]
    }
    with patch(
        "agent_workflow.eval.scoring._sealed_load",
        return_value=binding,
    ):
        assert _semantic_criterion_ids(tmp_path, final) == ("semantic",)


def test_precommitted_independent_review_cannot_be_waived_at_acceptance() -> None:
    with pytest.raises(WorkflowError, match="precommitted job"):
        _check_acceptance_gates(
            final_status={"tier": "low", "policy_result": "passed"},
            completion={"result": "completed"},
            collection={"validation_status": "valid"},
            score=None,
            score_hash=None,
            reviewed={
                "score_receipt_sha256": None,
                "reviewer_independent": False,
            },
            independent=True,
            independent_review_required=True,
        )

    _check_acceptance_gates(
        final_status={"tier": "low", "policy_result": "passed"},
        completion={"result": "completed"},
        collection={"validation_status": "valid"},
        score=None,
        score_hash=None,
        reviewed={
            "score_receipt_sha256": None,
            "reviewer_independent": True,
        },
        independent=True,
        independent_review_required=True,
    )
