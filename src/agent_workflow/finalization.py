"""Idempotent recovery finalization for terminal executor loss.

The normal runner remains the preferred owner of completion collection and sealing.
This module closes the gap where the runner or tmux presentation disappears after
launch and no normal terminal projection is written.
"""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from .config import Settings
from .contracts import read_launch_contract
from .errors import WorkflowError
from .eval.attempts import emit_attempt_artifacts
from .health import process_sample, record_incident
from .policy import evaluate_budgets
from .provider_evidence import write_provider_evidence
from .receipts import (
    final_receipt_sha256,
    make_read_only,
    seal_run,
    update_provenance,
    verify_seal_details,
)
from .state import TERMINAL_STATUSES, read_status, run_dir, update_status
from .util import atomic_write_json, sha256_file, utc_now

RECOVERY_FINALIZATION_SCHEMA = "agent-workflow/recovery-finalization/v1"


@contextmanager
def _finalization_lock(run: Path) -> Iterator[None]:
    path = run / "finalization.lock"
    descriptor = os.open(
        path,
        os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _heartbeat_pids(run: Path) -> tuple[int | None, int | None]:
    heartbeat = _json_object(run / "heartbeat.json")
    runner = heartbeat.get("runner_pid")
    executor = heartbeat.get("executor_pid")
    if not isinstance(executor, int) and isinstance(heartbeat.get("pid"), int):
        executor = heartbeat["pid"]
    return (
        runner if isinstance(runner, int) else None,
        executor if isinstance(executor, int) else None,
    )


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


def _executor_result(process_result: dict[str, Any]) -> tuple[str, int | None, str]:
    if not process_result:
        return "lost", None, "executor_lost"
    returncode = process_result.get("returncode")
    exit_code = process_result.get("exit_code")
    if returncode == 0:
        return "completed", exit_code if isinstance(exit_code, int) else 0, "completion_missing"
    if returncode in {130, 143}:
        return "interrupted", exit_code if isinstance(exit_code, int) else int(returncode), "interrupted"
    category = process_result.get("error_category")
    return (
        "failed",
        exit_code if isinstance(exit_code, int) else (int(returncode) if isinstance(returncode, int) else None),
        str(category) if isinstance(category, str) and category else "executor_failed",
    )


def _already_finalized(run: Path, status: dict[str, Any]) -> dict[str, Any] | None:
    receipt_path = run / "final-receipt.json"
    if not receipt_path.is_file():
        return None
    receipt, digest = verify_seal_details(run)
    return {
        "schema": RECOVERY_FINALIZATION_SCHEMA,
        "session_id": status.get("session_id"),
        "outcome": "already_finalized",
        "status": status.get("status"),
        "final_receipt_path": str(receipt_path),
        "final_receipt_sha256": digest,
        "sealed_artifact_count": len(receipt.get("artifacts", [])),
    }


def finalize_run(
    settings: Settings,
    session_id: str,
    *,
    observation: dict[str, Any] | None = None,
    actor: str = "agent-workflow-recovery",
    reason: str = "terminal executor evidence requires recovery finalization",
) -> dict[str, Any]:
    """Finalize one terminal, unsealed run without inventing process success.

    The operation is idempotent. It refuses to race an alive runner or executor.
    Missing process exit information is recorded as ``executor_result=lost`` and
    never converted into a fabricated process-result contract.
    """

    run = run_dir(settings, session_id)
    with _finalization_lock(run):
        status = read_status(settings, session_id)
        existing = _already_finalized(run, status)
        if existing is not None:
            return existing

        launch = read_launch_contract(run / "launch-contract.json")
        runner_pid, executor_pid = _heartbeat_pids(run)
        runner_sample = process_sample(runner_pid)
        executor_sample = process_sample(executor_pid)
        process_result = _json_object(run / "process-result.json")
        observed = observation or {}
        tmux_alive = observed.get("tmux_alive")
        observed_state = observed.get("observed_state")

        if runner_sample.get("alive") is True:
            raise WorkflowError("cannot recovery-finalize while the runner process is alive")
        if executor_sample.get("alive") is True:
            raise WorkflowError("cannot recovery-finalize while the executor process is alive")
        if not process_result and not (
            observed_state == "orphaned" and tmux_alive is False
        ):
            raise WorkflowError(
                "recovery finalization requires a durable process result or a confirmed dead orphan observation"
            )

        from .runner import _capture_patch, _collect_completion, _collect_task_result

        workdir = Path(str(launch["worktree"]["path"]))
        finished_at = utc_now()
        completion = _collect_completion(run, workdir)
        _collect_task_result(run, workdir)
        _capture_patch(workdir, run, run / "patch.diff")

        provider = write_provider_evidence(
            run,
            stream_format=str(launch["command_plan"]["stream_format"]),
            executor=(
                str(launch["command_plan"].get("executor"))
                if launch["command_plan"].get("executor")
                else None
            ),
        )
        provenance = _json_object(run / "run-provenance.json")
        wall_seconds = _duration_seconds(provenance, finished_at)
        policy = evaluate_budgets(
            provider.get("aggregate") if isinstance(provider.get("aggregate"), dict) else None,
            provenance.get("budgets") if isinstance(provenance.get("budgets"), dict) else None,
            wall_seconds=wall_seconds,
        )
        executor_result, exit_code, failure_category = _executor_result(process_result)
        completion_result = str(completion["validation_status"])
        if completion_result == "invalid":
            failure_category = "completion_invalid"
        elif completion_result == "missing" and executor_result == "completed":
            failure_category = "completion_missing"

        terminal_status = (
            "interrupted" if executor_result == "interrupted" else "failed"
        )
        recovery = {
            "schema": RECOVERY_FINALIZATION_SCHEMA,
            "session_id": session_id,
            "triggered_at": finished_at,
            "actor": actor,
            "reason": reason,
            "source_status": status.get("status"),
            "observed_state": observed_state,
            "tmux_alive": tmux_alive,
            "runner": runner_sample,
            "executor": executor_sample,
            "process_result_present": bool(process_result),
            "executor_result": executor_result,
            "completion_result": completion_result,
            "terminal_status": terminal_status,
            "failure_category": failure_category,
        }
        from .contracts import validate_instance

        validate_instance(recovery, RECOVERY_FINALIZATION_SCHEMA, artifact=str(run / "recovery-finalization.json"))
        atomic_write_json(run / "recovery-finalization.json", recovery)

        provenance_changes: dict[str, Any] = {
            "finished_at": finished_at,
            "usage": provider.get("aggregate"),
            "provider_evidence": {
                "path": "provider-evidence.json",
                "sha256": sha256_file(run / "provider-evidence.json"),
                "usage_complete": provider.get("usage_complete"),
                "capture_complete": provider.get("capture_complete"),
            },
        }
        if exit_code is not None:
            provenance_changes["exit_code"] = exit_code
        update_provenance(run, **provenance_changes)

        final_status = {
            **read_status(settings, session_id),
            "status": terminal_status,
            "executor_result": executor_result,
            "completion_result": completion_result,
            "policy_result": policy["policy_result"],
            "policy_failures": policy["policy_failures"],
            "policy_failure_category": policy["policy_failure_category"],
            "acceptance_eligible": False,
            "finished_at": finished_at,
            "exit_code": exit_code,
            "failure_category": failure_category,
            "recovery_finalization_path": str(run / "recovery-finalization.json"),
            "budget_exceeded": list(policy["budget_exceeded"]),
            "updated_at": finished_at,
        }
        atomic_write_json(run / "final-status.json", final_status)
        record_incident(
            run,
            session_id=session_id,
            category=failure_category,
            severity="high",
            summary="run required recovery finalization after terminal executor loss",
            evidence={
                "executor_result": executor_result,
                "completion_result": completion_result,
                "process_result_present": bool(process_result),
                "runner_pid": runner_pid,
                "executor_pid": executor_pid,
            },
        )
        update_status(
            settings,
            session_id,
            **{key: value for key, value in final_status.items() if key != "session_id"},
            _actor=actor,
            _reason=reason,
            _projection_source="recovery-finalization",
        )

        try:
            receipt = seal_run(run, session_id=session_id)
            digest = final_receipt_sha256(run)
            update_status(
                settings,
                session_id,
                final_receipt_path=str(run / "final-receipt.json"),
                final_receipt_sha256=digest,
                sealed_artifact_count=len(receipt["artifacts"]),
                _actor=actor,
                _reason="recovery finalization sealed terminal evidence",
                _projection_source="recovery-finalization",
            )
            make_read_only(run)
            try:
                attempt = emit_attempt_artifacts(run)
                update_status(
                    settings,
                    session_id,
                    **attempt,
                    _actor=actor,
                    _reason="recovery finalization projected attempt evidence",
                    _projection_source="recovery-finalization",
                )
            except Exception as eval_exc:
                update_status(
                    settings,
                    session_id,
                    evaluation_state="not_verified",
                    evaluation_error=str(eval_exc),
                    _actor=actor,
                    _reason="recovery attempt projection failed",
                    _projection_source="recovery-finalization",
                )
        except Exception as exc:
            update_status(
                settings,
                session_id,
                status="failed",
                failure_category="seal_failed",
                seal_error=str(exc),
                _actor=actor,
                _reason="recovery finalization could not seal evidence",
                _projection_source="recovery-finalization",
            )
            raise WorkflowError(f"recovery finalization failed to seal run: {exc}") from exc

        return {
            **recovery,
            "outcome": "finalized",
            "final_receipt_path": str(run / "final-receipt.json"),
            "final_receipt_sha256": digest,
            "sealed_artifact_count": len(receipt["artifacts"]),
            "next_action": f"agent-workflow restart {session_id}",
        }
