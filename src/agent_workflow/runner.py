from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import signal
import stat
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, BinaryIO

from .agent_run_paths import AgentRunPaths
from .run_collections import capture_patch, collect_completion, collect_task_result
from .errors import WorkflowError
from .run_lifecycle import transition_execution_path
from .state import read_status_path, update_projection_path
from .contracts import read_agent_run_contract
from .diagnostics import classify_failure
from .health import (
    PROCESS_RESULT_SCHEMA,
    last_event,
    record_health_sample,
    record_incident,
    write_process_result,
)
from .eval.commands import collect_commands, specs_from_data
from .eval.scope import ScopePolicy, collect_scope
from .executors import accumulate_usage, event_text, parse_event, usage_update
from .receipts import final_receipt_sha256, make_read_only, seal_run, update_provenance
from .eval.attempts import emit_attempt_artifacts
from .metrics import write_execution_evidence
from .agent_context import apply_bridged_completion
from .messages import (
    CONTROL_BRIDGE_ENV,
    CONTROL_BRIDGE_MAX_BYTES,
    CONTROL_BRIDGE_SCHEMA,
    append_message,
)
from .steering import (
    STEERING_INBOX_ENV,
    current_delivery,
    deliver_pending,
    record_acknowledgement,
)
from .provider_evidence import MAX_PROVIDER_EVENT_BYTES, write_provider_evidence
from .process import (
    EnvironmentPolicy,
    ProcessRequest,
    redact_argv,
    redact_text,
    secret_values_from_argv,
    spawn,
)
from .util import atomic_write_json, sha256_file, utc_now
from .path import read_regular_file
from .policy import evaluate_budgets


MAX_EXECUTOR_STDOUT_BYTES = 16 * 1024 * 1024
MAX_EXECUTOR_STDERR_BYTES = 16 * 1024 * 1024
CONTROL_POLL_SECONDS = 0.25
_RUNTIME_ENVIRONMENT = (
    "AGENT_WORKFLOW_AGENT_RUN_ID",
    "AGENT_WORKFLOW_TICKET_ID",
    "AGENT_WORKFLOW_PACK_ID",
    "AGENT_WORKFLOW_PROMPT_SOURCE",
    "AGENT_WORKFLOW_HANDOFF_DIR",
    "AGENT_WORKFLOW_PROMPT_PACK_ROOT",
    "AGENT_WORKFLOW_COMMAND_CATALOG",
    "AGENT_WORKFLOW_COMMAND_CARD",
    "AGENT_WORKFLOW_CLI",
    CONTROL_BRIDGE_ENV,
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_STATE_HOME",
    "FAKE_AGENT_MODE",
    "FAKE_AGENT_DELAY",
    "FAKE_AGENT_RESULT_JSON",
    "FAKE_AGENT_AUTO_STEER",
    "FAKE_AGENT_EMPTY_COMPLETION",
    "FAKE_AGENT_STEER_OUTCOME",
)


def _drain_control_bridge(
    run_dir: Path, *, active: bool, allow_terminal_at_exit: bool = False
) -> bool:
    """Consume bounded child intents using host-owned durable state."""
    paths = AgentRunPaths(run_dir)
    launch = read_agent_run_contract(paths.contract)
    agent_run_id = str(launch["agent_run"]["id"])
    handoff = Path(str(launch["paths"].get("handoff_dir", ""))).resolve()
    bridge = handoff / "control-intents"
    if bridge.parent != handoff or bridge.is_symlink() or not bridge.is_dir():
        return False
    evidence_path = paths.control_intents
    processed: set[str] = set()
    processed_requests: set[str] = set()
    processed_sequences: set[int] = set()
    if evidence_path.is_file():
        for line in evidence_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and isinstance(row.get("file"), str):
                processed.add(row["file"])
                if isinstance(row.get("request_id"), str):
                    processed_requests.add(row["request_id"])
                if isinstance(row.get("sequence"), int):
                    processed_sequences.add(row["sequence"])

    def record(name: str, request_id: str | None, sequence: int | None, outcome: str, reason: str) -> None:
        with evidence_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({
                "file": name, "request_id": request_id, "sequence": sequence, "outcome": outcome,
                "reason": reason, "at": utc_now(),
            }, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def source_sequence(path: Path) -> int:
        try:
            return int(path.stem.rsplit("-", 1)[1])
        except (ValueError, IndexError):
            return 2**31

    terminal_completion = False
    for source in sorted(bridge.glob("intent-*.json"), key=source_sequence):
        if source.name in processed:
            continue
        intent: dict[str, Any] | None = None
        request_id: str | None = None
        outcome, reason = "rejected", "malformed control intent"
        try:
            mode = source.lstat().st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISREG(mode) or source.stat().st_size > CONTROL_BRIDGE_MAX_BYTES:
                raise WorkflowError("unsafe or oversized control intent")
            value = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("schema") != CONTROL_BRIDGE_SCHEMA:
                raise WorkflowError("unsupported control intent schema")
            intent = value
            request_id = str(value.get("request_id"))
            uuid.UUID(request_id)
            if request_id in processed_requests:
                raise WorkflowError("duplicate control request")
            sequence = value.get("sequence")
            if (
                not isinstance(sequence, int)
                or sequence < 1
                or sequence in processed_sequences
                or sequence != max(processed_sequences, default=0) + 1
            ):
                raise WorkflowError("stale or duplicate control sequence")
            body = {key: item for key, item in value.items() if key != "digest"}
            digest = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if value.get("agent_run_id") != agent_run_id or value.get("digest") != digest:
                raise WorkflowError("control intent identity or digest mismatch")
            intent_kind = str(value["kind"])
            if intent_kind not in {"progress", "ack", "task_complete"}:
                raise WorkflowError("unsupported control intent kind")
            if not active and not (allow_terminal_at_exit and intent_kind == "task_complete"):
                raise WorkflowError("request arrived after executor exit")
            acknowledgement_outcome = value.get("outcome", "applied")
            if intent_kind == "ack" and acknowledgement_outcome not in {"applied", "rejected"}:
                raise WorkflowError("invalid acknowledgement outcome")
            if intent_kind != "ack" and value.get("outcome") is not None:
                raise WorkflowError("only acknowledgement intents may include outcome")
            if intent_kind == "task_complete":
                terminal = value.get("terminal", False)
                if not isinstance(terminal, bool):
                    raise WorkflowError("task completion terminal flag must be boolean")
                completion_sha256 = value.get("completion_sha256")
                if (
                    not isinstance(completion_sha256, str)
                    or len(completion_sha256) != 64
                    or any(character not in "0123456789abcdef" for character in completion_sha256)
                ):
                    raise WorkflowError("task completion intent requires a completion handoff digest")
                completion = collect_completion(
                    run_dir,
                    Path(str(launch["worktree"]["path"])),
                    expected_source_sha256=completion_sha256,
                )
                if completion["validation_status"] != "valid":
                    details = "; ".join(completion.get("validation_errors", []))
                    raise WorkflowError(f"task completion handoff is invalid: {details}")
                apply_bridged_completion(
                    run_dir,
                    agent_run_id,
                    actor=str(value["actor"]),
                    summary=str(value["content"]),
                    terminal=terminal,
                )
                terminal_completion = terminal
            if intent_kind == "ack":
                correlation_id = str(value["correlation_id"])
                existing_delivery = current_delivery(run_dir, correlation_id)
                if existing_delivery is not None and existing_delivery["outcome"] in {
                    "applied", "rejected", "expired",
                }:
                    prior = str(existing_delivery["outcome"])
                    if prior == "expired":
                        raise WorkflowError("steering request already expired")
                    if prior != acknowledgement_outcome:
                        raise WorkflowError(
                            f"steering request already has terminal outcome {prior}"
                        )
                    outcome, reason = (
                        "duplicate",
                        "duplicate terminal acknowledgement ignored",
                    )
                else:
                    append_message(
                        run_dir, agent_run_id=agent_run_id, direction="child_to_parent",
                        kind=intent_kind, actor=str(value["actor"]),
                        content=str(value["content"]),
                        correlation_id=correlation_id,
                    )
                    record_acknowledgement(
                        run_dir,
                        correlation_id=correlation_id,
                        outcome=str(acknowledgement_outcome),
                        reason=str(value["content"]),
                    )
                    outcome, reason = "applied", "authoritative host append"
            else:
                append_message(
                    run_dir, agent_run_id=agent_run_id, direction="child_to_parent",
                    kind=intent_kind, actor=str(value["actor"]),
                    content=str(value["content"]),
                    correlation_id=value.get("correlation_id"),
                )
                outcome, reason = "applied", "authoritative host append"
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, WorkflowError) as exc:
            reason = str(exc)
            correlation_id = intent.get("correlation_id") if intent else None
            try:
                uuid.UUID(correlation_id) if isinstance(correlation_id, str) else None
            except ValueError:
                correlation_id = None
            append_message(
                run_dir, agent_run_id=agent_run_id, direction="child_to_parent", kind="error",
                actor="agent-workflow-host",
                content=json.dumps({"outcome": outcome, "request_id": request_id, "reason": reason}, sort_keys=True),
                correlation_id=correlation_id if isinstance(correlation_id, str) else None,
            )
        record(source.name, request_id, intent.get("sequence") if intent else None, outcome, reason)
        if request_id is not None:
            processed_requests.add(request_id)
        if intent and isinstance(intent.get("sequence"), int):
            processed_sequences.add(intent["sequence"])
    return terminal_completion


def _authoritative_projection(
    launch: dict[str, Any], run_dir: Path, current: dict[str, Any]
) -> dict[str, Any]:
    """Overlay only launch-bound identity and paths onto the status projection."""
    paths_obj = AgentRunPaths(run_dir)
    agent_run = launch["agent_run"]
    worktree = launch["worktree"]
    command = launch["worker_plan"]
    pack = launch["pack"]
    paths = launch["paths"]
    evaluation = launch["evaluation_policy"]
    # Preserve execution observations collected by the runner, but never carry
    # mutable review/receipt selectors into the sealed final-status authority.
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
            # Projection metadata describes the mutable status cache, not the
            # immutable terminal authority. Carrying it into final-status.json
            # also collides with the explicit projection metadata supplied
            # when the sealed result is projected back to status.json.
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


def _write_bytes(stream: BinaryIO, data: bytes) -> None:
    stream.write(data)
    stream.flush()


def _mirror_output(stream: BinaryIO, data: bytes) -> None:
    """Best-effort output mirroring; durable Agent Run artifacts remain authoritative."""
    try:
        _write_bytes(stream, data)
    except (BrokenPipeError, OSError, ValueError):
        pass


def _child_environment(
    environment_allowlist: object,
    *,
    bridge_dir: Path,
    steering_dir: Path,
    ticket_id: str | None,
    pack_id: str | None,
) -> EnvironmentPolicy:
    configured = environment_allowlist
    names = set(_RUNTIME_ENVIRONMENT)
    if isinstance(configured, list):
        names.update(value for value in configured if isinstance(value, str) and value)
    names.discard("XDG_STATE_HOME")
    values = {
        CONTROL_BRIDGE_ENV: str(bridge_dir),
        STEERING_INBOX_ENV: str(steering_dir),
        "XDG_STATE_HOME": str(bridge_dir.parent),
    }
    if ticket_id is not None:
        values["AGENT_WORKFLOW_TICKET_ID"] = ticket_id
    if pack_id is not None:
        values["AGENT_WORKFLOW_PACK_ID"] = pack_id
    return EnvironmentPolicy(
        allowlist=tuple(sorted(names)),
        values=values,
    )



def _seal_terminal_run(
    run_dir: Path,
    launch: dict[str, Any],
    final_status: dict[str, Any],
    *,
    elapsed_seconds: float,
    seal_failure_reason: str,
    terminal_reason: str,
    seal_failure_exit: int,
) -> int | None:
    """Seal one terminal result and synchronize its mutable projection."""
    paths = AgentRunPaths(run_dir)
    atomic_write_json(paths.final_status, final_status)
    write_execution_evidence(run_dir, elapsed_seconds=elapsed_seconds)
    try:
        receipt = seal_run(run_dir, agent_run_id=str(launch["agent_run"]["id"]))
        receipt_hash = final_receipt_sha256(run_dir)
    except Exception as exc:
        transition_execution_path(
            paths.status,
            "failed",
            actor="runner",
            reason=seal_failure_reason,
            projection_source="runner-final",
            finished_at=utc_now(),
            exit_code=seal_failure_exit,
            failure_category="seal_failed",
            seal_error=str(exc),
        )
        return seal_failure_exit

    transition_execution_path(
        paths.status,
        str(final_status["status"]),
        actor="runner",
        reason=terminal_reason,
        projection_source="runner-final",
        **{key: value for key, value in final_status.items() if key != "status"},
        final_receipt_path=str(paths.final_receipt),
        final_receipt_sha256=receipt_hash,
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
    return None

def execute(
    run_dir: Path,
    workdir: Path,
    command: list[str],
    *,
    stream_format: str,
    interactive: bool = False,
    force_noninteractive: bool = False,
    heartbeat_seconds: float = 5.0,
) -> int:
    run_dir = run_dir.resolve()
    paths = AgentRunPaths(run_dir)
    launch = read_agent_run_contract(paths.contract)
    contract_workdir = Path(str(launch["worktree"]["path"]))
    workdir = contract_workdir
    worker_plan = launch["worker_plan"]
    contract_command = [str(value) for value in worker_plan["argv"]]
    if force_noninteractive:
        contract_command = [
            str(value)
            for value in worker_plan.get("noninteractive_argv", contract_command)
        ]
    if command:
        encoded = json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        actual_digest = hashlib.sha256(encoded).hexdigest()
        expected_digest = worker_plan.get(
            "noninteractive_command_sha256" if force_noninteractive else "command_sha256"
        )
        if not isinstance(expected_digest, str) or actual_digest != expected_digest:
            raise WorkflowError("runtime command does not match immutable launch contract")
    else:
        command = contract_command
    stream_format = str(worker_plan["stream_format"])
    interactive = bool(worker_plan["interactive_stdio"]) and not force_noninteractive
    status_path = paths.status
    prompt_read = read_regular_file(run_dir / launch["prompt"]["launch_stored"])
    if prompt_read.sha256 != launch["prompt"]["launch_sha256"]:
        raise WorkflowError("launch prompt changed after contract creation")
    prompt = prompt_read.data
    output_path = paths.output_log
    events_path = paths.executor_events
    stderr_path = paths.executor_stderr
    heartbeat_path = paths.heartbeat
    lock = threading.Lock()
    usage: dict[str, Any] | None = None
    provider_event_bytes = 0
    provider_capture_exceeded = False
    first_output_at: str | None = None
    last_normalized_text: str | None = None
    pump_errors: list[str] = []
    wall_started = time.monotonic()
    runtime = launch.get("runtime_policy")
    # The immutable launch contract carries executor budgets, while the
    # sealed evaluation-runtime artifact carries the full evaluation policy
    # (including writable/disposable scope). Merge them before post-run
    # collectors so scope evidence is collected under the same policy used at
    # launch. Older contracts may omit the persisted policy entirely.
    persisted_runtime_path = paths.evaluation_runtime
    if persisted_runtime_path.is_file():
        try:
            persisted_runtime = json.loads(
                persisted_runtime_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            persisted_runtime = None
        if isinstance(persisted_runtime, dict):
            merged_runtime = dict(persisted_runtime)
            if isinstance(runtime, dict):
                merged_runtime.update(runtime)
            runtime = merged_runtime
    provenance_initial = json.loads(
        (paths.provenance).read_text(encoding="utf-8")
    )
    initial_budgets = runtime.get("budgets", {}) if isinstance(runtime, dict) else {}
    plan_timeout = (
        float(runtime.get("timeout_seconds"))
        if isinstance(runtime, dict) and runtime.get("timeout_seconds")
        else None
    )
    budget_timeout = (
        float(initial_budgets["max_wall_seconds"])
        if isinstance(initial_budgets, dict)
        and initial_budgets.get("max_wall_seconds")
        else None
    )
    timeout_seconds = (
        min(value for value in (plan_timeout, budget_timeout) if value is not None)
        if plan_timeout is not None or budget_timeout is not None
        else None
    )

    transition_execution_path(
        status_path,
        "running",
        actor="runner",
        reason="executor started",
        projection_source="runner",
        started_at=utc_now(),
    )
    secret_values = secret_values_from_argv(command)
    try:
        launch_command = command + ([prompt.decode("utf-8")] if interactive else [])
        process = spawn(
            ProcessRequest(
            argv=tuple(launch_command),
            cwd=workdir,
            timeout_seconds=timeout_seconds,
            create_process_group=not interactive,
            max_stdout_bytes=MAX_EXECUTOR_STDOUT_BYTES,
            max_stderr_bytes=MAX_EXECUTOR_STDERR_BYTES,
            environment=_child_environment(
                launch["worker_plan"].get("environment_allowlist", []),
                bridge_dir=Path(str(launch["paths"]["handoff_dir"])) / "control-intents",
                steering_dir=Path(str(launch["paths"]["handoff_dir"])) / "steering-inbox",
                ticket_id=launch.get("ticket"),
                pack_id=(
                    launch.get("pack", {}).get("id")
                    if isinstance(launch.get("pack"), dict)
                    else None
                ),
            ),
            secret_values=secret_values,
            interactive=interactive,
            )
        )
    except WorkflowError as exc:
        finished_at = utc_now()
        category = classify_failure(exit_code=127, stderr=str(exc))
        write_process_result(
            paths.process_result,
            {
                "schema": PROCESS_RESULT_SCHEMA,
                "argv": list(redact_argv(command, secret_values=secret_values)),
                "resolved_executable": None,
                "returncode": 127,
                "exit_code": 127,
                "signal": None,
                "timed_out": False,
                "cancelled": False,
                "stdout_truncated": False,
                "stderr_truncated": False,
                "stdout_bytes": 0,
                "stderr_bytes": 0,
                "duration_seconds": round(time.monotonic() - wall_started, 6),
                "error_category": category,
                "runner_pid": os.getpid(),
                "executor_pid": None,
                "recorded_at": finished_at,
            },
        )
        record_incident(
            run_dir,
            agent_run_id=str(launch["agent_run"]["id"]),
            category=category or "spawn_error",
            severity="high",
            summary="executor could not be started",
            evidence={"exit_code": 127, "error": str(exc)},
        )
        update_provenance(
            run_dir,
            finished_at=finished_at,
            exit_code=127,
        )
        capture_patch(workdir, run_dir, paths.patch)
        collect_completion(run_dir, workdir, secret_values=secret_values)
        collect_task_result(run_dir, workdir, secret_values=secret_values)
        current = read_status_path(status_path)
        final_status = {
            **_authoritative_projection(launch, run_dir, current),
            "status": "failed",
            "finished_at": finished_at,
            "exit_code": 127,
            "failure_category": category,
            "updated_at": finished_at,
        }
        provider = write_provider_evidence(
            run_dir, stream_format=stream_format, executor=provenance_initial.get("executor")
        )
        update_provenance(
            run_dir,
            provider_evidence={
                "path": "provider-evidence.json",
                "sha256": sha256_file(paths.provider_evidence),
                "usage_complete": provider["usage_complete"],
                "capture_complete": provider["capture_complete"],
            },
            usage=provider["aggregate"],
        )
        seal_failure = _seal_terminal_run(
            run_dir,
            launch,
            final_status,
            elapsed_seconds=time.monotonic() - wall_started,
            seal_failure_reason="executor spawn evidence could not be sealed",
            terminal_reason="executor failed to start and terminal evidence sealed",
            seal_failure_exit=127,
        )
        return seal_failure or 127
    if not interactive:
        assert process.process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None
        process.process.stdin.write(prompt)
        process.process.stdin.close()

    def forward_signal(signum: int, _frame: Any) -> None:
        if process.poll() is None:
            process.send_signal(signum)

    signal.signal(signal.SIGINT, forward_signal)
    signal.signal(signal.SIGTERM, forward_signal)

    def stdout_pump() -> None:
        nonlocal usage, provider_event_bytes, provider_capture_exceeded
        nonlocal first_output_at, last_normalized_text
        try:
            with output_path.open("ab") as output, events_path.open("ab") as events:
                for raw in iter(process.stdout.readline, b""):
                    if first_output_at is None:
                        first_output_at = utc_now()
                    if stream_format == "text":
                        with lock:
                            _write_bytes(output, raw)
                            _mirror_output(sys.stdout.buffer, raw)
                    else:
                        if provider_event_bytes + len(raw) <= MAX_PROVIDER_EVENT_BYTES:
                            _write_bytes(events, raw)
                            provider_event_bytes += len(raw)
                        else:
                            provider_capture_exceeded = True
                        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                        event = parse_event(line, stream_format)
                        if event is None:
                            with lock:
                                _write_bytes(output, raw)
                                _mirror_output(sys.stdout.buffer, raw)
                            continue
                        usage_value = usage_update(event)
                        if usage_value is not None:
                            payload, mode = usage_value
                            usage = accumulate_usage(usage, payload, mode=mode)
                        for text in event_text(event, stream_format):
                            normalized = text.rstrip()
                            if normalized == last_normalized_text:
                                continue
                            last_normalized_text = normalized
                            with lock:
                                visible = (normalized + "\n").encode()
                                _write_bytes(output, visible)
                                _mirror_output(sys.stdout.buffer, visible)
        except Exception as exc:  # pragma: no cover - defensive thread boundary
            pump_errors.append(redact_text(f"stdout: {exc}", secret_values))

    def stderr_pump() -> None:
        nonlocal first_output_at
        try:
            with output_path.open("ab") as output, stderr_path.open("ab") as errors:
                for raw in iter(process.stderr.readline, b""):
                    if first_output_at is None:
                        first_output_at = utc_now()
                    _write_bytes(errors, raw)
                    with lock:
                        _write_bytes(output, raw)
                        _mirror_output(sys.stderr.buffer, raw)
        except Exception as exc:  # pragma: no cover - defensive thread boundary
            pump_errors.append(redact_text(f"stderr: {exc}", secret_values))

    threads = [] if interactive else [
        threading.Thread(target=stdout_pump, daemon=True),
        threading.Thread(target=stderr_pump, daemon=True),
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout_seconds if timeout_seconds else None
    timed_out = False
    completed_by_child = False
    last_health_at: float | None = None
    while True:
        now = time.monotonic()
        active = process.poll() is None
        if last_health_at is None or now - last_health_at >= max(0.1, heartbeat_seconds):
            atomic_write_json(
                heartbeat_path,
                {
                    "schema": "agent-workflow/heartbeat/v2",
                    "runner_pid": os.getpid(),
                    "executor_pid": process.pid,
                    "at": utc_now(),
                },
            )
            record_health_sample(
                run_dir,
                agent_run_id=str(launch["agent_run"]["id"]),
                runner_pid=os.getpid(),
                executor_pid=process.pid,
            )
            last_health_at = now
        # Drain child intents before acting on executor exit. A cooperative
        # child can write its terminal intent and exit between polling cycles;
        # rejecting that already-present intent would leave the sealed run
        # completed while durable assignment state incorrectly remains busy.
        # The later active=False drain still rejects intents that arrive only
        # after this exit boundary has been observed.
        if _drain_control_bridge(
            run_dir, active=active, allow_terminal_at_exit=not active
        ):
            # A valid terminal handoff is authoritative completion, not an
            # operator cancellation. Close the live interactive executor when
            # it is still present so the runner can seal the run and retire
            # the worker cleanly.
            completed_by_child = True
            if active:
                process.close_after_completion()
            return_code = 0
            break
        if not active:
            return_code = process.returncode
            if return_code is None:
                return_code = 0
            break
        # Control delivery is intentionally more responsive than observability
        # sampling so short-lived cooperative executors can consume steering.
        deliver_pending(run_dir, active=True)
        wait_seconds = min(max(0.1, heartbeat_seconds), CONTROL_POLL_SECONDS)
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                process.cancel(timed_out=True)
                return_code = process.poll()
                if return_code is None:
                    return_code = process.process.returncode or 124
                break
            wait_seconds = min(wait_seconds, remaining)
        waited = process.wait_for(wait_seconds)
        if waited is not None:
            # The child may emit its final control intent immediately before
            # exiting. Consume any intent already present at the observed exit
            # boundary before treating the process return code as completion.
            if _drain_control_bridge(
                run_dir, active=False, allow_terminal_at_exit=True
            ):
                completed_by_child = True
                return_code = 0
            else:
                return_code = waited
            break
    for thread in threads:
        thread.join(timeout=5)
    # The child may write its final intent immediately before exiting. Drain it
    # once while completion is still being finalized; later arrivals are never
    # consumed after the terminal receipt is sealed.
    _drain_control_bridge(run_dir, active=False)
    deliver_pending(run_dir, active=False)
    if any(thread.is_alive() for thread in threads):
        pump_errors.append("stream drain deadline exceeded")
        try:
            process.cancel()
        except OSError:
            pass
        process.close_streams()
        for thread in threads:
            thread.join(timeout=2)
        if any(thread.is_alive() for thread in threads):
            pump_errors.append("stream pump did not stop after descriptor close")
    process_result = process.result()
    write_process_result(
        paths.process_result,
        {
            "schema": PROCESS_RESULT_SCHEMA,
            **process_result.as_dict(include_output=False),
            "completion_terminated": completed_by_child,
            "runner_pid": os.getpid(),
            "executor_pid": process.pid,
            "recorded_at": utc_now(),
        },
    )
    if process_result.stdout_truncated:
        pump_errors.append("stdout capture limit exceeded; output truncated")
    if process_result.stderr_truncated:
        pump_errors.append("stderr capture limit exceeded; output truncated")
    if completed_by_child:
        return_code = 0
    if pump_errors:
        return_code = return_code or 1

    completion_collection = collect_completion(
        run_dir, workdir, secret_values=secret_values
    )
    if completion_collection["validation_status"] != "valid":
        pump_errors.append(
            "completion: "
            + "; ".join(completion_collection.get("validation_errors", []))
        )
        return_code = return_code or 1
    collect_task_result(run_dir, workdir, secret_values=secret_values)

    if isinstance(runtime, dict):
        try:
            scope_data = runtime.get("scope", {})
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
                receipt_dir=paths.scope,
            )
            commands = runtime.get("acceptance_commands", [])
            if commands or runtime.get("native_job_binding_sha256"):
                collect_commands(
                    workdir,
                    specs_from_data(commands),
                    phase="post",
                    receipt_dir=paths.collections,
                )
        except Exception as exc:
            pump_errors.append(f"collectors: {exc}")
            return_code = return_code or 1

    provider = write_provider_evidence(
        run_dir,
        capture_exceeded=provider_capture_exceeded,
        stream_format=stream_format,
        executor=(
            str(provenance_initial["executor"])
            if provenance_initial.get("executor")
            else None
        ),
    )
    usage = provider["aggregate"]
    if provider_capture_exceeded:
        pump_errors.append("provider evidence capture limit exceeded")
        return_code = return_code or 1

    executor_status = (
        "completed"
        if return_code == 0
        else "interrupted"
        if return_code in {130, 143, -2, -15}
        else "failed"
    )
    wall_seconds = time.monotonic() - wall_started
    policy = evaluate_budgets(
        usage if isinstance(usage, dict) else None,
        provenance_initial.get("budgets")
        if isinstance(provenance_initial.get("budgets"), dict)
        else None,
        wall_seconds=wall_seconds,
    )
    if timed_out:
        executor_status = "failed"
        return_code = 124
    finished_at = utc_now()
    update_provenance(
        run_dir,
        first_output_at=first_output_at,
        finished_at=finished_at,
        exit_code=return_code,
        usage=usage,
        provider_evidence={
            "path": "provider-evidence.json",
            "sha256": sha256_file(paths.provider_evidence),
            "usage_complete": provider["usage_complete"],
            "capture_complete": provider["capture_complete"],
        },
    )
    current = read_status_path(status_path)
    diagnostic_stderr = stderr_path.read_text(
        encoding="utf-8", errors="replace"
    )[-8192:]
    failure_category = (
        "timeout"
        if timed_out
        else classify_failure(
            exit_code=return_code,
            stderr=diagnostic_stderr,
            errors=pump_errors,
        )
    )
    final_status = {
        **_authoritative_projection(launch, run_dir, current),
        "status": executor_status,
        "executor_result": executor_status,
        "completion_result": current.get("completion_validation_status"),
        "policy_result": policy["policy_result"],
        "policy_failures": policy["policy_failures"],
        "policy_failure_category": policy["policy_failure_category"],
        "acceptance_eligible": bool(
            executor_status == "completed"
            and current.get("completion_validation_status") == "valid"
            and policy["policy_result"] != "failed"
        ),
        "finished_at": finished_at,
        "exit_code": return_code,
        "pump_errors": pump_errors,
        "failure_category": failure_category,
        "stdout_bytes": process_result.stdout_bytes,
        "stderr_bytes": process_result.stderr_bytes,
        "stdout_truncated": process_result.stdout_truncated,
        "stderr_truncated": process_result.stderr_truncated,
        "wall_seconds": round(wall_seconds, 6),
        "updated_at": finished_at,
    }
    capture_patch(workdir, run_dir, paths.patch)
    record_health_sample(
        run_dir,
        agent_run_id=str(launch["agent_run"]["id"]),
        runner_pid=os.getpid(),
        executor_pid=process.pid,
    )
    if failure_category:
        record_incident(
            run_dir,
            agent_run_id=str(launch["agent_run"]["id"]),
            category=failure_category,
            severity="high",
            summary="executor finished with a classified failure",
            evidence={
                "exit_code": return_code,
                "pump_errors": pump_errors,
                "stdout_truncated": process_result.stdout_truncated,
                "stderr_truncated": process_result.stderr_truncated,
            },
        )
    if policy["policy_result"] == "failed":
        record_incident(
            run_dir,
            agent_run_id=str(launch["agent_run"]["id"]),
            category="budget_policy_failed",
            severity="medium",
            summary="executor completed with one or more budget-policy violations",
            evidence={
                "executor_result": executor_status,
                "policy_failures": policy["policy_failures"],
            },
        )
    seal_failure = _seal_terminal_run(
        run_dir,
        launch,
        final_status,
        elapsed_seconds=wall_seconds,
        seal_failure_reason="terminal evidence sealing failed",
        terminal_reason="executor terminal evidence sealed",
        seal_failure_exit=return_code or 1,
    )
    return seal_failure if seal_failure is not None else return_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--command-b64")
    parser.add_argument("--non-interactive", action="store_true")
    args = parser.parse_args(argv)
    command: list[str] = []
    if args.command_b64 and not args.non_interactive:
        try:
            decoded = base64.b64decode(args.command_b64, validate=True)
            value = json.loads(decoded.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"invalid encoded launch command: {exc}") from exc
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise WorkflowError("encoded launch command must be a string array")
        command = value
    return execute(
        args.run_dir,
        args.run_dir,
        command,
        stream_format="text",
        interactive=False,
        force_noninteractive=args.non_interactive,
    )


if __name__ == "__main__":
    raise SystemExit(main())
