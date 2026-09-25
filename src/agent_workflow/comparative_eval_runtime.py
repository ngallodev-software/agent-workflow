"""Host-owned persistence for provider-neutral comparative decision evidence."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

from .comparative_eval import require_shared_library


class EvidenceStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.execute("CREATE TABLE IF NOT EXISTS observations (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS outcomes (id TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(id, kind))")
        self.db.execute("CREATE TABLE IF NOT EXISTS provider_requests (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.db.commit()

    def observation(self, observation_id: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT payload FROM observations WHERE id=?", (observation_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def provider_request(self, request_id: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT payload FROM provider_requests WHERE id=?", (request_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def put_observation(self, record: Mapping[str, Any]) -> dict[str, Any]:
        lib = require_shared_library()
        lib.validate_observation(record)
        payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
        try:
            self.db.execute("INSERT INTO observations VALUES (?,?)", (record["observation_id"], payload))
        except sqlite3.IntegrityError:
            row = self.db.execute("SELECT payload FROM observations WHERE id=?", (record["observation_id"],)).fetchone()
            if row is None or row[0] != payload:
                raise ValueError("observation ID already contains different evidence")
        self.db.commit()
        return dict(record)

    def put_provider_request(self, record: Mapping[str, Any]) -> dict[str, Any]:
        lib = require_shared_library()
        lib.validate_record(record, lib.PROVIDER_REQUEST_SCHEMA)
        payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
        try:
            self.db.execute("INSERT INTO provider_requests VALUES (?,?)", (record["request_id"], payload))
        except sqlite3.IntegrityError:
            row = self.db.execute("SELECT payload FROM provider_requests WHERE id=?", (record["request_id"],)).fetchone()
            if row is None or row[0] != payload:
                raise ValueError("provider request ID already contains different evidence")
        self.db.commit()
        return dict(record)

    def put_outcome(self, record: Mapping[str, Any]) -> dict[str, Any]:
        payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
        try:
            self.db.execute("INSERT INTO outcomes VALUES (?,?,?)", (record["observation_id"], record["outcome_kind"], payload))
        except sqlite3.IntegrityError:
            row = self.db.execute(
                "SELECT payload FROM outcomes WHERE id=? AND kind=?",
                (record["observation_id"], record["outcome_kind"]),
            ).fetchone()
            if row is None or json.loads(row[0]).get("outcome") != dict(record.get("outcome", {})):
                raise ValueError("outcome key already contains different evidence")
        self.db.commit()
        return dict(record)

    def observations(self) -> list[dict[str, Any]]:
        return [json.loads(row[0]) for row in self.db.execute("SELECT payload FROM observations ORDER BY id")]

    def provider_requests(self) -> list[dict[str, Any]]:
        return [json.loads(row[0]) for row in self.db.execute("SELECT payload FROM provider_requests ORDER BY id")]

    def outcomes(self) -> list[dict[str, Any]]:
        return [json.loads(row[0]) for row in self.db.execute("SELECT payload FROM outcomes ORDER BY id,kind")]

    def reports(self) -> list[dict[str, Any]]:
        """Return legacy per-feature generic reports for operator inspection."""
        lib = require_shared_library()
        groups: dict[str, list[dict[str, Any]]] = {}
        for obs in self.observations():
            key = json.dumps((obs["feature_id"], obs["mode"], obs["identity"]), sort_keys=True)
            groups.setdefault(key, []).append(obs)
        outcomes = self.outcomes()
        result = []
        for items in groups.values():
            ids = {item["observation_id"] for item in items}
            result.append(lib.comparison_report(items, [item for item in outcomes if item["observation_id"] in ids]))
        return result

    def decision_study_report(
        self,
        *,
        study_id: str,
        study_version: str,
        exclusions: Sequence[Mapping[str, Any]] = (),
        cohort: Mapping[str, Any] | None = None,
        ece_minimum_n: int = 100,
    ) -> dict[str, Any]:
        lib = require_shared_library()
        return lib.build_decision_study_report(
            self.observations(),
            self.outcomes(),
            study_id=study_id,
            study_version=study_version,
            requests=self.provider_requests(),
            exclusions=exclusions,
            cohort=cohort,
            ece_minimum_n=ece_minimum_n,
        )

    def close(self) -> None:
        self.db.close()


def make_precomputed_observation(
    *,
    feature_id: str,
    identity: Mapping[str, Any],
    source_input: Mapping[str, Any],
    projected_input: Mapping[str, Any],
    control_result: Mapping[str, Any],
    candidate_result: Mapping[str, Any],
    control_duration_seconds: float | None,
    candidate_duration_seconds: float | None,
    provider_elapsed_seconds: float | None = None,
    case_id: str | None = None,
    observation_id: str | None = None,
) -> dict[str, Any]:
    """Create a generic shared observation without re-executing either decision arm."""
    lib = require_shared_library()
    record = lib.make_observation(
        feature_id=feature_id,
        mode="shadow-normal-usage",
        identity=dict(identity),
        source_input=dict(source_input),
        projected_input=dict(projected_input),
        case_id=case_id,
        data_class="production-metadata",
        observation_id=observation_id or str(uuid4()),
        control=lambda: dict(control_result),
        candidate=lambda: dict(candidate_result),
        candidate_applied=False,
        authoritative_arm="control",
    )
    if control_duration_seconds is not None:
        record["control"]["duration_seconds"] = float(control_duration_seconds)
    if candidate_duration_seconds is not None:
        record["candidate"]["duration_seconds"] = float(candidate_duration_seconds)
    if provider_elapsed_seconds is not None:
        record["candidate"]["provider_elapsed_seconds"] = float(provider_elapsed_seconds)
    lib.validate_observation(record)
    return record


def make_precomputed_decision_observation(**kwargs: Any) -> dict[str, Any]:
    lib = require_shared_library()
    return lib.make_precomputed_decision_observation(**kwargs)


def make_provider_request_record(**kwargs: Any) -> dict[str, Any]:
    lib = require_shared_library()
    return lib.make_provider_request(**kwargs)


def join_agent_run_outcome(store: EvidenceStore, observation_id: str, outcome: Mapping[str, Any]) -> dict[str, Any]:
    for current in store.outcomes():
        if current["observation_id"] == observation_id and current["outcome_kind"] == "agent-run-outcome":
            if current["outcome"] != dict(outcome):
                raise ValueError("agent-run outcome conflicts with immutable prior evidence")
            return current
    lib = require_shared_library()
    record = lib.make_outcome(observation_id, "agent-run-outcome", dict(outcome))
    return store.put_outcome(record)


ROUTING_COMPARATIVE_FEATURES = {
    "routing.task_class": "routing.task-class/v1",
    "routing.interaction_required": "routing.interaction-required/v1",
    "routing.semantic_risk": "routing.semantic-risk/v1",
}


def routing_comparison_records(
    *,
    advice: Mapping[str, Any],
    identity: Mapping[str, Any],
    source_input: Mapping[str, Any],
    projected_input: Mapping[str, Any],
    case_id: str,
    observation_scope: str,
    mode: str = "shadow-normal-usage",
    data_class: str = "production-metadata",
) -> dict[str, Any]:
    """Project one Agent-Workflow routing decision set into neutral study evidence.

    The three semantic seams share one provider request. This helper returns that
    request separately from the three decision observations so consumers cannot
    accidentally triple-count provider latency or usage.
    """
    receipts = advice.get("decision_receipts")
    if not isinstance(receipts, Mapping):
        raise ValueError("routing advice has no decision receipts")

    expected = tuple(ROUTING_COMPARATIVE_FEATURES)
    semantic_records: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
    for decision_id in expected:
        receipt = receipts.get(decision_id)
        if not isinstance(receipt, Mapping):
            raise ValueError(f"routing advice missing decision receipt: {decision_id}")
        semantic = receipt.get("semantic")
        if not isinstance(semantic, Mapping):
            raise ValueError(f"routing decision has no semantic evidence: {decision_id}")
        semantic_records.append((decision_id, receipt, semantic))

    first_semantic = semantic_records[0][2]
    request_sha256 = first_semantic.get("request_sha256")
    request_id = first_semantic.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        request_id = (
            f"typesafe:{str(request_sha256)[:32]}"
            if isinstance(request_sha256, str) and request_sha256
            else f"routing:{case_id}"
        )
    for decision_id, _, semantic in semantic_records[1:]:
        other = semantic.get("request_id")
        if not isinstance(other, str) or not other:
            other_sha = semantic.get("request_sha256")
            other = (
                f"typesafe:{str(other_sha)[:32]}"
                if isinstance(other_sha, str) and other_sha
                else request_id
            )
        if other != request_id:
            raise ValueError(
                f"batched comparative decisions do not share one provider request: {decision_id}"
            )

    timing = advice.get("decision_timing")
    timing = timing if isinstance(timing, Mapping) else {}
    provider_elapsed = timing.get("provider_elapsed_seconds")
    statuses = [
        str(semantic.get("status") or "invalid_contract")
        for _, _, semantic in semantic_records
    ]
    request_status = (
        "timeout"
        if any(status == "timeout" for status in statuses)
        else "success"
        if all(status in {"success", "no_match"} for status in statuses)
        else "error"
    )
    error_class = next(
        (
            str(semantic.get("error_class"))
            for _, _, semantic in semantic_records
            if semantic.get("error_class")
        ),
        None,
    )
    usage = first_semantic.get("usage")
    usage = dict(usage) if isinstance(usage, Mapping) else {}

    request = make_provider_request_record(
        request_id=request_id,
        identity=dict(identity),
        decisions=expected,
        status=request_status,
        duration_seconds=(
            float(provider_elapsed)
            if isinstance(provider_elapsed, (int, float))
            and not isinstance(provider_elapsed, bool)
            else None
        ),
        usage=usage,
        request_sha256=(
            str(request_sha256)
            if isinstance(request_sha256, str) and request_sha256
            else None
        ),
        error_class=error_class,
    )

    observations: list[dict[str, Any]] = []
    for decision_id, receipt, semantic in semantic_records:
        semantic_type = str(semantic.get("semantic_type") or "")
        evidence_result = receipt.get("evidence_result")
        probability = semantic.get("probability")
        if semantic_type == "noul":
            candidate_decision = (
                float(probability) >= 0.5
                if isinstance(probability, (int, float))
                and not isinstance(probability, bool)
                else None
            )
        else:
            candidate_decision = evidence_result

        control_decision = receipt.get("control_result")
        if decision_id == "routing.task_class":
            control_decision = {
                "exploratory": "diagnosis",
            }.get(str(control_decision), control_decision)

        semantic_status = str(semantic.get("status") or "invalid_contract")
        candidate_arm_status = (
            "success"
            if semantic_status in {"success", "no_match"}
            else "timeout"
            if semantic_status == "timeout"
            else "error"
        )
        key = f"{observation_scope}:{decision_id}"
        observation_id = "routing-" + hashlib.sha256(key.encode()).hexdigest()[:32]
        observations.append(
            make_precomputed_decision_observation(
                feature_id=ROUTING_COMPARATIVE_FEATURES[decision_id],
                decision_id=decision_id,
                semantic_type=semantic_type,
                identity={**dict(identity), "decision_id": decision_id},
                source_input=source_input,
                projected_input=projected_input,
                control_decision=control_decision,
                candidate_decision=candidate_decision,
                semantic_status=semantic_status,
                request_id=request_id,
                probability=(
                    float(probability)
                    if isinstance(probability, (int, float))
                    and not isinstance(probability, bool)
                    else None
                ),
                confidence=(
                    float(semantic["confidence"])
                    if isinstance(semantic.get("confidence"), (int, float))
                    and not isinstance(semantic.get("confidence"), bool)
                    else None
                ),
                probabilities=(
                    semantic.get("distribution")
                    if isinstance(semantic.get("distribution"), Mapping)
                    else {}
                ),
                policy_candidate=receipt.get("policy_candidate_result"),
                applied_result=receipt.get("applied_result"),
                fallback=(
                    receipt.get("fallback")
                    if isinstance(receipt.get("fallback"), Mapping)
                    else {}
                ),
                candidate_arm_status=candidate_arm_status,
                case_id=case_id,
                observation_id=observation_id,
                data_class=data_class,
                mode=mode,
            )
        )

    return {
        "request": request,
        "observations": observations,
        "request_id": request_id,
        "observation_ids": [item["observation_id"] for item in observations],
    }


def persist_routing_comparison(
    store: EvidenceStore, records: Mapping[str, Any]
) -> dict[str, Any]:
    request = records.get("request")
    observations = records.get("observations")
    if not isinstance(request, Mapping) or not isinstance(observations, Sequence):
        raise ValueError("invalid routing comparison record bundle")
    existing_request = store.provider_request(str(request["request_id"]))
    if existing_request is None:
        store.put_provider_request(request)
    elif existing_request != dict(request):
        raise ValueError("provider request ID already contains different evidence")
    for observation in observations:
        if not isinstance(observation, Mapping):
            raise ValueError("routing observation must be a mapping")
        existing = store.observation(str(observation["observation_id"]))
        if existing is None:
            store.put_observation(observation)
        elif existing != dict(observation):
            raise ValueError("observation ID already contains different evidence")
    return {
        "request_id": str(request["request_id"]),
        "observation_ids": [str(item["observation_id"]) for item in observations],
    }
