"""Provider-neutral semantic checkpoint mechanics for bounded proposal selection.

This module is intentionally narrower than the production routing decision registry.
It prototypes the application-owned reconciliation contract for a future structural
workflow gate without granting a semantic provider lifecycle authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any, Callable, Literal, Mapping

from .contracts import validate_instance
from .errors import WorkflowError
from .plugin_api import DecisionEvidence

PROPOSAL_SELECTION_DECISION_ID = "implementation.proposal_selection/v1"
DECISION_DRAFT_SCHEMA = "agent-workflow/decision-draft/v1"
DECISION_RESOLUTION_SCHEMA = "agent-workflow/decision-resolution/v1"
SEMANTIC_CHECKPOINT_RECEIPT_SCHEMA = "agent-workflow/semantic-checkpoint-receipt/v1"
QUESTION_SET_VERSION = "implementation-proposal-selection/v1"
PROJECTOR_VERSION = "implementation-proposal-selection-state/v1"

MAX_CANDIDATES = 16
MAX_PROJECTED_STATE_BYTES = 64 * 1024

CheckpointOutcome = Literal[
    "agreement", "disagreement", "uncertainty", "provider_failure"
]
ProviderFailurePolicy = Literal["block", "fallback_initial"]
SemanticProvider = Callable[[Mapping[str, object]], DecisionEvidence]


@dataclass(frozen=True)
class CheckpointPolicy:
    """Application-owned evidence thresholds and provider-failure behavior."""

    minimum_confidence: float = 0.80
    minimum_margin: float = 0.10
    provider_failure: ProviderFailurePolicy = "block"

    def __post_init__(self) -> None:
        for name, value in (
            ("minimum_confidence", self.minimum_confidence),
            ("minimum_margin", self.minimum_margin),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.provider_failure not in {"block", "fallback_initial"}:
            raise ValueError("provider_failure must be 'block' or 'fallback_initial'")


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _unique_strings(value: object, *, field: str, minimum: int = 0) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise WorkflowError(f"{field} must be a list of non-empty strings")
    if len(value) < minimum:
        raise WorkflowError(f"{field} requires at least {minimum} entries")
    if len(value) != len(set(value)):
        raise WorkflowError(f"{field} contains duplicate entries")
    return list(value)


def normalize_decision_draft(value: Mapping[str, object]) -> dict[str, Any]:
    """Validate the investigation-produced decision draft.

    The tentative agent choice is preserved for reconciliation but is not part of the
    semantic-provider projection built by :func:`build_checkpoint_request`.
    """
    draft = dict(value)
    validate_instance(draft, DECISION_DRAFT_SCHEMA, artifact="decision draft")
    if draft.get("decision_id") != PROPOSAL_SELECTION_DECISION_ID:
        raise WorkflowError(
            f"unsupported checkpoint decision: {draft.get('decision_id')!r}"
        )
    candidate_ids = _unique_strings(
        draft.get("candidate_ids"), field="candidate_ids", minimum=2
    )
    if len(candidate_ids) > MAX_CANDIDATES:
        raise WorkflowError(f"candidate_ids exceeds {MAX_CANDIDATES} entries")
    initial = draft.get("initial_agent_choice")
    if initial not in candidate_ids:
        raise WorkflowError("initial_agent_choice must name one candidate_id")
    _unique_strings(draft.get("evidence_refs"), field="evidence_refs", minimum=1)
    return draft


def _normalize_context(
    draft: Mapping[str, object], context: Mapping[str, object]
) -> tuple[dict[str, object], tuple[str, ...]]:
    requirement = context.get("requirement")
    if not isinstance(requirement, Mapping):
        raise WorkflowError("checkpoint context requires requirement evidence")
    requirement_text = requirement.get("text")
    requirement_ref = requirement.get("source_ref")
    if not isinstance(requirement_text, str) or not requirement_text:
        raise WorkflowError("checkpoint requirement text must be non-empty")
    if not isinstance(requirement_ref, str) or not requirement_ref:
        raise WorkflowError("checkpoint requirement source_ref must be non-empty")

    raw_candidates = context.get("candidates")
    if not isinstance(raw_candidates, list):
        raise WorkflowError("checkpoint context candidates must be a list")
    candidate_ids = list(draft["candidate_ids"])
    by_id: dict[str, Mapping[str, object]] = {}
    for raw in raw_candidates:
        if not isinstance(raw, Mapping):
            raise WorkflowError("checkpoint candidate context entries must be objects")
        candidate_id = raw.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise WorkflowError("checkpoint candidate_id must be non-empty")
        if candidate_id in by_id:
            raise WorkflowError(f"duplicate checkpoint candidate context: {candidate_id}")
        by_id[candidate_id] = raw
    if set(by_id) != set(candidate_ids):
        raise WorkflowError("checkpoint context must contain exactly the draft candidates")

    projected_candidates: list[dict[str, object]] = []
    source_refs: list[str] = [requirement_ref]
    for candidate_id in candidate_ids:
        raw = by_id[candidate_id]
        artifact = raw.get("artifact")
        refs = _unique_strings(
            raw.get("source_refs"),
            field=f"candidates[{candidate_id}].source_refs",
            minimum=1,
        )
        if not isinstance(artifact, str) or not artifact:
            raise WorkflowError(f"candidate {candidate_id} artifact must be non-empty")
        projected_candidates.append(
            {
                "candidate_id": candidate_id,
                "artifact": artifact,
                "source_refs": refs,
            }
        )
        source_refs.extend(refs)

    raw_evidence = context.get("deterministic_evidence", [])
    if not isinstance(raw_evidence, list):
        raise WorkflowError("deterministic_evidence must be a list")
    projected_evidence: list[dict[str, object]] = []
    for index, raw in enumerate(raw_evidence):
        if not isinstance(raw, Mapping):
            raise WorkflowError("deterministic_evidence entries must be objects")
        source_ref = raw.get("source_ref")
        kind = raw.get("kind")
        content = raw.get("content")
        scope = raw.get("scope")
        if not all(isinstance(item, str) and item for item in (source_ref, kind, content)):
            raise WorkflowError(
                f"deterministic_evidence[{index}] requires source_ref, kind, and content"
            )
        if scope is not None and (not isinstance(scope, str) or not scope):
            raise WorkflowError(f"deterministic_evidence[{index}].scope must be non-empty")
        item: dict[str, object] = {
            "source_ref": source_ref,
            "kind": kind,
            "content": content,
        }
        if scope is not None:
            item["scope"] = scope
        projected_evidence.append(item)
        source_refs.append(source_ref)

    state: dict[str, object] = {
        "requirement": {"text": requirement_text, "source_ref": requirement_ref},
        "candidates": projected_candidates,
        "deterministic_evidence": projected_evidence,
        "provider_authority": "evidence_only",
    }
    encoded = _canonical_json_bytes(state)
    if len(encoded) > MAX_PROJECTED_STATE_BYTES:
        raise WorkflowError(
            f"checkpoint projected state exceeds {MAX_PROJECTED_STATE_BYTES} bytes"
        )
    return state, tuple(dict.fromkeys(source_refs))


def build_checkpoint_request(
    draft_value: Mapping[str, object], context: Mapping[str, object]
) -> dict[str, Any]:
    """Build a frozen, provider-neutral Choice request from primary evidence.

    The draft's tentative selection, confidence, rationale, and other agent-authored
    judgment are deliberately excluded. Candidate artifacts are included because they
    are the objects being compared, but the selecting agent's preference is not.
    """
    draft = normalize_decision_draft(draft_value)
    state, source_refs = _normalize_context(draft, context)
    missing_refs = sorted(set(draft["evidence_refs"]) - set(source_refs))
    if missing_refs:
        raise WorkflowError(
            "checkpoint context is missing draft evidence refs: " + ", ".join(missing_refs)
        )
    candidate_ids = list(draft["candidate_ids"])
    question = {
        "primitive": "choice",
        "instructions": (
            "Using only the supplied requirement, candidate artifacts, and scoped "
            "deterministic evidence, choose the candidate_id that best satisfies the "
            "requirement. Do not infer missing verification."
        ),
        "criteria": {candidate_id: f"Candidate {candidate_id}" for candidate_id in candidate_ids},
    }
    payload = {
        "decision_id": PROPOSAL_SELECTION_DECISION_ID,
        "question_set_version": QUESTION_SET_VERSION,
        "projector_version": PROJECTOR_VERSION,
        "state": state,
        "question": question,
    }
    return {
        **payload,
        "request_sha256": _sha256(payload),
        "source_refs": list(source_refs),
    }


def _semantic_candidate(
    draft: Mapping[str, object], evidence: DecisionEvidence
) -> str | None:
    value = evidence.value
    if (
        evidence.decision_id != PROPOSAL_SELECTION_DECISION_ID
        or evidence.status != "success"
        or evidence.semantic_type != "choice"
    ):
        return None
    if not isinstance(value, str) or value not in draft["candidate_ids"]:
        return None
    return value


def _evidence_outcome(
    draft: Mapping[str, object], evidence: DecisionEvidence, policy: CheckpointPolicy
) -> CheckpointOutcome:
    candidate = _semantic_candidate(draft, evidence)
    if candidate is None:
        return "provider_failure"
    if (
        evidence.confidence is None
        or isinstance(evidence.confidence, bool)
        or not 0.0 <= float(evidence.confidence) <= 1.0
    ):
        return "provider_failure"
    if evidence.confidence < policy.minimum_confidence:
        return "uncertainty"
    distribution = {
        str(key): float(value)
        for key, value in evidence.distribution.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    if set(distribution) != set(draft["candidate_ids"]):
        return "provider_failure"
    if any(not 0.0 <= value <= 1.0 for value in distribution.values()):
        return "provider_failure"
    ranked = sorted(distribution.values(), reverse=True)
    if len(ranked) < 2:
        return "provider_failure"
    margin = ranked[0] - ranked[1]
    if margin == 0.0 or margin < policy.minimum_margin:
        return "uncertainty"
    top = max(distribution, key=distribution.get)
    if top != candidate:
        return "provider_failure"
    return "agreement" if candidate == draft["initial_agent_choice"] else "disagreement"


def _validate_resolution(
    value: Mapping[str, object],
    *,
    draft: Mapping[str, object],
    semantic_candidate: str | None,
    outcome: CheckpointOutcome,
    policy: CheckpointPolicy,
) -> dict[str, Any]:
    resolution = dict(value)
    validate_instance(resolution, DECISION_RESOLUTION_SCHEMA, artifact="decision resolution")
    if resolution.get("decision_id") != PROPOSAL_SELECTION_DECISION_ID:
        raise WorkflowError("decision resolution has wrong decision_id")
    if resolution.get("draft_id") != draft.get("draft_id"):
        raise WorkflowError("decision resolution has wrong draft_id")
    if resolution.get("initial_agent_choice") != draft.get("initial_agent_choice"):
        raise WorkflowError("decision resolution changed initial_agent_choice")
    if resolution.get("semantic_candidate") != semantic_candidate:
        raise WorkflowError("decision resolution semantic_candidate does not match evidence")

    disposition = resolution["disposition"]
    basis = resolution["basis"]
    resolved = resolution.get("resolved_choice")
    refs = resolution.get("evidence_refs", [])
    if resolved is not None and resolved not in draft["candidate_ids"]:
        raise WorkflowError("resolved_choice must name a candidate_id")

    if outcome == "agreement":
        if not (
            disposition == "retain_initial_on_agreement"
            and basis == "semantic_agreement"
            and resolved == draft["initial_agent_choice"]
        ):
            raise WorkflowError("agreement resolution must retain the initial choice")
    elif outcome == "disagreement":
        if disposition == "accept_semantic_candidate":
            if basis != "semantic_evidence" or resolved != semantic_candidate:
                raise WorkflowError("semantic acceptance must resolve to the semantic candidate")
        elif disposition == "reject_semantic_candidate":
            if basis not in {
                "deterministic_authority",
                "additional_evidence",
                "independent_review",
                "human_authority",
            }:
                raise WorkflowError("semantic rejection requires an independent reconciliation basis")
            if resolved is None:
                raise WorkflowError("semantic rejection requires a resolved_choice")
            if resolved == semantic_candidate:
                raise WorkflowError("semantic rejection cannot resolve to the semantic candidate")
            if not refs:
                raise WorkflowError("semantic rejection requires evidence_refs")
        elif disposition not in {"defer_for_evidence", "escalate_review"}:
            raise WorkflowError("disagreement requires reconciliation or escalation")
    elif outcome == "uncertainty":
        if disposition in {"defer_for_evidence", "escalate_review"}:
            pass
        elif basis in {"additional_evidence", "independent_review", "human_authority"}:
            if resolved is None or not refs:
                raise WorkflowError("uncertainty override requires resolved_choice and evidence_refs")
        else:
            raise WorkflowError("uncertainty cannot be collapsed without new authority/evidence")
    else:
        if disposition in {"defer_for_evidence", "escalate_review"}:
            pass
        elif (
            policy.provider_failure == "fallback_initial"
            and disposition == "provider_fallback"
            and basis == "provider_failure_policy"
            and resolved == draft["initial_agent_choice"]
        ):
            pass
        else:
            raise WorkflowError("provider failure is blocked by checkpoint policy")
    return resolution


def _advance_allowed(
    resolution: Mapping[str, object] | None, *, outcome: CheckpointOutcome
) -> bool:
    if resolution is None:
        return False
    if resolution.get("resolved_choice") is None:
        return False
    if resolution.get("disposition") in {"defer_for_evidence", "escalate_review"}:
        return False
    if outcome == "provider_failure" and resolution.get("disposition") != "provider_fallback":
        return False
    return True


def run_checkpoint(
    *,
    draft: Mapping[str, object],
    context: Mapping[str, object],
    provider: SemanticProvider,
    provider_name: str,
    policy: CheckpointPolicy | None = None,
    resolution: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Evaluate one proposal-selection checkpoint and return a validated receipt.

    Disagreement and uncertainty are blocking states until a valid reconciliation
    artifact is supplied. A provider failure is blocking unless the application-owned
    policy explicitly permits the initial choice as a deterministic fallback.
    """
    effective_policy = policy or CheckpointPolicy()
    if not isinstance(provider_name, str) or not provider_name.strip():
        raise WorkflowError("provider_name must be non-empty")
    normalized_draft = normalize_decision_draft(draft)
    request = build_checkpoint_request(normalized_draft, context)
    provider_started = time.perf_counter()
    try:
        evidence = provider(request)
    except Exception as exc:
        evidence = DecisionEvidence(
            PROPOSAL_SELECTION_DECISION_ID,
            "service_failure",
            "choice",
            request_sha256=request["request_sha256"],
            projector_version=PROJECTOR_VERSION,
            question_set_version=QUESTION_SET_VERSION,
            source_refs=tuple(request["source_refs"]),
            error_class=type(exc).__name__,
        )
    provider_elapsed_seconds = max(0.0, time.perf_counter() - provider_started)
    if not isinstance(evidence, DecisionEvidence):
        evidence = DecisionEvidence(
            PROPOSAL_SELECTION_DECISION_ID,
            "invalid_contract",
            "choice",
            request_sha256=request["request_sha256"],
            projector_version=PROJECTOR_VERSION,
            question_set_version=QUESTION_SET_VERSION,
            source_refs=tuple(request["source_refs"]),
            error_class="provider_return_type",
        )
    elif (
        evidence.decision_id != PROPOSAL_SELECTION_DECISION_ID
        or (evidence.request_sha256 is not None and evidence.request_sha256 != request["request_sha256"])
        or (evidence.question_set_version is not None and evidence.question_set_version != QUESTION_SET_VERSION)
        or (evidence.projector_version is not None and evidence.projector_version != PROJECTOR_VERSION)
    ):
        evidence = DecisionEvidence(
            PROPOSAL_SELECTION_DECISION_ID,
            "invalid_contract",
            "choice",
            request_sha256=request["request_sha256"],
            projector_version=PROJECTOR_VERSION,
            question_set_version=QUESTION_SET_VERSION,
            source_refs=tuple(request["source_refs"]),
            error_class="provider_evidence_identity_mismatch",
        )
    semantic_candidate = _semantic_candidate(normalized_draft, evidence)
    outcome = _evidence_outcome(normalized_draft, evidence, effective_policy)

    normalized_resolution: dict[str, Any] | None = None
    if outcome == "agreement" and resolution is None:
        normalized_resolution = {
            "schema": DECISION_RESOLUTION_SCHEMA,
            "decision_id": PROPOSAL_SELECTION_DECISION_ID,
            "draft_id": normalized_draft["draft_id"],
            "initial_agent_choice": normalized_draft["initial_agent_choice"],
            "semantic_candidate": semantic_candidate,
            "resolved_choice": normalized_draft["initial_agent_choice"],
            "disposition": "retain_initial_on_agreement",
            "basis": "semantic_agreement",
            "actor": "agent-workflow",
            "reason": "Initial agent choice and independent semantic candidate agree.",
            "evidence_refs": [],
        }
        validate_instance(
            normalized_resolution,
            DECISION_RESOLUTION_SCHEMA,
            artifact="decision resolution",
        )
    elif resolution is not None:
        normalized_resolution = _validate_resolution(
            resolution,
            draft=normalized_draft,
            semantic_candidate=semantic_candidate,
            outcome=outcome,
            policy=effective_policy,
        )

    advance_allowed = _advance_allowed(normalized_resolution, outcome=outcome)
    receipt = {
        "schema": SEMANTIC_CHECKPOINT_RECEIPT_SCHEMA,
        "decision_id": PROPOSAL_SELECTION_DECISION_ID,
        "draft_id": normalized_draft["draft_id"],
        "draft_sha256": _sha256(normalized_draft),
        "projected_state_sha256": _sha256(request["state"]),
        "request_sha256": request["request_sha256"],
        "question_set_version": QUESTION_SET_VERSION,
        "projector_version": PROJECTOR_VERSION,
        "candidate_ids": list(normalized_draft["candidate_ids"]),
        "initial_agent_choice": normalized_draft["initial_agent_choice"],
        "provider": provider_name.strip(),
        "provider_elapsed_seconds": provider_elapsed_seconds,
        "policy": {
            "minimum_confidence": float(effective_policy.minimum_confidence),
            "minimum_margin": float(effective_policy.minimum_margin),
            "provider_failure": effective_policy.provider_failure,
        },
        "semantic": {
            "status": evidence.status,
            "candidate": semantic_candidate,
            "confidence": evidence.confidence,
            "probability": evidence.probability,
            "distribution": dict(evidence.distribution),
            "model": evidence.model,
            "request_id": evidence.request_id,
            "usage": dict(evidence.usage),
            "source_refs": list(evidence.source_refs or tuple(request["source_refs"])),
            "error_class": evidence.error_class,
        },
        "outcome": outcome,
        "resolution": normalized_resolution,
        "applied_result": (
            normalized_resolution.get("resolved_choice") if advance_allowed and normalized_resolution else None
        ),
        "advance_allowed": advance_allowed,
    }
    validate_instance(
        receipt,
        SEMANTIC_CHECKPOINT_RECEIPT_SCHEMA,
        artifact="semantic checkpoint receipt",
    )
    return receipt
