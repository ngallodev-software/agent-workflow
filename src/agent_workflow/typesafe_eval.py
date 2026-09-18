"""Host-side comparative evaluation primitives for advisory plugins.

This module is deliberately a projection: it records paired evidence and
reports it, but never participates in Agent-Run or workflow authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from .errors import WorkflowError

FEATURE_SCHEMA = "agent-workflow-typesafe/eval-feature/v1"
OBSERVATION_SCHEMA = "agent-workflow-typesafe/comparison-observation/v1"
OUTCOME_SCHEMA = "agent-workflow-typesafe/comparison-outcome/v1"
REPORT_SCHEMA = "agent-workflow-typesafe/comparison-report/v1"


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvalFeature:
    feature_id: str
    control: Mapping[str, Any]
    candidate: Mapping[str, Any]
    normalization: Mapping[str, Any]
    oracle: Mapping[str, Any]
    metrics: tuple[str, ...]
    capture: Mapping[str, Any]

    def as_record(self) -> dict[str, Any]:
        return {"schema": FEATURE_SCHEMA, "feature_id": self.feature_id,
                "control": dict(self.control), "candidate": dict(self.candidate),
                "normalization": dict(self.normalization), "oracle": dict(self.oracle),
                "metrics": list(self.metrics), "capture": dict(self.capture)}


class FeatureRegistry:
    """Small explicit registry; registration is not a generic hook bus."""

    def __init__(self) -> None:
        self._features: dict[str, EvalFeature] = {}

    def register(self, feature: EvalFeature | Mapping[str, Any]) -> EvalFeature:
        if not isinstance(feature, EvalFeature):
            if feature.get("schema") != FEATURE_SCHEMA:
                raise ValueError("invalid evaluation feature schema")
            metrics = feature.get("metrics")
            if not isinstance(metrics, list) or not all(isinstance(x, str) for x in metrics):
                raise ValueError("feature metrics must be a string list")
            feature = EvalFeature(str(feature["feature_id"]), feature["control"], feature["candidate"], feature["normalization"], feature["oracle"], tuple(metrics), feature["capture"])
        if not feature.feature_id.strip() or feature.feature_id in self._features:
            raise ValueError(f"invalid or duplicate feature: {feature.feature_id!r}")
        self._features[feature.feature_id] = feature
        return feature

    def get(self, feature_id: str) -> EvalFeature:
        try:
            return self._features[feature_id]
        except KeyError as exc:
            raise WorkflowError(f"unknown evaluation feature: {feature_id}") from exc

    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._features[name].as_record() for name in sorted(self._features))


def _arm(call: Callable[[], Mapping[str, Any]] | None, timeout: float | None = None) -> dict[str, Any]:
    if call is None:
        return {"status": "not_applicable", "duration_seconds": None, "result": None, "usage": {}}
    started = time.perf_counter()
    try:
        value = dict(call())
    except TimeoutError:
        return {"status": "timeout", "duration_seconds": time.perf_counter() - started, "result": None, "usage": {}}
    except Exception as exc:  # evidence must not persist exception details
        return {"status": "error", "duration_seconds": time.perf_counter() - started, "result": None, "usage": {}, "error_class": type(exc).__name__}
    duration = time.perf_counter() - started
    if timeout is not None and duration > timeout:
        return {"status": "timeout", "duration_seconds": duration, "result": None, "usage": {}}
    usage = value.get("usage", {})
    safe_usage = {str(k): v for k, v in usage.items() if v is None or isinstance(v, (int, float))} if isinstance(usage, Mapping) else {}
    result = {"status": "success", "duration_seconds": duration, "result": value, "usage": safe_usage}
    for key in ("provider_elapsed_seconds", "first_output_latency_seconds"):
        if isinstance(value.get(key), (int, float)) and value[key] >= 0:
            result[key] = float(value[key])
    return result


def make_observation(*, feature_id: str, mode: str, identity: Mapping[str, Any], source_input: Mapping[str, Any], projected_input: Mapping[str, Any], control: Callable[[], Mapping[str, Any]], candidate: Callable[[], Mapping[str, Any]] | None, case_id: str | None = None, data_class: str = "synthetic", candidate_timeout: float | None = None, observation_id: str | None = None) -> dict[str, Any]:
    if mode not in {"static", "shadow-normal-usage", "guarded-experiment"}:
        raise ValueError("invalid comparison mode")
    c = _arm(control)
    n = _arm(candidate, candidate_timeout)
    left, right = c.get("result"), n.get("result")
    return {"schema": OBSERVATION_SCHEMA, "observation_id": observation_id or str(uuid.uuid4()), "feature_id": feature_id, "mode": mode, "recorded_at": datetime.now(timezone.utc).isoformat(), "identity": dict(identity), "input": {"case_id": case_id, "input_sha256": canonical_hash(source_input), "projection_sha256": canonical_hash(projected_input), "raw_input_persisted": False}, "control": c, "candidate": n, "comparison": {"candidate_applied": False, "authoritative_arm": "control", "agreement": None if left is None or right is None else left == right, "normalized_control": left, "normalized_candidate": right}, "privacy": {"data_class": data_class, "raw_content_stored": False, "secret_values_stored": False}}


def validate_observation(observation: Mapping[str, Any]) -> None:
    if observation.get("schema") != OBSERVATION_SCHEMA or observation.get("comparison", {}).get("candidate_applied") is not False or observation.get("comparison", {}).get("authoritative_arm") != "control":
        raise ValueError("invalid or non-control-authoritative observation")
    inp, privacy = observation.get("input", {}), observation.get("privacy", {})
    for key in ("input_sha256", "projection_sha256"):
        if not isinstance(inp.get(key), str) or len(inp[key]) != 64:
            raise ValueError("invalid observation digest")
    if inp.get("raw_input_persisted") is not False or privacy.get("raw_content_stored") is not False or privacy.get("secret_values_stored") is not False:
        raise ValueError("observation violates privacy boundary")


class OutcomeJoiner:
    """Append-only outcome projection keyed by observation ID."""

    def __init__(self) -> None:
        self._outcomes: dict[tuple[str, str], dict[str, Any]] = {}

    def join(self, observation_id: str, outcome_kind: str, outcome: Mapping[str, Any]) -> dict[str, Any]:
        if outcome_kind not in {"static-oracle", "human-adjudication", "agent-run-outcome", "none"}:
            raise ValueError("invalid outcome kind")
        key = (observation_id, outcome_kind)
        existing = self._outcomes.get(key)
        if existing is not None:
            if existing["outcome"] != dict(outcome):
                raise WorkflowError("outcome join conflicts with immutable prior outcome")
            return dict(existing)
        record = {"schema": OUTCOME_SCHEMA, "observation_id": observation_id, "joined_at": datetime.now(timezone.utc).isoformat(), "outcome_kind": outcome_kind, "outcome": dict(outcome)}
        self._outcomes[key] = record
        return dict(record)

    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(self._outcomes[key]) for key in sorted(self._outcomes))


def _quantile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low, high = math.floor(pos), math.ceil(pos)
    return ordered[low] if low == high else ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def comparison_report(observations: Sequence[Mapping[str, Any]], outcomes: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    if not observations:
        raise ValueError("at least one observation is required")
    for item in observations:
        validate_observation(item)
    feature = observations[0]["feature_id"]
    cohort = observations[0]["identity"]
    if any(item["feature_id"] != feature or item["mode"] != observations[0]["mode"] or item["identity"] != cohort for item in observations):
        raise WorkflowError("comparison report cannot mix feature, mode, or cohort identities")
    correct = {"control_only": 0, "candidate_only": 0, "both_correct": 0, "both_wrong": 0}
    eligible = 0
    for item in observations:
        oracle = next((o["outcome"].get("oracle") for o in outcomes if o.get("observation_id") == item["observation_id"] and o.get("outcome_kind") == "static-oracle"), None)
        if oracle is None:
            continue
        eligible += 1
        control_ok = item["control"].get("result") == oracle
        candidate_ok = item["candidate"].get("result") == oracle
        key = "both_correct" if control_ok and candidate_ok else "both_wrong" if not control_ok and not candidate_ok else "control_only" if control_ok else "candidate_only"
        correct[key] += 1
    durations = {"control": [x["control"]["duration_seconds"] for x in observations if isinstance(x["control"].get("duration_seconds"), (int, float))], "candidate": [x["candidate"]["duration_seconds"] for x in observations if isinstance(x["candidate"].get("duration_seconds"), (int, float))]}
    return {"schema": REPORT_SCHEMA, "feature_id": feature, "cohort": dict(cohort), "counts": {"observations": len(observations), "oracle_eligible": eligible, "control_success": sum(x["control"].get("status") == "success" for x in observations), "candidate_success": sum(x["candidate"].get("status") == "success" for x in observations)}, "correctness": correct, "efficiency": {arm: {"n": len(vals), "p50": _quantile(vals, .5), "p90": _quantile(vals, .9) if len(vals) >= 20 else None, "p95": _quantile(vals, .95) if len(vals) >= 40 else None} for arm, vals in durations.items()}, "reliability": {"candidate_timeouts": sum(x["candidate"].get("status") == "timeout" for x in observations), "candidate_errors": sum(x["candidate"].get("status") == "error" for x in observations)}, "calibration": {"eligible": False, "reason": "probability evidence unavailable"}, "downstream": {"outcome_ids": [x["observation_id"] for x in outcomes if x.get("observation_id") in {o["observation_id"] for o in observations}]}, "limitations": ["shadow evidence is descriptive and does not establish causality", "quality counts require an independent oracle"]}
