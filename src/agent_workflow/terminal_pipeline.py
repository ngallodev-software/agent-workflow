"""Deterministic terminal evidence pipeline shared by runner and recovery.

The executor/process loop supplies observed facts. This module owns the fixed
administrative sequence that turns those facts into canonical collections,
policy results, immutable terminal status, a sealed receipt, and the mutable
status projection. Recovery and normal execution therefore cannot drift into
separate interpretations of the same evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from time import monotonic
from pathlib import Path
from typing import Any, Iterable

from .agent_run_paths import AgentRunPaths
from .agent_context import close_terminal_assignment
from .contracts import read_contract
from .errors import WorkflowError
from .eval.attempts import emit_attempt_artifacts
from .eval.commands import collect_commands, specs_from_data
from .eval.scope import ScopePolicy, collect_scope
from .health import record_incident
from .metrics import write_execution_evidence
from .policy import evaluate_budgets
from .provider_evidence import write_provider_evidence
from .receipts import (
    final_receipt_sha256,
    make_read_only,
    seal_run,
    update_provenance,
)
from .run_collections import capture_patch, collect_completion, collect_task_result
from .run_lifecycle import transition_execution_path
from .state import read_status_path, update_projection_path
from .util import atomic_write_json, sha256_file, utc_now

TERMINAL_EXECUTOR_RESULTS = frozenset({"completed", "failed", "interrupted", "lost"})
EXECUTOR_TERMINAL_STATUS = {
    "completed": "completed",
    "failed": "failed",
    "interrupted": "interrupted",
    "lost": "failed",
}


@dataclass(frozen=True, slots=True)
class TerminalObservation:
    """Observed executor/process facts supplied to the deterministic pipeline."""

    executor_result: str
    exit_code: int | None
    failure_category: str | None = None
    timed_out: bool = False
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    stdout_bytes: int | None = None
    stderr_bytes: int | None = None
    stdout_truncated: bool | None = None
    stderr_truncated: bool | None = None
    wall_seconds: float | None = None
    first_output_at: str | None = None
    provider_capture_exceeded: bool = False




@dataclass(frozen=True, slots=True)
class TerminalOutcome:
    status: str
    exit_code: int | None
    failure_category: str | None
    acceptance_eligible: bool


def derive_terminal_outcome(
    observation: TerminalObservation,
    *,
    completion_result: str,
    policy_result: str,
    evidence_errors: Iterable[str] = (),
) -> TerminalOutcome:
    """Derive the only supported terminal interpretation from observed facts."""
    if observation.executor_result not in TERMINAL_EXECUTOR_RESULTS:
        raise WorkflowError(
            f"unsupported executor result: {observation.executor_result!r}"
        )
    errors = tuple(evidence_errors)
    status = EXECUTOR_TERMINAL_STATUS[observation.executor_result]
    if status == "completed" and (completion_result != "valid" or errors):
        status = "failed"

    failure_candidates = (
        (observation.timed_out, "timeout"),
        (completion_result == "invalid", "completion_invalid"),
        (
            completion_result == "missing"
            and observation.executor_result == "completed",
            "completion_missing",
        ),
        (observation.provider_capture_exceeded, "provider_evidence_capture_exceeded"),
        (bool(errors), "terminal_collection_failed"),
        (bool(observation.failure_category), observation.failure_category),
    )
    failure_category = next(
        (str(category) for applies, category in failure_candidates if applies and category),
        None,
    )

    if status == "completed":
        exit_code = 0 if observation.exit_code is None else observation.exit_code
    elif observation.exit_code not in {None, 0}:
        exit_code = observation.exit_code
    elif status == "interrupted":
        exit_code = 130
    else:
        exit_code = 1

    return TerminalOutcome(
        status=status,
        exit_code=exit_code,
        failure_category=failure_category,
        acceptance_eligible=bool(
            status == "completed"
            and completion_result == "valid"
            and policy_result != "failed"
        ),
    )


@dataclass(frozen=True, slots=True)
class RecoveryContext:
    actor: str
    reason: str
    source_status: str | None
    observed_state: str | None
    worker_alive: bool | None
    runner: dict[str, Any]
    executor: dict[str, Any]
    process_result_present: bool


def authoritative_projection(
    launch: dict[str, Any], run_dir: Path, current: dict[str, Any]
) -> dict[str, Any]:
    """Overlay immutable launch identity and paths onto mutable status state."""
    paths_obj = AgentRunPaths(run_dir)
    agent_run = launch["agent_run"]
    worktree = launch["worktree"]
    command = launch["worker_plan"]
    pack = launch["pack"]
    paths = launch["paths"]
    evaluation = launch["evaluation_policy"]
    projected = {
        key: value
        for key, value in current.items()
        if key
        not in {
            "disposition",
            "disposition_at",
            "disposition_actor",
            "accepted_revision",
            "lifecycle_receipt_path",
            "final_receipt_path",
            "final_receipt_sha256",
            "sealed_artifact_count",
            "projection_generated_at",
            "projection_source",
            "projection_freshness",
            "projection_authority",
        }
    }
    projected.update(
        {
            "schema": "agent-workflow/agent-run-status/v1",
            "agent_run_id": agent_run["id"],
            "ticket_id": launch.get("ticket"),
            "agent_name": agent_run.get("agent_name"),
            "agent_class": agent_run.get("agent_class"),
            "role": (launch.get("role") or {}).get("id"),
            "role_digest": (launch.get("role") or {}).get("digest"),
            "tier": agent_run.get("tier"),
            "retry_of": agent_run.get("retry_of_agent_run_id"),
            "created_at": agent_run["created_at"],
            "workdir": worktree["path"],
            "source_revision": worktree.get("source_revision"),
            "branch": worktree.get("branch"),
            "dirty_at_launch": worktree.get("dirty_at_launch"),
            "prompt_path": str(run_dir / launch["prompt"]["stored"]),
            "prompt_source": launch["prompt"]["source"],
            "prompt_sha256": launch["prompt"]["sha256"],
            "prompt_pack_root": pack.get("root"),
            "pack_id": pack.get("id"),
            "result_contract": paths.get("result_contract"),
            "launch_prompt_path": str(run_dir / launch["prompt"]["launch_stored"]),
            "launch_prompt_sha256": launch["prompt"]["launch_sha256"],
            "log_path": str(run_dir / launch["expected_outputs"]["output_log"]),
            "command_path": str(paths_obj.command),
            "handoff_dir": paths["handoff_dir"],
            "provenance_path": str(paths_obj.provenance),
            "events_path": str(paths_obj.executor_events),
            "stderr_path": str(paths_obj.executor_stderr),
            "source_baseline_path": str(run_dir / launch["source_baseline"]["path"]),
            "launch_contract_path": str(paths_obj.contract),
            "worker_mode": command["mode"],
            "interactive_stdio": command["interactive_stdio"],
            "evaluation_path": evaluation.get("path"),
            "disposition": None,
        }
    )
    return projected


def _json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _duration_seconds(provenance: dict[str, Any], finished_at: str) -> float | None:
    started = provenance.get("started_at")
    if not isinstance(started, str):
        return None
    try:
        return max(
            0.0,
            datetime.fromisoformat(finished_at).timestamp()
            - datetime.fromisoformat(started).timestamp(),
        )
    except ValueError:
        return None


def _post_runtime_policy(run_dir: Path, launch: dict[str, Any]) -> dict[str, Any]:
    runtime_path = AgentRunPaths(run_dir).evaluation_runtime
    if runtime_path.is_file():
        return read_contract(runtime_path, "agent-workflow/evaluation-runtime/v1")
    raw = launch.get("runtime_policy")
    return dict(raw) if isinstance(raw, dict) else {}


def _collect_post_policy(
    run_dir: Path,
    workdir: Path,
    launch: dict[str, Any],
) -> list[str]:
    runtime = _post_runtime_policy(run_dir, launch)
    errors: list[str] = []
    try:
        scope_data = runtime.get("scope", {})
        if isinstance(scope_data, dict) and scope_data:
            policy = ScopePolicy(
                authorized_root=workdir,
                writable_paths=tuple(scope_data.get("writable_paths", ())),
                writable_trees=tuple(scope_data.get("writable_trees", ())),
                disposable_trees=tuple(scope_data.get("disposable_trees", ())),
            )
            collect_scope(
                workdir,
                phase="post",
                policy=policy,
                receipt_dir=AgentRunPaths(run_dir).scope,
            )
        commands = runtime.get("acceptance_commands", [])
        if commands or runtime.get("native_job_binding_sha256"):
            collect_commands(
                workdir,
                specs_from_data(commands),
                phase="post",
                receipt_dir=AgentRunPaths(run_dir).collections,
            )
    except Exception as exc:  # deterministic failure evidence, not a crash boundary
        errors.append(f"collectors: {exc}")
    return errors


def _write_recovery_record(
    run_dir: Path,
    *,
    recovery: RecoveryContext,
    observation: TerminalObservation,
    completion_result: str,
    terminal_status: str,
    failure_category: str | None,
    triggered_at: str,
) -> dict[str, Any]:
    value = {
        "schema": "agent-workflow/recovery-finalization/v1",
        "agent_run_id": run_dir.name,
        "triggered_at": triggered_at,
        "actor": recovery.actor,
        "reason": recovery.reason,
        "source_status": recovery.source_status,
        "observed_state": recovery.observed_state,
        "worker_alive": recovery.worker_alive,
        "runner": recovery.runner,
        "executor": recovery.executor,
        "process_result_present": recovery.process_result_present,
        "executor_result": observation.executor_result,
        "completion_result": completion_result,
        "terminal_status": terminal_status,
        "failure_category": failure_category,
    }
    from .contracts import validate_instance

    validate_instance(
        value,
        "agent-workflow/recovery-finalization/v1",
        artifact=str(run_dir / "recovery-finalization.json"),
    )
    atomic_write_json(run_dir / "recovery-finalization.json", value)
    return value


def finalize_terminal_run(
    run_dir: Path,
    launch: dict[str, Any],
    observation: TerminalObservation,
    *,
    secret_values: tuple[str, ...] = (),
    actor: str = "runner",
    reason: str = "executor terminal evidence sealed",
    projection_source: str = "runner-final",
    seal_failure_reason: str = "terminal evidence sealing failed",
    recovery: RecoveryContext | None = None,
) -> dict[str, Any]:
    """Execute the single terminal administrative pipeline for one Agent Run."""
    if observation.executor_result not in TERMINAL_EXECUTOR_RESULTS:
        raise WorkflowError(
            f"unsupported executor result: {observation.executor_result!r}"
        )
    run_dir = run_dir.resolve()
    paths = AgentRunPaths(run_dir)
    workdir = Path(str(launch["worktree"]["path"])).resolve()
    agent_run_id = str(launch["agent_run"]["id"])
    finished_at = utc_now()
    pipeline_started = monotonic()
    section_timings: dict[str, float] = {}

    def timed(label: str, operation: Any) -> Any:
        started = monotonic()
        try:
            return operation()
        finally:
            section_timings[label] = round(monotonic() - started, 6)

    evidence_errors = list(observation.errors)
    completion = timed(
        "completion_collection",
        lambda: collect_completion(run_dir, workdir, secret_values=secret_values),
    )
    completion_result = str(completion.get("validation_status", "invalid"))
    if completion_result == "valid":
        try:
            timed(
                "assignment_close",
                lambda: close_terminal_assignment(run_dir, agent_run_id),
            )
        except Exception as exc:
            evidence_errors.append(f"assignment-close: {exc}")
    try:
        timed(
            "task_result_collection",
            lambda: collect_task_result(run_dir, workdir, secret_values=secret_values),
        )
    except Exception as exc:
        evidence_errors.append(f"task-result: {exc}")
    evidence_errors.extend(
        timed(
            "post_policy_collection",
            lambda: _collect_post_policy(run_dir, workdir, launch),
        )
    )
    try:
        timed("patch_capture", lambda: capture_patch(workdir, run_dir, paths.patch))
    except Exception as exc:
        evidence_errors.append(f"patch: {exc}")

    provider: dict[str, Any] | None = None
    try:
        provider = timed(
            "provider_evidence",
            lambda: write_provider_evidence(
                run_dir,
                capture_exceeded=observation.provider_capture_exceeded,
                stream_format=str(launch["worker_plan"]["stream_format"]),
                executor=(
                    str(launch["worker_plan"].get("executor"))
                    if launch["worker_plan"].get("executor")
                    else None
                ),
            ),
        )
    except Exception as exc:
        evidence_errors.append(f"provider-evidence: {exc}")

    provenance = _json_object(paths.provenance)
    wall_seconds = observation.wall_seconds
    if wall_seconds is None:
        wall_seconds = _duration_seconds(provenance, finished_at)
    usage = (
        provider.get("aggregate")
        if isinstance(provider, dict) and isinstance(provider.get("aggregate"), dict)
        else None
    )
    policy = timed(
        "policy_evaluation",
        lambda: evaluate_budgets(
            usage,
            provenance.get("budgets") if isinstance(provenance.get("budgets"), dict) else None,
            wall_seconds=wall_seconds,
        ),
    )

    outcome = derive_terminal_outcome(
        observation,
        completion_result=completion_result,
        policy_result=str(policy["policy_result"]),
        evidence_errors=evidence_errors,
    )
    terminal_status = outcome.status
    failure_category = outcome.failure_category
    run_exit_code = outcome.exit_code

    provenance_changes: dict[str, Any] = {
        "finished_at": finished_at,
        "exit_code": run_exit_code,
        "usage": usage,
    }
    if observation.first_output_at is not None:
        provenance_changes["first_output_at"] = observation.first_output_at
    if provider is not None:
        provenance_changes["provider_evidence"] = {
            "path": "provider-evidence.json",
            "sha256": sha256_file(paths.provider_evidence),
            "usage_complete": provider.get("usage_complete"),
            "capture_complete": provider.get("capture_complete"),
        }
    timed("provenance_update", lambda: update_provenance(run_dir, **provenance_changes))

    current = read_status_path(paths.status)
    final_status: dict[str, Any] = {
        **authoritative_projection(launch, run_dir, current),
        "status": terminal_status,
        "executor_result": observation.executor_result,
        "completion_result": completion_result,
        "policy_result": policy["policy_result"],
        "policy_failures": policy["policy_failures"],
        "policy_failure_category": policy["policy_failure_category"],
        "acceptance_eligible": outcome.acceptance_eligible,
        "finished_at": finished_at,
        "exit_code": run_exit_code,
        "pump_errors": [*evidence_errors, *observation.warnings],
        "failure_category": failure_category,
        "updated_at": finished_at,
    }
    if observation.stdout_bytes is not None:
        final_status["stdout_bytes"] = observation.stdout_bytes
    if observation.stderr_bytes is not None:
        final_status["stderr_bytes"] = observation.stderr_bytes
    if observation.stdout_truncated is not None:
        final_status["stdout_truncated"] = observation.stdout_truncated
    if observation.stderr_truncated is not None:
        final_status["stderr_truncated"] = observation.stderr_truncated
    if wall_seconds is not None:
        final_status["wall_seconds"] = round(wall_seconds, 6)

    recovery_value = None
    if recovery is not None:
        recovery_value = _write_recovery_record(
            run_dir,
            recovery=recovery,
            observation=observation,
            completion_result=completion_result,
            terminal_status=terminal_status,
            failure_category=failure_category,
            triggered_at=finished_at,
        )
        final_status["recovery_finalization_path"] = str(
            run_dir / "recovery-finalization.json"
        )

    if failure_category:
        record_incident(
            run_dir,
            agent_run_id=agent_run_id,
            category=failure_category,
            severity="high",
            summary=(
                "Agent Run required recovery finalization"
                if recovery is not None
                else "Agent Run terminal pipeline classified a failure"
            ),
            evidence={
                "executor_result": observation.executor_result,
                "completion_result": completion_result,
                "exit_code": run_exit_code,
                "errors": evidence_errors,
            },
        )
    if policy["policy_result"] == "failed":
        record_incident(
            run_dir,
            agent_run_id=agent_run_id,
            category="budget_policy_failed",
            severity="medium",
            summary="executor completed with one or more budget-policy violations",
            evidence={
                "executor_result": observation.executor_result,
                "policy_failures": policy["policy_failures"],
            },
        )

    timed("final_status_write", lambda: atomic_write_json(paths.final_status, final_status))
    timed(
        "execution_evidence",
        lambda: write_execution_evidence(run_dir, elapsed_seconds=wall_seconds),
    )
    terminal_timing = {
        "schema": "agent-workflow/terminal-timing/v1",
        "agent_run_id": agent_run_id,
        "recorded_at": utc_now(),
        "sections": section_timings,
        "pre_seal_total_seconds": round(monotonic() - pipeline_started, 6),
        "executor_wall_seconds": round(wall_seconds, 6) if wall_seconds is not None else None,
        "note": (
            "Section timings are host-side terminal evidence work after executor exit; "
            "they exclude executor/model-active time. Sealing and final projection occur "
            "after this artifact is written and are observable as residual host overhead."
        ),
    }
    atomic_write_json(run_dir / "terminal-timing.json", terminal_timing)
    try:
        receipt = seal_run(run_dir, agent_run_id=agent_run_id)
        digest = final_receipt_sha256(run_dir)
    except Exception as exc:
        transition_execution_path(
            paths.status,
            "failed",
            actor=actor,
            reason=seal_failure_reason,
            projection_source=projection_source,
            finished_at=utc_now(),
            exit_code=run_exit_code or 1,
            failure_category="seal_failed",
            seal_error=str(exc),
        )
        raise WorkflowError(f"terminal finalization failed to seal run: {exc}") from exc

    transition_execution_path(
        paths.status,
        terminal_status,
        actor=actor,
        reason=reason,
        projection_source=projection_source,
        **{key: value for key, value in final_status.items() if key != "status"},
        final_receipt_path=str(paths.final_receipt),
        final_receipt_sha256=digest,
        sealed_artifact_count=len(receipt["artifacts"]),
    )
    make_read_only(run_dir)
    try:
        attempt = emit_attempt_artifacts(run_dir)
        update_projection_path(paths.status, projection_source="evaluation", **attempt)
    except Exception as eval_exc:
        update_projection_path(
            paths.status,
            projection_source="evaluation",
            evaluation_state="not_verified",
            evaluation_error=str(eval_exc),
        )

    return {
        "agent_run_id": agent_run_id,
        "outcome": "finalized",
        "status": terminal_status,
        "executor_result": observation.executor_result,
        "completion_result": completion_result,
        "policy_result": policy["policy_result"],
        "exit_code": run_exit_code,
        "failure_category": failure_category,
        "final_receipt_path": str(paths.final_receipt),
        "final_receipt_sha256": digest,
        "sealed_artifact_count": len(receipt["artifacts"]),
        "recovery": recovery_value,
    }
