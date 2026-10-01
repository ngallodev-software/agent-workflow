from __future__ import annotations

import json

import pytest

from agent_workflow.decision_checkpoint import (
    CheckpointPolicy,
    build_checkpoint_request,
    run_checkpoint,
)
from agent_workflow.errors import WorkflowError
from agent_workflow.plugin_api import DecisionEvidence


def _draft(initial: str = "proposal_1") -> dict[str, object]:
    return {
        "schema": "agent-workflow/decision-draft/v1",
        "draft_id": "draft-1",
        "decision_id": "implementation.proposal_selection/v1",
        "candidate_ids": ["proposal_0", "proposal_1"],
        "initial_agent_choice": initial,
        "rationale": "Proposal 1 appears to fit the observed mechanism with the narrowest scope.",
        "evidence_refs": ["issue.md", "proposal-0.diff", "proposal-1.diff"],
    }


def _context() -> dict[str, object]:
    return {
        "requirement": {
            "text": "Fix the nested control behavior without changing unrelated layout.",
            "source_ref": "issue.md",
        },
        "candidates": [
            {
                "candidate_id": "proposal_0",
                "artifact": "Patch proposal 0",
                "source_refs": ["proposal-0.diff"],
            },
            {
                "candidate_id": "proposal_1",
                "artifact": "Patch proposal 1",
                "source_refs": ["proposal-1.diff"],
            },
        ],
        "deterministic_evidence": [
            {
                "source_ref": "tests.txt",
                "kind": "test-result",
                "content": "12 passed",
                "scope": "focused tests only; integration not exercised",
            }
        ],
    }


def _policy(*, provider_failure: str = "block") -> CheckpointPolicy:
    return CheckpointPolicy(
        minimum_confidence=0.8,
        minimum_margin=0.1,
        provider_failure=provider_failure,
    )


def _choice(
    candidate: str,
    *,
    confidence: float = 0.9,
    probabilities: dict[str, float] | None = None,
) -> DecisionEvidence:
    return DecisionEvidence(
        "implementation.proposal_selection/v1",
        "success",
        "choice",
        value=candidate,
        confidence=confidence,
        distribution=probabilities
        or {candidate: 0.9, ("proposal_0" if candidate == "proposal_1" else "proposal_1"): 0.1},
        model="jev-test",
        request_id="req-1",
    )


def test_checkpoint_request_excludes_tentative_agent_choice() -> None:
    request = build_checkpoint_request(_draft(), _context())
    serialized_state = json.dumps(request["state"], sort_keys=True)
    assert "initial_agent_choice" not in serialized_state
    assert "narrowest scope" not in serialized_state
    assert "proposal_1" in serialized_state  # candidate artifact identity remains visible
    assert request["state"]["provider_authority"] == "evidence_only"


def test_agreement_auto_resolves_and_allows_advance() -> None:
    receipt = run_checkpoint(
        draft=_draft("proposal_1"),
        context=_context(),
        provider_name="test-provider",
        policy=_policy(),
        provider=lambda request: _choice("proposal_1"),
    )
    assert receipt["outcome"] == "agreement"
    assert receipt["advance_allowed"] is True
    assert receipt["applied_result"] == "proposal_1"
    assert receipt["resolution"]["basis"] == "semantic_agreement"
    assert receipt["provider"] == "test-provider"
    assert receipt["provider_elapsed_seconds"] >= 0
    assert receipt["policy"] == {
        "minimum_confidence": 0.8,
        "minimum_margin": 0.1,
        "provider_failure": "block",
    }
    assert receipt["candidate_ids"] == ["proposal_0", "proposal_1"]
    assert set(receipt["projected_source_refs"]) == {
        "issue.md", "proposal-0.diff", "proposal-1.diff", "tests.txt"
    }


def test_disagreement_blocks_without_reconciliation() -> None:
    receipt = run_checkpoint(
        draft=_draft("proposal_1"),
        context=_context(),
        provider_name="test-provider",
        policy=_policy(),
        provider=lambda request: _choice("proposal_0"),
    )
    assert receipt["outcome"] == "disagreement"
    assert receipt["advance_allowed"] is False
    assert receipt["resolution"] is None
    assert receipt["applied_result"] is None


def test_disagreement_can_accept_semantic_candidate_explicitly() -> None:
    receipt = run_checkpoint(
        draft=_draft("proposal_1"),
        context=_context(),
        provider_name="test-provider",
        policy=_policy(),
        provider=lambda request: _choice("proposal_0"),
        resolution={
            "schema": "agent-workflow/decision-resolution/v1",
            "decision_id": "implementation.proposal_selection/v1",
            "draft_id": "draft-1",
            "initial_agent_choice": "proposal_1",
            "semantic_candidate": "proposal_0",
            "resolved_choice": "proposal_0",
            "disposition": "accept_semantic_candidate",
            "basis": "semantic_evidence",
            "actor": "agent:luna",
            "reason": "The independent semantic comparison identifies proposal 0 as the stronger match.",
            "evidence_refs": [],
        },
    )
    assert receipt["advance_allowed"] is True
    assert receipt["applied_result"] == "proposal_0"


def test_rejecting_semantic_candidate_requires_independent_evidence() -> None:
    with pytest.raises(WorkflowError, match="requires evidence_refs"):
        run_checkpoint(
            draft=_draft("proposal_1"),
            context=_context(),
            provider_name="test-provider",
            policy=_policy(),
            provider=lambda request: _choice("proposal_0"),
            resolution={
                "schema": "agent-workflow/decision-resolution/v1",
                "decision_id": "implementation.proposal_selection/v1",
                "draft_id": "draft-1",
                "initial_agent_choice": "proposal_1",
                "semantic_candidate": "proposal_0",
                "resolved_choice": "proposal_1",
                "disposition": "reject_semantic_candidate",
                "basis": "additional_evidence",
                "actor": "agent:luna",
                "reason": "Attempted override without an actual evidence reference.",
                "evidence_refs": [],
            },
        )

    receipt = run_checkpoint(
        draft=_draft("proposal_1"),
        context=_context(),
        provider_name="test-provider",
        policy=_policy(),
        provider=lambda request: _choice("proposal_0"),
        resolution={
            "schema": "agent-workflow/decision-resolution/v1",
            "decision_id": "implementation.proposal_selection/v1",
            "draft_id": "draft-1",
            "initial_agent_choice": "proposal_1",
            "semantic_candidate": "proposal_0",
            "resolved_choice": "proposal_1",
            "disposition": "reject_semantic_candidate",
            "basis": "deterministic_authority",
            "actor": "agent:luna",
            "reason": "A deterministic type-check failure invalidates the semantic candidate.",
            "evidence_refs": ["typecheck.txt"],
        },
    )
    assert receipt["advance_allowed"] is True
    assert receipt["applied_result"] == "proposal_1"


def test_close_distribution_is_uncertainty_not_a_plurality_decision() -> None:
    receipt = run_checkpoint(
        draft=_draft("proposal_1"),
        context=_context(),
        provider_name="test-provider",
        policy=_policy(),
        provider=lambda request: _choice(
            "proposal_0",
            confidence=0.91,
            probabilities={"proposal_0": 0.52, "proposal_1": 0.48},
        ),
    )
    assert receipt["outcome"] == "uncertainty"
    assert receipt["advance_allowed"] is False


def test_uncertainty_can_only_advance_after_explicit_new_evidence_resolution() -> None:
    receipt = run_checkpoint(
        draft=_draft("proposal_1"),
        context=_context(),
        provider_name="test-provider",
        policy=_policy(),
        provider=lambda request: _choice(
            "proposal_0",
            confidence=0.91,
            probabilities={"proposal_0": 0.52, "proposal_1": 0.48},
        ),
        resolution={
            "schema": "agent-workflow/decision-resolution/v1",
            "decision_id": "implementation.proposal_selection/v1",
            "draft_id": "draft-1",
            "initial_agent_choice": "proposal_1",
            "semantic_candidate": "proposal_0",
            "resolved_choice": "proposal_1",
            "disposition": "resolve_uncertainty",
            "basis": "additional_evidence",
            "actor": "reviewer:independent",
            "reason": "A newly captured integration test distinguishes the candidates.",
            "evidence_refs": ["integration-test.txt"],
        },
    )
    assert receipt["outcome"] == "uncertainty"
    assert receipt["advance_allowed"] is True
    assert receipt["applied_result"] == "proposal_1"


def test_defer_or_escalate_cannot_claim_a_resolved_choice() -> None:
    with pytest.raises(WorkflowError, match="cannot carry a resolved_choice"):
        run_checkpoint(
            draft=_draft("proposal_1"),
            context=_context(),
            provider_name="test-provider",
            policy=_policy(),
            provider=lambda request: _choice("proposal_0"),
            resolution={
                "schema": "agent-workflow/decision-resolution/v1",
                "decision_id": "implementation.proposal_selection/v1",
                "draft_id": "draft-1",
                "initial_agent_choice": "proposal_1",
                "semantic_candidate": "proposal_0",
                "resolved_choice": "proposal_1",
                "disposition": "escalate_review",
                "basis": "independent_review",
                "actor": "agent:luna",
                "reason": "Independent review is required before choosing.",
                "evidence_refs": [],
            },
        )


def test_provider_failure_blocks_by_default() -> None:
    def failed(_request):
        raise RuntimeError("boom")

    receipt = run_checkpoint(
        draft=_draft(),
        context=_context(),
        provider_name="test-provider",
        policy=_policy(),
        provider=failed,
    )
    assert receipt["outcome"] == "provider_failure"
    assert receipt["advance_allowed"] is False
    assert receipt["semantic"]["error_class"] == "RuntimeError"


def test_provider_failure_fallback_requires_explicit_application_policy_and_receipt() -> None:
    receipt = run_checkpoint(
        draft=_draft("proposal_1"),
        context=_context(),
        provider_name="test-provider",
        policy=_policy(provider_failure="fallback_initial"),
        provider=lambda request: DecisionEvidence(
            "implementation.proposal_selection/v1", "service_failure", "choice"
        ),
        resolution={
            "schema": "agent-workflow/decision-resolution/v1",
            "decision_id": "implementation.proposal_selection/v1",
            "draft_id": "draft-1",
            "initial_agent_choice": "proposal_1",
            "semantic_candidate": None,
            "resolved_choice": "proposal_1",
            "disposition": "provider_fallback",
            "basis": "provider_failure_policy",
            "actor": "agent-workflow",
            "reason": "Configured provider-failure policy permits retaining the initial choice.",
            "evidence_refs": [],
        },
    )
    assert receipt["advance_allowed"] is True
    assert receipt["applied_result"] == "proposal_1"


def test_provider_success_requires_complete_candidate_distribution() -> None:
    receipt = run_checkpoint(
        draft=_draft(),
        context=_context(),
        provider_name="test-provider",
        policy=_policy(),
        provider=lambda request: DecisionEvidence(
            "implementation.proposal_selection/v1",
            "success",
            "choice",
            value="proposal_1",
            confidence=0.95,
            distribution={"proposal_1": 0.95},
        ),
    )
    assert receipt["outcome"] == "provider_failure"
    assert receipt["advance_allowed"] is False


def test_provider_evidence_identity_mismatch_fails_closed() -> None:
    receipt = run_checkpoint(
        draft=_draft(),
        context=_context(),
        provider_name="test-provider",
        policy=_policy(),
        provider=lambda request: DecisionEvidence(
            "implementation.proposal_selection/v1",
            "success",
            "choice",
            value="proposal_1",
            confidence=0.95,
            distribution={"proposal_0": 0.05, "proposal_1": 0.95},
            request_sha256="0" * 64,
        ),
    )
    assert receipt["outcome"] == "provider_failure"
    assert receipt["semantic"]["error_class"] == "provider_evidence_identity_mismatch"


def test_draft_evidence_refs_must_be_present_in_neutral_context() -> None:
    draft = _draft()
    draft["evidence_refs"] = list(draft["evidence_refs"]) + ["missing.txt"]
    with pytest.raises(WorkflowError, match="missing draft evidence refs"):
        build_checkpoint_request(draft, _context())


def test_context_must_contain_exactly_the_draft_candidates() -> None:
    context = _context()
    context["candidates"] = context["candidates"][:1]
    with pytest.raises(WorkflowError, match="exactly the draft candidates"):
        build_checkpoint_request(_draft(), context)
