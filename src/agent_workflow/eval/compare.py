from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..errors import WorkflowError

COHORT_KEYS = (
    "fixture_revision",
    "task_id",
    "base_revision",
    "prompt_sha256",
    "oracle_sha256",
    "acceptance_commands_sha256",
    "scope_policy_sha256",
    "scorer_versions_sha256",
    "sandbox",
    "budget_sha256",
    "repetition",
)


@dataclass(frozen=True)
class ComparisonPolicy:
    confidence: float = 0.95
    minimum_n: int = 10
    effect_threshold: float = 0.0
    allow_unpaired: bool = False
    primary_metric: str = "pass_rate"
    stop_rule: str = "fixed_n"


def _key(trial: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(trial.get(name) for name in COHORT_KEYS)


def _z_value(confidence: float) -> float:
    if confidence == 0.95:
        return 1.959963984540054
    try:
        from scipy.stats import norm
    except ImportError as exc:
        raise WorkflowError(
            "non-default confidence levels require the stats extra"
        ) from exc
    return float(norm.ppf(0.5 + confidence / 2))


def _wilson(
    successes: int, count: int, confidence: float
) -> list[float] | None:
    if not count:
        return None
    z = _z_value(confidence)
    proportion = successes / count
    denominator = 1 + z * z / count
    center = (proportion + z * z / (2 * count)) / denominator
    margin = z * math.sqrt(
        proportion * (1 - proportion) / count + z * z / (4 * count * count)
    ) / denominator
    return [round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6)]


def _bootstrap_interval(
    values: Sequence[float], seed: int, confidence: float
) -> list[float] | None:
    if len(values) < 10:
        return None
    try:
        import numpy as np
        from scipy.stats import bootstrap
    except ImportError as exc:
        raise WorkflowError(
            "paired confidence intervals require the stats extra: "
            "pip install 'agent-workflow[stats]'"
        ) from exc
    result = bootstrap(
        (np.asarray(values),),
        np.mean,
        confidence_level=confidence,
        n_resamples=9999,
        random_state=np.random.default_rng(seed),
        method="percentile",
    )
    return [
        round(float(result.confidence_interval.low), 6),
        round(float(result.confidence_interval.high), 6),
    ]


def compare_trials(
    baseline: Sequence[Mapping[str, Any]],
    candidate: Sequence[Mapping[str, Any]],
    *,
    policy: ComparisonPolicy = ComparisonPolicy(),
) -> dict[str, Any]:
    left = {_key(item): item for item in baseline}
    right = {_key(item): item for item in candidate}
    if len(left) != len(baseline) or len(right) != len(candidate):
        raise WorkflowError("duplicate trial cohort key")
    unmatched = sorted(str(item) for item in set(left) ^ set(right))
    paired = sorted(set(left) & set(right), key=str)
    if unmatched and not policy.allow_unpaired:
        raise WorkflowError(f"trial cohorts do not match: {unmatched[:10]}")
    differences = [
        float(right[key].get("verdict") == "pass")
        - float(left[key].get("verdict") == "pass")
        for key in paired
    ]
    cohort_payload = json.dumps(paired, sort_keys=True, default=str).encode()
    cohort_hash = hashlib.sha256(cohort_payload).hexdigest()
    seed = int(cohort_hash[:16], 16)
    baseline_passes = sum(left[key].get("verdict") == "pass" for key in paired)
    candidate_passes = sum(right[key].get("verdict") == "pass" for key in paired)
    interval = (
        _bootstrap_interval(differences, seed, policy.confidence)
        if len(paired) >= policy.minimum_n
        else None
    )
    effect = sum(differences) / len(differences) if differences else 0.0
    winner = None
    if interval is not None and not unmatched and policy.primary_metric == "pass_rate":
        if interval[0] > policy.effect_threshold:
            winner = "candidate"
        elif interval[1] < -policy.effect_threshold:
            winner = "baseline"
    efficiency: dict[str, Any] = {}
    exclusions: dict[str, int] = {}
    for metric in ("duration_seconds", "tokens", "cost"):
        values: list[float] = []
        excluded = 0
        for key in paired:
            before = left[key].get(metric)
            after = right[key].get(metric)
            if not isinstance(before, (int, float)) or not isinstance(
                after, (int, float)
            ):
                excluded += 1
                continue
            values.append(float(after) - float(before))
        exclusions[metric] = excluded
        efficiency[metric] = {
            "n": len(values),
            "mean_difference": sum(values) / len(values) if values else None,
            "paired_bootstrap": (
                _bootstrap_interval(
                    values,
                    seed ^ int(hashlib.sha256(metric.encode()).hexdigest()[:8], 16),
                    policy.confidence,
                )
                if len(values) >= policy.minimum_n
                else None
            ),
        }
    return {
        "schema": "agent-workflow/comparison/v1",
        "paired": not unmatched,
        "descriptive_only": bool(unmatched),
        "cohort_sha256": cohort_hash,
        "paired_n": len(paired),
        "unmatched": unmatched,
        "baseline": {
            "passes": baseline_passes,
            "rate": baseline_passes / len(paired) if paired else None,
            "wilson": _wilson(
                baseline_passes, len(paired), policy.confidence
            ),
        },
        "candidate": {
            "passes": candidate_passes,
            "rate": candidate_passes / len(paired) if paired else None,
            "wilson": _wilson(
                candidate_passes, len(paired), policy.confidence
            ),
        },
        "pass_rate_difference": effect,
        "paired_bootstrap_95": interval,
        "winner": winner,
        "confidence": policy.confidence,
        "primary_metric": policy.primary_metric,
        "effect_threshold": policy.effect_threshold,
        "stop_rule": policy.stop_rule,
        "efficiency": efficiency,
        "efficiency_exclusions": exclusions,
        "tail_metrics_eligible": {"p90": len(paired) >= 20, "p95": len(paired) >= 40},
    }
