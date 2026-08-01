from __future__ import annotations

from pathlib import Path
import shutil
import time
from typing import Any

from ..assets import asset_path, copy_asset_tree
from ..config import Settings
from ..errors import WorkflowError
from ..process import EnvironmentPolicy, run as run_process
from ..util import atomic_write_json, utc_now
from .common import read_object, write_manifest
from .auth import preflight_authentication
from .policy import apply_operating_policy, implicit_operating_policy, load_operating_policy
from .pairing import attempts_for
from .runtime import attest_runtime, seal_runtime_lock, validate_runtime_lock
from .consolidation import consolidate_run, verify_consolidated_run
from .contracts import validate_executor_config, validate_spec
from .planning import create_run_plan, materialize_fixture
from .reporting import write_report
from .review import prepare_assignment, submit_review
from .runner import execute_run
from .scoring import score_run
from .visual import capture_run


def _resolve_plan(settings: Settings, value: str | Path) -> Path:
    candidate = Path(value).expanduser()
    if candidate.exists():
        if candidate.is_dir():
            candidate = candidate / "run-plan.json"
        return candidate.resolve()
    run_id = str(value)
    candidate = settings.worktree_root / "benchmarks" / run_id / "coordinator" / "benchmarks" / "runs" / run_id / "run-plan.json"
    if candidate.is_file():
        return candidate.resolve()
    raise WorkflowError(f"benchmark run not found: {value}")


def validate_benchmark(spec: Path, executor: Path | None = None) -> dict[str, Any]:
    value = validate_spec(spec)
    result = {
        "benchmark_id": value["benchmark_id"],
        "version": value["version"],
        "cases": [item["id"] for item in value["cases"]],
        "phases": [item["id"] for item in value["phases"]],
        "machine_points": sum(item["max_points"] for item in value["machine_scoring"]["scorers"]),
        "arms": sorted(value["arms"]),
    }
    if executor is not None:
        configured = validate_executor_config(executor)
        result["executor"] = {
            "provider": configured["provider"],
            "executor": configured["executor"],
            "version": configured["executor_version"],
            "model": configured["model"],
            "authentication_mode": configured["authentication"]["mode"],
            "billing_mode": configured["billing"]["mode"],
        }
    return result


def export_builtin_suite(
    destination: Path,
    *,
    benchmark_id: str = "priority-picker-v1",
    force: bool = False,
) -> dict[str, Any]:
    if benchmark_id != "priority-picker-v1":
        raise WorkflowError(f"unknown built-in benchmark suite: {benchmark_id}")
    source = asset_path(f"benchmarks/{benchmark_id}")
    if not source.is_dir():
        raise WorkflowError(f"built-in benchmark suite is unavailable: {benchmark_id}")
    destination = destination.expanduser().resolve()
    if destination.exists():
        if not force:
            raise WorkflowError(f"benchmark suite destination already exists: {destination}")
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    copy_asset_tree(f"benchmarks/{benchmark_id}", destination)
    spec = destination / "benchmark-spec.json"
    synthetic = destination / "executors" / "synthetic.json"
    validate_spec(spec)
    validate_executor_config(synthetic)
    executors = sorted(str(path) for path in (destination / "executors").glob("*.json"))
    return {
        "benchmark_id": benchmark_id,
        "destination": str(destination),
        "spec": str(spec),
        "synthetic_executor": str(synthetic),
        "executors": executors,
        "default_authentication": "subscription-session",
        "optional_authentication": ["api-key", "access-token"],
        "operating_policies": sorted(str(path) for path in (destination / "policies").glob("*.json")),
        "default_subscription_executors": [
            str(destination / "executors" / "codex-subscription.json"),
            str(destination / "executors" / "claude-subscription.json"),
        ],
    }


def create_fixture(spec: Path, destination: Path, *, force: bool = False) -> dict[str, Any]:
    return materialize_fixture(spec, destination, force=force)


def create_plan(
    settings: Settings,
    *,
    spec: Path,
    executor: Path,
    repo: Path,
    base_ref: str,
    run_id: str | None,
    repetitions: int | None,
    worktree_root: Path | None,
    allow_dirty: bool,
    assistance_cohort: str | None = None,
    policy: Path | None = None,
    runtime_lock: Path | None = None,
) -> dict[str, Any]:
    return create_run_plan(
        settings,
        spec_path=spec,
        executor_path=executor,
        repo=repo,
        base_ref=base_ref,
        run_id=run_id,
        repetitions=repetitions,
        worktree_root=worktree_root,
        allow_dirty=allow_dirty,
        assistance_cohort=assistance_cohort,
        policy_path=policy,
        runtime_lock_path=runtime_lock,
    )


def _finalize_automated(settings: Settings, plan: Path) -> dict[str, Any]:
    del settings  # The resolved run plan owns all execution paths and policies.
    plan_value = read_object(plan)
    run_dir = Path(plan_value["coordinator"]["run_dir"])
    pipeline_started = time.monotonic()

    def timed(field: str, operation: Any) -> Any:
        started = time.monotonic()
        result = operation(plan)
        state_value = read_object(run_dir / "run.json")
        state_value[field] = round(time.monotonic() - started, 6)
        state_value["updated_at"] = utc_now()
        atomic_write_json(run_dir / "run.json", state_value)
        return result

    timed("execution_stage_wall_seconds", execute_run)
    timed("visual_capture_stage_wall_seconds", capture_run)
    timed("machine_scoring_stage_wall_seconds", score_run)
    consolidated = timed("consolidation_stage_wall_seconds", consolidate_run)
    report_started = time.monotonic()
    report = write_report(plan)
    report_wall = round(time.monotonic() - report_started, 6)
    state = read_object(run_dir / "run.json")
    state.update(
        state="awaiting_human_review"
        if report["state"] == "awaiting_human_review"
        else "completed",
        updated_at=utc_now(),
        automated_pipeline_completed_at=utc_now(),
        reporting_stage_wall_seconds=report_wall,
        automated_pipeline_wall_seconds=round(time.monotonic() - pipeline_started, 6),
    )
    atomic_write_json(run_dir / "run.json", state)
    # Regenerate after terminal stage timings are durable so the report exposes
    # end-to-end wall time rather than only the pre-report snapshot.
    report = write_report(plan)
    write_manifest(run_dir)
    return {
        "run_id": plan_value["run_id"],
        "state": state["state"],
        "run_dir": str(run_dir),
        "report": str(run_dir / "report.json"),
        "markdown": str(run_dir / "report.md"),
        "consolidation": consolidated,
        "automated_pipeline_wall_seconds": state["automated_pipeline_wall_seconds"],
    }


def _existing_automated_result(plan_path: Path) -> dict[str, Any] | None:
    plan = read_object(plan_path)
    run_dir = Path(plan["coordinator"]["run_dir"])
    required = (
        run_dir / "visual-capture-summary.json",
        run_dir / "machine-scores.json",
        run_dir / "consolidation-receipt.json",
        run_dir / "report.json",
        run_dir / "report.md",
    )
    if not all(path.is_file() for path in required):
        return None
    verification = verify_consolidated_run(run_dir)
    if not verification["valid"]:
        return None
    state = read_object(run_dir / "run.json")
    return {
        "run_id": plan["run_id"],
        "state": state["state"],
        "run_dir": str(run_dir),
        "report": str(run_dir / "report.json"),
        "markdown": str(run_dir / "report.md"),
        "consolidation": {
            "receipt": str(run_dir / "consolidation-receipt.json"),
            "manifest": str(run_dir / "MANIFEST.sha256"),
            "existing": True,
        },
        "automated_pipeline_wall_seconds": state.get("automated_pipeline_wall_seconds"),
        "existing": True,
    }


def run_benchmark(settings: Settings, run: str | Path) -> dict[str, Any]:
    plan = _resolve_plan(settings, run)
    return _existing_automated_result(plan) or _finalize_automated(settings, plan)


def resume_benchmark(settings: Settings, run: str | Path) -> dict[str, Any]:
    plan = _resolve_plan(settings, run)
    return _existing_automated_result(plan) or _finalize_automated(settings, plan)


def visual_capture_benchmark(settings: Settings, run: str | Path) -> dict[str, Any]:
    return capture_run(_resolve_plan(settings, run))


def score_benchmark(settings: Settings, run: str | Path) -> dict[str, Any]:
    return score_run(_resolve_plan(settings, run))


def consolidate_benchmark(settings: Settings, run: str | Path) -> dict[str, Any]:
    return consolidate_run(_resolve_plan(settings, run))


def prepare_or_submit_review(
    settings: Settings,
    run: str | Path,
    *,
    reviewer: str,
    input_path: Path | None,
) -> dict[str, Any]:
    plan = _resolve_plan(settings, run)
    result = submit_review(plan, reviewer, input_path) if input_path else prepare_assignment(plan, reviewer)
    if input_path:
        report = write_report(plan)
        plan_value = read_object(plan)
        run_dir = Path(plan_value["coordinator"]["run_dir"])
        state = read_object(run_dir / "run.json")
        state.update(
            state="completed" if report["state"] not in {"awaiting_human_review", "descriptive_only"} else "awaiting_human_review",
            updated_at=utc_now(),
        )
        atomic_write_json(run_dir / "run.json", state)
        write_manifest(run_dir)
        result["report_state"] = report["state"]
    return result


def render_benchmark_report(settings: Settings, run: str | Path) -> dict[str, Any]:
    return write_report(_resolve_plan(settings, run))


def verify_benchmark(settings: Settings, run: str | Path) -> dict[str, Any]:
    plan = read_object(_resolve_plan(settings, run))
    return verify_consolidated_run(Path(plan["coordinator"]["run_dir"]))



def cleanup_benchmark(settings: Settings, run: str | Path) -> dict[str, Any]:
    plan_path = _resolve_plan(settings, run)
    plan = read_object(plan_path)
    run_dir = Path(plan["coordinator"]["run_dir"])
    verification = verify_consolidated_run(run_dir)
    if not verification["valid"]:
        raise WorkflowError("benchmark evidence must verify before arm worktrees are removed")
    repository = Path(plan["source"]["repository"])
    removed: list[dict[str, Any]] = []
    for pair in plan["pairs"]:
        for attempt in attempts_for(pair):
            for arm_name in ("control_raw", "workflow_full"):
                arm = attempt["arms"][arm_name]
                worktree = Path(arm["worktree"])
                result = run_process(
                    ["git", "-C", str(repository), "worktree", "remove", "--force", str(worktree)],
                    check=False,
                    environment=EnvironmentPolicy(unsafe_inherit=True, git_config_policy="operator"),
                )
                if result.returncode not in {0, 128}:
                    raise WorkflowError(str(result.stderr).strip() or f"failed to remove benchmark worktree {worktree}")
                branch_result = run_process(
                    ["git", "-C", str(repository), "branch", "-D", str(arm["branch"])],
                    check=False,
                    environment=EnvironmentPolicy(unsafe_inherit=True, git_config_policy="operator"),
                )
                removed.append({
                    "pair_id": pair["pair_id"], "attempt": attempt["attempt"], "arm": arm_name,
                    "worktree": str(worktree), "worktree_removed": not worktree.exists(),
                    "branch": arm["branch"], "branch_delete_returncode": branch_result.returncode,
                })
    cleanup_value = {
        "schema": "agent-workflow/benchmark-cleanup/v1", "run_id": plan["run_id"],
        "completed_at": utc_now(), "verification": verification, "removed": removed,
        "coordinator_preserved": plan["coordinator"]["worktree"],
    }
    atomic_write_json(run_dir / "cleanup.json", cleanup_value)
    write_manifest(run_dir)
    return cleanup_value



def benchmark_readiness(
    spec: Path,
    executor: Path,
    *,
    policy: Path | None = None,
    runtime_lock: Path | None = None,
) -> dict[str, Any]:
    """Evaluate whether a benchmark profile can be planned without creating worktrees."""
    base_spec = validate_spec(spec)
    configured = validate_executor_config(executor)
    operating_policy = (
        load_operating_policy(policy)
        if policy is not None
        else implicit_operating_policy(base_spec)
    )
    effective_spec = apply_operating_policy(
        base_spec,
        operating_policy,
        authentication_mode=str(configured["authentication"]["mode"]),
    )
    lock_path = (
        runtime_lock.expanduser().resolve()
        if runtime_lock is not None
        else (spec.expanduser().resolve().parent / str(base_spec["visual"]["runtime_lock_path"])).resolve()
    )
    checks: list[dict[str, Any]] = []
    authentication = preflight_authentication(configured)
    checks.append({
        "id": "authentication",
        "passed": bool(authentication["authenticated"]),
        "detail": authentication["detail"],
    })
    try:
        lock_value = read_object(lock_path)
        validate_runtime_lock(lock_value, claim_level=str(effective_spec["claim_level"]))
        runtime = attest_runtime(lock_path, claim_level=str(effective_spec["claim_level"]))
        required_state = (
            "publication-verified"
            if effective_spec["claim_level"] == "publication"
            else "development-verified"
        )
        runtime_passed = runtime["runtime_state"] in (
            {"publication-verified"}
            if required_state == "publication-verified"
            else {"development-verified", "publication-verified"}
        )
        checks.append({
            "id": "visual-runtime",
            "passed": runtime_passed,
            "detail": f"required={required_state}; observed={runtime['runtime_state']}",
        })
    except WorkflowError as exc:
        runtime = {"runtime_state": "not-verified", "detail": str(exc)}
        checks.append({"id": "visual-runtime", "passed": False, "detail": str(exc)})
    checks.extend([
        {
            "id": "paired-repetitions",
            "passed": int(operating_policy["repetitions"]) >= int(operating_policy["winner_policy"]["minimum_eligible_pairs"])
            if operating_policy["winner_policy"]["enabled"]
            else True,
            "detail": (
                f"repetitions={operating_policy['repetitions']}; "
                f"minimum={operating_policy['winner_policy']['minimum_eligible_pairs']}"
            ),
        },
        {
            "id": "subscription-default",
            "passed": operating_policy["authentication_default"] == "subscription-session",
            "detail": f"default={operating_policy['authentication_default']}; selected={configured['authentication']['mode']}",
        },
        {
            "id": "retry-isolation",
            "passed": bool(operating_policy["retry_policy"]["fresh_pair_worktrees"]),
            "detail": (
                f"retries={operating_policy['infrastructure_retries']}; "
                f"classification={operating_policy['retry_policy']['classification']}"
            ),
        },
    ])
    return {
        "benchmark_id": effective_spec["benchmark_id"],
        "claim_level": effective_spec["claim_level"],
        "policy_id": operating_policy["policy_id"],
        "executor": {
            "provider": configured["provider"],
            "executor": configured["executor"],
            "model": configured["model"],
            "authentication_mode": configured["authentication"]["mode"],
            "billing_mode": configured["billing"]["mode"],
        },
        "authentication": authentication,
        "runtime": runtime,
        "checks": checks,
        "ready": all(item["passed"] for item in checks),
    }

def check_benchmark_auth(executor: Path) -> dict[str, Any]:
    configured = validate_executor_config(executor)
    return preflight_authentication(configured)


def attest_benchmark_runtime(runtime_lock: Path, *, claim_level: str = "development") -> dict[str, Any]:
    return attest_runtime(runtime_lock, claim_level=claim_level)


def seal_benchmark_runtime(base_lock: Path, output: Path, *, container_image: str) -> dict[str, Any]:
    return seal_runtime_lock(base_lock, output, container_image=container_image)


def status_benchmark(settings: Settings, run: str | Path) -> dict[str, Any]:
    plan = read_object(_resolve_plan(settings, run))
    run_dir = Path(plan["coordinator"]["run_dir"])
    state = read_object(run_dir / "run.json")
    reviews = list((run_dir / "human-review" / "reviews").glob("*.json")) if (run_dir / "human-review" / "reviews").is_dir() else []
    return {
        **state,
        "run_dir": str(run_dir),
        "run_plan": str(run_dir / "run-plan.json"),
        "visual_capture": (run_dir / "visual-capture-summary.json").is_file(),
        "machine_scores": (run_dir / "machine-scores.json").is_file(),
        "consolidated": (run_dir / "consolidation-receipt.json").is_file(),
        "human_reviews": len(reviews),
        "report": str(run_dir / "report.json") if (run_dir / "report.json").is_file() else None,
    }
