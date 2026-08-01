from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..errors import WorkflowError
from ..process import EnvironmentPolicy, run
from ..util import atomic_write_json, sha256_file, utc_now
from .common import format_argv, read_object
from .contracts import BENCHMARK_MACHINE_SCORE_SCHEMA, validate_spec, validate_value
from .events import append_event
from .pairing import selected_arms


def _guardrail(id_: str, state: str, detail: str, *, required: bool) -> dict[str, Any]:
    return {"id": id_, "state": state, "required": required, "detail": detail}


def _core_guardrails(
    plan: Mapping[str, Any],
    pair: Mapping[str, Any],
    pair_state: Mapping[str, Any],
    arm_value: Mapping[str, Any],
    capture: Mapping[str, Any] | None,
    spec: Mapping[str, Any],
) -> list[dict[str, Any]]:
    required = set(str(item) for item in spec["eligibility"]["required_guardrails"])
    values: list[dict[str, Any]] = []
    values.append(
        _guardrail(
            "paired_identity",
            "pass" if arm_value["task_prompt_sha256"] == pair["task_prompt_sha256"] else "fail",
            "canonical task, fixture, base revision, and environment are pair-bound",
            required="paired_identity" in required,
        )
    )
    wrapper_other = pair["arms"]["workflow_full" if arm_value["arm"] == "control_raw" else "control_raw"]["arm_wrapper_sha256"]
    values.append(
        _guardrail(
            "declared_treatment",
            "pass" if arm_value["arm_wrapper_sha256"] != wrapper_other else "fail",
            "arm wrappers must differ while canonical task digest remains equal",
            required="declared_treatment" in required,
        )
    )
    skew = float(pair_state["pair_start_skew_seconds"])
    limit = float(plan["policies"]["max_start_skew_seconds"])
    values.append(
        _guardrail(
            "start_skew",
            "pass" if skew <= limit else "fail",
            f"observed {skew:.6f}s; limit {limit:.6f}s",
            required="start_skew" in required,
        )
    )
    violations = list(arm_value.get("scope_violations", []))
    values.append(
        _guardrail(
            "writable_scope",
            "pass" if not violations else "fail",
            "no out-of-scope writes" if not violations else f"out-of-scope paths: {violations}",
            required="writable_scope" in required,
        )
    )
    sandbox = plan["executor"]["sandbox"]
    isolation_state = "pass" if sandbox.get("verified_isolation") else "not_verified"
    values.append(
        _guardrail(
            "sandbox_isolation",
            isolation_state,
            f"adapter={sandbox.get('adapter')}; verified={bool(sandbox.get('verified_isolation'))}",
            required="sandbox_isolation" in required,
        )
    )
    expected_assistance = "none" if plan["policies"].get("human_assistance") == "unassisted" else "declared"
    values.append(
        _guardrail(
            "assistance_cohort",
            "pass" if arm_value.get("assistance") == expected_assistance else "fail",
            f"cohort={plan['policies'].get('human_assistance')}; assistance={arm_value.get('assistance')}",
            required="assistance_cohort" in required,
        )
    )
    visual_state = capture.get("state") if isinstance(capture, Mapping) else None
    runtime_state = capture.get("runtime_state") if isinstance(capture, Mapping) else None
    visual_ok = visual_state == "complete" and runtime_state in {"development-verified", "publication-verified"}
    if plan["claim_level"] == "publication":
        visual_ok = visual_ok and runtime_state == "publication-verified"
    values.append(
        _guardrail(
            "visual_capture",
            "pass" if visual_ok else "fail",
            f"visual capture state={visual_state or 'missing'}; runtime_state={runtime_state or 'missing'}",
            required="visual_capture" in required,
        )
    )
    usage = arm_value.get("usage", {})
    usage_state = "pass" if usage.get("complete") is True else "not_verified"
    values.append(
        _guardrail(
            "provider_usage",
            usage_state,
            f"usage complete={usage.get('complete') is True}",
            required="provider_usage" in required,
        )
    )
    task_state = arm_value.get("state")
    values.append(
        _guardrail(
            "harness_integrity",
            "fail" if task_state == "infrastructure_failed" else "pass",
            f"arm terminal state={task_state}",
            required="harness_integrity" in required,
        )
    )
    return values


def _run_scorer(
    plan: Mapping[str, Any],
    pair: Mapping[str, Any],
    arm: Mapping[str, Any],
    scorer: Mapping[str, Any],
) -> dict[str, Any]:
    stage = Path(arm["stage_dir"])
    scores_dir = stage / "scores"
    scores_dir.mkdir(parents=True, exist_ok=True)
    result_path = scores_dir / f"{scorer['id']}.json"
    suite = Path(plan["coordinator"]["suite_dir"])
    values = {
        "run_id": str(plan["run_id"]),
        "pair_id": str(pair["pair_id"]),
        "case_id": str(pair["case_id"]),
        "arm": str(arm["arm"]),
        "worktree": str(arm["worktree"]),
        "stage_dir": str(stage),
        "scores_dir": str(scores_dir),
        "result_file": str(result_path),
        "suite": str(suite),
        "max_points": str(scorer["max_points"]),
        "dimension": str(scorer["dimension"]),
        "scorer_id": str(scorer["id"]),
    }
    argv = format_argv(scorer["argv"], values)
    process = run(
        argv,
        cwd=Path(arm["worktree"]),
        check=False,
        timeout_seconds=float(scorer["timeout_seconds"]),
        max_stdout_bytes=4 * 1024 * 1024,
        max_stderr_bytes=4 * 1024 * 1024,
        environment=EnvironmentPolicy(
            allowlist=tuple(plan["executor"].get("environment_allowlist", [])),
            values={
                "AGENT_WORKFLOW_BENCHMARK_SCORER": str(scorer["id"]),
                "AGENT_WORKFLOW_BENCHMARK_RESULT_FILE": str(result_path),
            },
            unsafe_inherit=bool(plan["executor"].get("unsafe_inherit_environment", False)),
        ),
        digest_executable=True,
    )
    (scores_dir / f"{scorer['id']}.stdout.log").write_text(str(process.stdout), encoding="utf-8")
    (scores_dir / f"{scorer['id']}.stderr.log").write_text(str(process.stderr), encoding="utf-8")
    if not result_path.is_file():
        return {
            "id": scorer["id"],
            "dimension": scorer["dimension"],
            "max_points": scorer["max_points"],
            "earned_points": 0.0,
            "state": "harness_failure",
            "details": [f"scorer produced no result file; returncode={process.returncode}"],
            "result_sha256": None,
            "duration_seconds": process.duration_seconds,
        }
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid scorer result {result_path}: {exc}") from exc
    if not isinstance(result, dict):
        raise WorkflowError(f"scorer result must be an object: {result_path}")
    earned = result.get("earned_points")
    if isinstance(earned, bool) or not isinstance(earned, (int, float)):
        raise WorkflowError(f"scorer {scorer['id']} did not provide numeric earned_points")
    maximum = float(scorer["max_points"])
    if earned < 0 or earned > maximum:
        raise WorkflowError(f"scorer {scorer['id']} points {earned} exceed 0..{maximum}")
    return {
        "id": scorer["id"],
        "dimension": scorer["dimension"],
        "max_points": maximum,
        "earned_points": round(float(earned), 4),
        "state": str(result.get("state", "pass" if earned == maximum else "partial")),
        "details": [str(item) for item in result.get("details", [])],
        "checks": result.get("checks", []),
        "result_sha256": sha256_file(result_path),
        "duration_seconds": process.duration_seconds,
    }


def score_run(plan_path: Path) -> dict[str, Any]:
    plan = read_object(plan_path.resolve())
    run_dir = Path(plan["coordinator"]["run_dir"])
    summary_path = run_dir / "machine-scores.json"
    if summary_path.is_file():
        return read_object(summary_path)
    spec = validate_spec(Path(plan["coordinator"]["spec_path"]))
    append_event(run_dir, event_type="machine_scoring_started", run_id=str(plan["run_id"]))
    scored: list[dict[str, Any]] = []
    for pair in plan["pairs"]:
        pair_state_path = run_dir / "pair-state" / str(pair["case_id"]) / f"r{int(pair['repetition']):02d}" / "pair.json"
        if not pair_state_path.is_file():
            raise WorkflowError(f"pair execution evidence missing: {pair_state_path}")
        pair_state = read_object(pair_state_path)
        arms = selected_arms(pair, pair_state)
        selected_pair = {**pair, "arms": arms}
        for arm_name in ("control_raw", "workflow_full"):
            arm = arms[arm_name]
            stage = Path(arm["stage_dir"])
            arm_value = read_object(stage / "arm.json")
            capture_path = stage / "visual" / "capture.json"
            capture = read_object(capture_path) if capture_path.is_file() else None
            guardrails = _core_guardrails(plan, selected_pair, pair_state, arm_value, capture, spec)
            components = [_run_scorer(plan, pair, arm, item) for item in spec["machine_scoring"]["scorers"]]
            required_failures = [
                item["id"]
                for item in guardrails
                if item["required"] and item["state"] != "pass"
            ]
            scorer_harness_failures = [item["id"] for item in components if item["state"] == "harness_failure"]
            eligible = not required_failures and not scorer_harness_failures
            score = round(sum(float(item["earned_points"]) for item in components), 4) if eligible else None
            value = {
                "schema": BENCHMARK_MACHINE_SCORE_SCHEMA,
                "run_id": plan["run_id"],
                "benchmark_id": plan["benchmark_id"],
                "pair_id": pair["pair_id"],
                "case_id": pair["case_id"],
                "repetition": pair["repetition"],
                "arm": arm_name,
                "eligibility": {
                    "state": "eligible" if eligible else "invalid",
                    "required_failures": required_failures,
                    "scorer_harness_failures": scorer_harness_failures,
                    "guardrails": guardrails,
                    "publication_eligible": eligible
                    and bool(plan["executor"]["sandbox"].get("verified_isolation"))
                    and isinstance(capture, Mapping)
                    and capture.get("runtime_state") == "publication-verified",
                },
                "machine_score": score,
                "maximum_score": 100.0,
                "components": components,
                "verification_wall_seconds": round(
                    sum(float(item["duration_seconds"]) for item in components), 6
                ),
                "scored_at": utc_now(),
            }
            validate_value(value, BENCHMARK_MACHINE_SCORE_SCHEMA, f"machine score {pair['pair_id']} {arm_name}")
            atomic_write_json(stage / "score.json", value)
            scored.append(value)
    summary = {
        "schema": "agent-workflow/benchmark-machine-score-set/v1",
        "run_id": plan["run_id"],
        "scores": scored,
        "eligible": sum(1 for item in scored if item["eligibility"]["state"] == "eligible"),
        "invalid": sum(1 for item in scored if item["eligibility"]["state"] != "eligible"),
    }
    atomic_write_json(run_dir / "machine-scores.json", summary)
    append_event(
        run_dir,
        event_type="machine_scoring_terminal",
        run_id=str(plan["run_id"]),
        payload={"eligible": summary["eligible"], "invalid": summary["invalid"]},
    )
    return summary
