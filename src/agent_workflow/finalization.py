"""Idempotent recovery finalization for terminal executor loss.

The normal runner remains the preferred owner of completion collection and sealing.
This module closes the gap where an owned worker disappears after launch and no
normal final projection is written.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import Settings
from .contracts import read_agent_run_contract
from .errors import WorkflowError
from .health import process_sample
from .receipts import verify_seal_details
from .state import run_dir
from .run_lifecycle import authoritative_execution_status, synchronize_projection
from .contracts import read_contract
from .terminal_pipeline import RecoveryContext, TerminalObservation, finalize_terminal_run

RECOVERY_FINALIZATION_SCHEMA = "agent-workflow/recovery-finalization/v1"
RUNNER_CONVERGENCE_SECONDS = 2.0
RUNNER_CONVERGENCE_POLL_SECONDS = 0.05


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


def _executor_result(process_result: dict[str, Any]) -> tuple[str, int | None, str | None]:
    if not process_result:
        return "lost", None, "executor_lost"
    returncode = process_result.get("returncode")
    exit_code = process_result.get("exit_code")
    if returncode == 0:
        return "completed", exit_code if isinstance(exit_code, int) else 0, None
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
        "agent_run_id": status.get("agent_run_id"),
        "outcome": "already_finalized",
        "status": authoritative_execution_status(run),
        "final_receipt_path": str(receipt_path),
        "final_receipt_sha256": digest,
        "sealed_artifact_count": len(receipt.get("artifacts", [])),
    }


def finalize_run(
    settings: Settings,
    agent_run_id: str,
    *,
    observation: dict[str, Any] | None = None,
    actor: str = "agent-workflow-recovery",
    reason: str = "worker evidence requires recovery finalization",
) -> dict[str, Any]:
    """Finalize one stopped, unsealed Agent Run without inventing process success.

    The operation is idempotent. It refuses to race an alive runner or executor.
    Missing process exit information is recorded as ``executor_result=lost`` and
    never converted into a fabricated process-result contract.
    """

    run = run_dir(settings, agent_run_id)
    with _finalization_lock(run):
        status = synchronize_projection(run / "status.json", source="recovery-finalization")
        existing = _already_finalized(run, status)
        if existing is not None:
            return existing

        launch = read_agent_run_contract(run / "agent-run-contract.json")
        runner_pid, executor_pid = _heartbeat_pids(run)
        runner_sample = process_sample(runner_pid)
        executor_sample = process_sample(executor_pid)
        process_result = _json_object(run / "process-result.json")
        external_exit_path = run / "external-worker-exit.json"
        external_exit = (
            read_contract(external_exit_path, "agent-workflow/external-worker-exit/v1")
            if external_exit_path.is_file()
            else None
        )
        observed = observation or {}
        worker_alive = observed.get("worker_alive")
        observed_state = observed.get("observed_state")

        if runner_sample.get("alive") is True and process_result:
            # ``process-result.json`` is written only after the executor has
            # exited and stream collection has completed.  At that point the
            # still-live runner normally owns a short final collection/seal
            # window.  Give it bounded time to converge instead of turning a
            # normal monitor race into an operator-visible failure.
            deadline = time.monotonic() + RUNNER_CONVERGENCE_SECONDS
            while time.monotonic() < deadline:
                existing = _already_finalized(
                    run,
                    synchronize_projection(
                        run / "status.json", source="recovery-finalization-convergence"
                    ),
                )
                if existing is not None:
                    return existing
                runner_sample = process_sample(runner_pid)
                if runner_sample.get("alive") is not True:
                    break
                time.sleep(RUNNER_CONVERGENCE_POLL_SECONDS)
            if runner_sample.get("alive") is True:
                return {
                    "schema": RECOVERY_FINALIZATION_SCHEMA,
                    "agent_run_id": agent_run_id,
                    "outcome": "runner_converging",
                    "status": authoritative_execution_status(run),
                    "process_result_present": True,
                    "runner": runner_sample,
                    "next_action": f"agent-workflow agent-run finalize {agent_run_id}",
                }
        elif runner_sample.get("alive") is True:
            raise WorkflowError("cannot recovery-finalize while the runner process is alive")
        # A durable process result is stronger evidence of executor exit than a
        # later PID liveness sample, which can race PID reuse.
        if executor_sample.get("alive") is True and not process_result:
            raise WorkflowError("cannot recovery-finalize while the executor process is alive")
        if not process_result and external_exit is None and not (
            observed_state == "orphaned" and worker_alive is False
        ):
            raise WorkflowError(
                "recovery finalization requires a durable process result or a confirmed dead orphan observation"
            )

        if external_exit is not None:
            executor_result, exit_code, failure_category = (
                "completed",
                None,
                "external_exit_observed",
            )
        else:
            executor_result, exit_code, failure_category = _executor_result(process_result)

        finalized = finalize_terminal_run(
            run,
            launch,
            TerminalObservation(
                executor_result=executor_result,
                exit_code=exit_code,
                failure_category=failure_category,
            ),
            actor=actor,
            reason=reason,
            projection_source="recovery-finalization",
            seal_failure_reason="recovery finalization could not seal evidence",
            recovery=RecoveryContext(
                actor=actor,
                reason=reason,
                source_status=(str(status.get("status")) if status.get("status") is not None else None),
                observed_state=(str(observed_state) if observed_state is not None else None),
                worker_alive=(worker_alive if isinstance(worker_alive, bool) else None),
                runner=runner_sample,
                executor=executor_sample,
                process_result_present=bool(process_result),
            ),
        )
        recovery_value = finalized.pop("recovery", None)
        return {
            **(recovery_value if isinstance(recovery_value, dict) else {}),
            **finalized,
            "schema": RECOVERY_FINALIZATION_SCHEMA,
            "next_action": f"agent-workflow agent-run restart {agent_run_id}",
        }
