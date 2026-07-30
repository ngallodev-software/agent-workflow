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

from .errors import WorkflowError
from .contracts import read_launch_contract
from .completion import substantive_completion_errors
from .events import append_lifecycle_event
from .diagnostics import classify_failure
from .eval.commands import collect_commands, specs_from_data
from .eval.scope import ScopePolicy, collect_scope
from .executors import accumulate_usage, event_text, parse_event, usage_update
from .receipts import final_receipt_sha256, make_read_only, seal_run, update_provenance
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
    redact_bytes,
    redact_text,
    run_bytes,
    secret_values_from_argv,
    spawn,
)
from .util import atomic_write_json, sha256_file, utc_now
from .path import read_regular_file


MAX_COMPLETION_HANDOFF_BYTES = 1024 * 1024
MAX_EXECUTOR_STDOUT_BYTES = 16 * 1024 * 1024
MAX_EXECUTOR_STDERR_BYTES = 16 * 1024 * 1024
_RUNTIME_ENVIRONMENT = (
    "AGENT_WORKFLOW_SESSION_ID",
    "AGENT_WORKFLOW_TICKET_ID",
    "AGENT_WORKFLOW_PACK_ID",
    "AGENT_WORKFLOW_PROMPT_SOURCE",
    "AGENT_WORKFLOW_HANDOFF_DIR",
    "AGENT_WORKFLOW_PROMPT_PACK_ROOT",
    "AGENT_WORKFLOW_COMMAND_CATALOG",
    "AGENT_WORKFLOW_COMMAND_CARD",
    "AGENT_WORKFLOW_CLI",
    "AGENT_WORKFLOW_TMUX_SESSION",
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


def _drain_control_bridge(run_dir: Path, *, active: bool) -> None:
    """Consume bounded child intents using host-owned state and tmux authority."""
    launch = read_launch_contract(run_dir / "launch-contract.json")
    session_id = str(launch["session"]["id"])
    handoff = Path(str(launch["paths"].get("handoff_dir", ""))).resolve()
    bridge = handoff / "control-intents"
    if bridge.parent != handoff or bridge.is_symlink() or not bridge.is_dir():
        return
    evidence_path = run_dir / "control-intents.jsonl"
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
            if value.get("session_id") != session_id or value.get("digest") != digest:
                raise WorkflowError("control intent identity or digest mismatch")
            if not active:
                raise WorkflowError("request arrived after executor exit")
            intent_kind = str(value["kind"])
            acknowledgement_outcome = value.get("outcome", "applied")
            if intent_kind == "ack" and acknowledgement_outcome not in {"applied", "rejected"}:
                raise WorkflowError("invalid acknowledgement outcome")
            if intent_kind != "ack" and value.get("outcome") is not None:
                raise WorkflowError("only acknowledgement intents may include outcome")
            if intent_kind == "task_complete":
                apply_bridged_completion(
                    run_dir,
                    session_id,
                    actor=str(value["actor"]),
                    summary=str(value["content"]),
                )
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
                        run_dir, session_id=session_id, direction="child_to_parent",
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
                    run_dir, session_id=session_id, direction="child_to_parent",
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
                run_dir, session_id=session_id, direction="child_to_parent", kind="error",
                actor="agent-workflow-host",
                content=json.dumps({"outcome": outcome, "request_id": request_id, "reason": reason}, sort_keys=True),
                correlation_id=correlation_id if isinstance(correlation_id, str) else None,
            )
        record(source.name, request_id, intent.get("sequence") if intent else None, outcome, reason)
        if intent and isinstance(intent.get("sequence"), int):
            processed_sequences.add(intent["sequence"])


def _read_handoff_completion(path: Path) -> bytes:
    """Read one bounded regular file without following an executor-controlled link."""
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise WorkflowError(f"cannot inspect completion handoff: {exc}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise WorkflowError("completion handoff must be a regular non-symlink file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WorkflowError(f"cannot open completion handoff safely: {exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError("completion handoff must be a regular file")
        if info.st_size > MAX_COMPLETION_HANDOFF_BYTES:
            raise WorkflowError(
                f"completion handoff exceeds {MAX_COMPLETION_HANDOFF_BYTES} bytes"
            )
        chunks: list[bytes] = []
        remaining = MAX_COMPLETION_HANDOFF_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if len(data) > MAX_COMPLETION_HANDOFF_BYTES:
            raise WorkflowError(
                f"completion handoff exceeds {MAX_COMPLETION_HANDOFF_BYTES} bytes"
            )
        return data
    finally:
        os.close(descriptor)


def _require_real_handoff_dir(handoff: Path, workdir: Path) -> None:
    try:
        relative = handoff.relative_to(workdir)
    except ValueError as exc:
        raise WorkflowError("completion handoff escapes worktree") from exc
    current = workdir
    for component in relative.parts:
        current = current / component
        try:
            mode = current.lstat().st_mode
        except OSError as exc:
            raise WorkflowError(f"cannot inspect completion handoff directory: {exc}") from exc
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise WorkflowError("completion handoff directory must not contain symlinks")


def _collect_completion(
    run_dir: Path, workdir: Path, *, secret_values: tuple[str, ...] = ()
) -> dict[str, Any]:
    """Collect native executor evidence before downstream collectors and sealing."""
    launch = read_launch_contract(run_dir / "launch-contract.json")
    session_id = str(launch["session"]["id"])
    contract_workdir = Path(str(launch["worktree"]["path"]))
    handoff_value = launch["paths"].get("handoff_dir")
    handoff = Path(handoff_value) if isinstance(handoff_value, str) else None
    source = handoff / "completion.json" if handoff is not None else None
    receipt: dict[str, Any] = {
        "schema": "agent-workflow/completion-collection/v1",
        "session_id": session_id,
        "adapter": "native",
        "adapter_version": "1",
        "source_path": str(source) if source is not None else None,
        "source_sha256": None,
        "canonical_mapping": None,
        "canonical_sha256": None,
        "validation_status": "missing",
        "validation_errors": [],
        "collected_at": utc_now(),
        "stored_path": None,
    }
    try:
        if handoff is None:
            raise FileNotFoundError("launch has no completion handoff")
        _require_real_handoff_dir(handoff, contract_workdir)
        assert source is not None
        data = redact_bytes(_read_handoff_completion(source), secret_values)
    except FileNotFoundError as exc:
        receipt["validation_errors"] = [str(exc)]
    except WorkflowError as exc:
        receipt["validation_status"] = "invalid"
        receipt["validation_errors"] = [str(exc)]
    else:
        receipt["source_sha256"] = hashlib.sha256(data).hexdigest()
        try:
            value = json.loads(data.decode("utf-8"))
            if not isinstance(value, dict):
                raise WorkflowError("completion handoff must be a JSON object")
            if value.get("session_id") != session_id:
                raise WorkflowError("completion handoff session_id does not match run")
            from .contracts import validate_instance
            validate_instance(value, "agent-workflow/completion/v1", artifact=str(source))
            semantic_errors = substantive_completion_errors(
                value,
                session_id=session_id,
                ticket_id=launch.get("ticket"),
                pack_id=(
                    launch.get("pack", {}).get("id")
                    if isinstance(launch.get("pack"), dict)
                    else None
                ),
            )
            if semantic_errors:
                raise WorkflowError("; ".join(semantic_errors))
            completion_path = run_dir / "completion.json"
            temporary = completion_path.with_name(f".{completion_path.name}.handoff")
            temporary.write_bytes(data)
            os.replace(temporary, completion_path)
            receipt["stored_path"] = "completion.json"
            receipt["canonical_mapping"] = "identity"
            receipt["canonical_sha256"] = hashlib.sha256(completion_path.read_bytes()).hexdigest()
            receipt["validation_status"] = "valid"
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
            receipt["validation_status"] = "invalid"
            receipt["validation_errors"] = [str(exc)]
    receipt_path = run_dir / "collections" / "completion.json"
    atomic_write_json(receipt_path, receipt)
    _update_status(
        run_dir / "status.json",
        completion_collection_path=str(receipt_path),
        completion_validation_status=receipt["validation_status"],
    )
    return receipt


def _collect_task_result(
    run_dir: Path, workdir: Path, *, secret_values: tuple[str, ...] = ()
) -> dict[str, Any] | None:
    """Collect and validate an optional ticket-specific structured result."""
    launch = read_launch_contract(run_dir / "launch-contract.json")
    session_id = str(launch["session"]["id"])
    contract_workdir = Path(str(launch["worktree"]["path"]))
    contract = launch["paths"].get("result_contract")
    if not isinstance(contract, dict):
        return None
    required = bool(contract.get("required", True))
    schema_rel = contract.get("schema")
    pack_root_value = launch["pack"].get("root")
    handoff_value = launch["paths"].get("handoff_dir")
    handoff = Path(handoff_value) if isinstance(handoff_value, str) else None
    source = handoff / "result.json" if handoff is not None else None
    receipt: dict[str, Any] = {
        "schema": "agent-workflow/task-result-collection/v1",
        "session_id": session_id,
        "required": required,
        "schema_path": str(schema_rel) if isinstance(schema_rel, str) else None,
        "source_path": str(source) if source is not None else None,
        "source_sha256": None,
        "stored_path": None,
        "stored_sha256": None,
        "validation_status": "missing",
        "validation_errors": [],
        "collected_at": utc_now(),
    }
    try:
        if handoff is None:
            raise FileNotFoundError("launch has no completion handoff")
        _require_real_handoff_dir(handoff, contract_workdir)
        if not isinstance(schema_rel, str) or not schema_rel:
            raise WorkflowError("result contract schema path is missing")
        if not isinstance(pack_root_value, str):
            raise WorkflowError("result contract has no prompt pack root")
        pack_root = Path(pack_root_value)
        schema_path = pack_root / schema_rel
        try:
            schema_path.relative_to(pack_root)
        except ValueError as exc:
            raise WorkflowError("result contract schema escapes prompt pack root") from exc
        schema_read = read_regular_file(schema_path)
        expected_schema = launch["schemas"].get("task_result")
        if not isinstance(expected_schema, dict) or schema_read.sha256 != expected_schema.get("sha256"):
            raise WorkflowError("result contract schema changed after launch")
        assert source is not None
        data = redact_bytes(_read_handoff_completion(source), secret_values)
        value = json.loads(data.decode("utf-8"))
        schema_value = json.loads(schema_read.data.decode("utf-8"))
        if not isinstance(value, dict):
            raise WorkflowError("task result must be a JSON object")
        if not isinstance(schema_value, dict):
            raise WorkflowError("task result schema must be a JSON object")
        try:
            import jsonschema
        except ImportError as exc:
            raise WorkflowError("task result validation requires jsonschema") from exc
        errors = sorted(
            jsonschema.Draft202012Validator(schema_value).iter_errors(value),
            key=lambda item: list(item.path),
        )
        if errors:
            details = []
            for error in errors[:20]:
                location = ".".join(str(part) for part in error.absolute_path) or "$"
                details.append(f"{location}: {error.message}")
            raise WorkflowError("invalid task result: " + "; ".join(details))
        receipt["source_sha256"] = hashlib.sha256(data).hexdigest()
        stored = run_dir / "result.json"
        temporary = stored.with_name(f".{stored.name}.handoff")
        temporary.write_bytes(data)
        os.replace(temporary, stored)
        receipt["stored_path"] = "result.json"
        receipt["stored_sha256"] = hashlib.sha256(stored.read_bytes()).hexdigest()
        receipt["validation_status"] = "valid"
    except FileNotFoundError as exc:
        receipt["validation_errors"] = [str(exc)]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
        receipt["validation_status"] = "invalid"
        receipt["validation_errors"] = [str(exc)]
    receipt_path = run_dir / "collections" / "task-result.json"
    atomic_write_json(receipt_path, receipt)
    _update_status(
        run_dir / "status.json",
        task_result_collection_path=str(receipt_path),
        task_result_validation_status=receipt["validation_status"],
    )
    return receipt


def _authoritative_projection(
    launch: dict[str, Any], run_dir: Path, current: dict[str, Any]
) -> dict[str, Any]:
    """Overlay only launch-bound identity and paths onto the status projection."""
    session = launch["session"]
    worktree = launch["worktree"]
    command = launch["command_plan"]
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
        }
    }
    projected.update(
        {
            "schema": "agent-workflow/session-status/v2",
            "session_id": session["id"],
            "ticket_id": launch.get("ticket"),
            "agent_name": session.get("agent_name"),
            "agent_class": session.get("agent_class"),
            "tier": session.get("tier"),
            "retry_of": session.get("retry_of"),
            "created_at": session["created_at"],
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
            "command_path": str(run_dir / "command.json"),
            "handoff_dir": paths["handoff_dir"],
            "provenance_path": str(run_dir / "run-provenance.json"),
            "events_path": str(run_dir / "executor-events.jsonl"),
            "stderr_path": str(run_dir / "executor-stderr.log"),
            "source_baseline_path": str(run_dir / launch["source_baseline"]["path"]),
            "launch_contract_path": str(run_dir / "launch-contract.json"),
            "executor": command.get("executor"),
            "model": command.get("model"),
            "interactive": command["interactive"],
            "executor_interactive": command["executor_interactive"],
            "evaluation_path": evaluation.get("path"),
            "disposition": None,
        }
    )
    return projected


def _read_status(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read runner status {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"runner status must be an object: {path}")
    return value


def _update_status(path: Path, **changes: Any) -> dict[str, Any]:
    value = _read_status(path)
    if "status" in changes and changes["status"] != value.get("status"):
        append_lifecycle_event(
            path.parent,
            dimension="execution",
            prior=value.get("status"),
            new=changes["status"],
            actor="runner",
            reason="executor state changed",
        )
    value.update(changes)
    value["updated_at"] = utc_now()
    atomic_write_json(path, value)
    return value


def _write_bytes(stream: BinaryIO, data: bytes) -> None:
    stream.write(data)
    stream.flush()


def _mirror_terminal(stream: BinaryIO, data: bytes) -> None:
    """Best-effort pane output; durable run artifacts remain authoritative."""
    try:
        _write_bytes(stream, data)
    except (BrokenPipeError, OSError, ValueError):
        pass


def _capture_patch(workdir: Path, run_dir: Path, path: Path) -> None:
    baseline = None
    try:
        source = json.loads(
            (run_dir / "source-baseline.json").read_text(encoding="utf-8")
        )
        baseline = source.get("components", {}).get("primary", {}).get("head")
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    result = run_bytes(
        [
            "git", "-C", str(workdir), "diff", "--binary", "--full-index",
            str(baseline or "HEAD"),
        ],
        check=False,
        timeout_seconds=60,
        max_stdout_bytes=MAX_EXECUTOR_STDOUT_BYTES,
        max_stderr_bytes=64 * 1024,
    )
    patch = bytearray(result.stdout if result.returncode == 0 else b"")
    untracked = run_bytes(
        ["git", "-C", str(workdir), "ls-files", "--others", "--exclude-standard", "-z"],
        check=False,
        timeout_seconds=60,
        max_stdout_bytes=MAX_EXECUTOR_STDOUT_BYTES,
        max_stderr_bytes=64 * 1024,
    )
    if untracked.returncode == 0:
        for raw in untracked.stdout.split(b"\0"):
            if not raw:
                continue
            relative = raw.decode("utf-8", errors="surrogateescape")
            addition = run_bytes(
                [
                    "git",
                    "-C",
                    str(workdir),
                    "diff",
                    "--no-index",
                    "--binary",
                    "--",
                    "/dev/null",
                    relative,
                ],
                check=False,
                timeout_seconds=60,
                max_stdout_bytes=MAX_EXECUTOR_STDOUT_BYTES,
                max_stderr_bytes=64 * 1024,
            )
            if addition.returncode in {0, 1}:
                patch.extend(addition.stdout)
    path.write_bytes(patch)


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
    names.difference_update({"TMUX", "TMUX_PANE", "XDG_STATE_HOME"})
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


def execute(
    run_dir: Path,
    workdir: Path,
    command: list[str],
    *,
    stream_format: str,
    interactive: bool = False,
    heartbeat_seconds: float = 5.0,
) -> int:
    run_dir = run_dir.resolve()
    launch = read_launch_contract(run_dir / "launch-contract.json")
    contract_workdir = Path(str(launch["worktree"]["path"]))
    workdir = contract_workdir
    command_plan = launch["command_plan"]
    contract_command = [str(value) for value in command_plan["argv"]]
    if command:
        encoded = json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        actual_digest = hashlib.sha256(encoded).hexdigest()
        expected_digest = command_plan.get("command_sha256")
        if not isinstance(expected_digest, str) or actual_digest != expected_digest:
            raise WorkflowError("runtime command does not match immutable launch contract")
    else:
        # Direct callers and legacy wrappers can still execute a redacted
        # contract command; generated runners always provide the bound argv.
        command = contract_command
    stream_format = str(command_plan["stream_format"])
    interactive = bool(command_plan["executor_interactive"])
    status_path = run_dir / "status.json"
    prompt_read = read_regular_file(run_dir / launch["prompt"]["launch_stored"])
    if prompt_read.sha256 != launch["prompt"]["launch_sha256"]:
        raise WorkflowError("launch prompt changed after contract creation")
    prompt = prompt_read.data
    output_path = run_dir / "output.log"
    events_path = run_dir / "executor-events.jsonl"
    stderr_path = run_dir / "executor-stderr.log"
    heartbeat_path = run_dir / "heartbeat.json"
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
    persisted_runtime_path = run_dir / "evaluation-runtime.json"
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
        (run_dir / "run-provenance.json").read_text(encoding="utf-8")
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

    _update_status(status_path, status="running", started_at=utc_now())
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
                launch["command_plan"].get("environment_allowlist", []),
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
        update_provenance(
            run_dir,
            finished_at=finished_at,
            exit_code=127,
        )
        _capture_patch(workdir, run_dir, run_dir / "patch.diff")
        _collect_completion(run_dir, workdir, secret_values=secret_values)
        _collect_task_result(run_dir, workdir, secret_values=secret_values)
        current = _read_status(status_path)
        final_status = {
            **_authoritative_projection(launch, run_dir, current),
            "status": "failed",
            "finished_at": finished_at,
            "exit_code": 127,
            "failure_category": classify_failure(
                exit_code=127, stderr=str(exc)
            ),
            "updated_at": finished_at,
        }
        atomic_write_json(run_dir / "final-status.json", final_status)
        provider = write_provider_evidence(
            run_dir, stream_format=stream_format, executor=provenance_initial.get("executor")
        )
        update_provenance(
            run_dir,
            provider_evidence={
                "path": "provider-evidence.json",
                "sha256": sha256_file(run_dir / "provider-evidence.json"),
                "usage_complete": provider["usage_complete"],
                "capture_complete": provider["capture_complete"],
            },
            usage=provider["aggregate"],
        )
        write_execution_evidence(run_dir, elapsed_seconds=time.monotonic() - wall_started)
        receipt = seal_run(run_dir, session_id=str(launch["session"]["id"]))
        receipt_hash = final_receipt_sha256(run_dir)
        _update_status(
            status_path,
            **{
                key: value
                for key, value in final_status.items()
                if key not in {"final_receipt_path", "final_receipt_sha256"}
            },
            final_receipt_path=str(run_dir / "final-receipt.json"),
            final_receipt_sha256=receipt_hash,
            sealed_artifact_count=len(receipt["artifacts"]),
        )
        make_read_only(run_dir)
        return 127
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
                            _mirror_terminal(sys.stdout.buffer, raw)
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
                                _mirror_terminal(sys.stdout.buffer, raw)
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
                                _mirror_terminal(sys.stdout.buffer, visible)
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
                        _mirror_terminal(sys.stderr.buffer, raw)
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
    while True:
        atomic_write_json(
            heartbeat_path,
            {
                "schema": "agent-workflow/heartbeat/v1",
                "pid": process.pid,
                "at": utc_now(),
            },
        )
        active = process.poll() is None
        deliver_pending(run_dir, active=active)
        _drain_control_bridge(run_dir, active=active)
        wait_seconds = max(0.1, heartbeat_seconds)
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
            return_code = waited
            break
    for thread in threads:
        thread.join(timeout=5)
    # The child may write its final intent immediately before exiting. Drain it
    # once while completion is still being finalized; later arrivals are never
    # consumed after the terminal receipt is sealed.
    _drain_control_bridge(run_dir, active=True)
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
    if pump_errors:
        return_code = return_code or 1

    completion_collection = _collect_completion(
        run_dir, workdir, secret_values=secret_values
    )
    if completion_collection["validation_status"] != "valid":
        pump_errors.append(
            "completion: "
            + "; ".join(completion_collection.get("validation_errors", []))
        )
        return_code = return_code or 1
    _collect_task_result(run_dir, workdir, secret_values=secret_values)

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
                receipt_dir=run_dir / "scope",
            )
            commands = runtime.get("acceptance_commands", [])
            if commands or runtime.get("native_job_binding_sha256"):
                collect_commands(
                    workdir,
                    specs_from_data(commands),
                    phase="post",
                    receipt_dir=run_dir / "collections",
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

    terminal_status = (
        "completed"
        if return_code == 0
        else "interrupted"
        if return_code in {130, 143}
        else "failed"
    )
    budget_exceeded: list[str] = []
    budgets = provenance_initial.get("budgets", {})
    if isinstance(usage, dict) and isinstance(budgets, dict):
        for usage_key, budget_key in (
            ("input_tokens", "max_input_tokens"),
            ("output_tokens", "max_output_tokens"),
        ):
            used = usage.get(usage_key)
            limit = budgets.get(budget_key)
            if isinstance(used, (int, float)) and isinstance(limit, (int, float)):
                if used > limit:
                    budget_exceeded.append(f"{usage_key}:{used}>{limit}")
        cost = usage.get("provider_billed_cost")
        if cost is None:
            cost = usage.get("local_estimated_cost")
        if cost is None:
            cost = usage.get("cost", usage.get("total_cost"))
        max_cost = budgets.get("max_cost")
        if isinstance(cost, (int, float)) and isinstance(max_cost, (int, float)):
            if cost > max_cost:
                budget_exceeded.append(f"cost:{cost}>{max_cost}")
        expected_currency = budgets.get("currency")
        actual_currency = usage.get("currency")
        if expected_currency and actual_currency and expected_currency != actual_currency:
            budget_exceeded.append(
                f"currency:{actual_currency}!={expected_currency}"
            )
    wall_seconds = time.monotonic() - wall_started
    if isinstance(budgets, dict) and isinstance(
        budgets.get("max_wall_seconds"), (int, float)
    ):
        if wall_seconds > budgets["max_wall_seconds"]:
            budget_exceeded.append(
                f"wall_seconds:{wall_seconds:.6f}>{budgets['max_wall_seconds']}"
            )
    if budget_exceeded:
        terminal_status = "failed"
        return_code = return_code or 1
    if timed_out:
        terminal_status = "failed"
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
            "sha256": sha256_file(run_dir / "provider-evidence.json"),
            "usage_complete": provider["usage_complete"],
            "capture_complete": provider["capture_complete"],
        },
    )
    current = _read_status(status_path)
    final_status = {
        **_authoritative_projection(launch, run_dir, current),
        "status": terminal_status,
        "finished_at": finished_at,
        "exit_code": return_code,
        "pump_errors": pump_errors,
        "failure_category": (
            "budget_exhausted"
            if budget_exceeded
            else "timeout"
            if timed_out
            else classify_failure(
                exit_code=return_code,
                stderr=stderr_path.read_text(encoding="utf-8", errors="replace")[-8192:],
                errors=pump_errors,
            )
        ),
        "budget_exceeded": budget_exceeded,
        "wall_seconds": round(wall_seconds, 6),
        "updated_at": finished_at,
    }
    _capture_patch(workdir, run_dir, run_dir / "patch.diff")
    atomic_write_json(run_dir / "final-status.json", final_status)
    write_execution_evidence(run_dir, elapsed_seconds=wall_seconds)
    try:
        receipt = seal_run(run_dir, session_id=str(launch["session"]["id"]))
        receipt_hash = final_receipt_sha256(run_dir)
        _update_status(
            status_path,
            **{
                **final_status,
                "final_receipt_path": str(run_dir / "final-receipt.json"),
                "final_receipt_sha256": receipt_hash,
                "sealed_artifact_count": len(receipt["artifacts"]),
            },
        )
        make_read_only(run_dir)
    except Exception as exc:
        _update_status(
            status_path,
            status="failed",
            finished_at=utc_now(),
            exit_code=return_code or 1,
            failure_category="seal_failed",
            seal_error=str(exc),
        )
        return return_code or 1
    return return_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    # These legacy options are accepted only so an old shell wrapper fails at
    # the immutable-contract boundary rather than selecting new authority.
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--stream-format")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--command-b64")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command: list[str] = []
    if args.command_b64:
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
        args.workdir or args.run_dir,
        command,
        stream_format=args.stream_format or "text",
        interactive=args.interactive,
    )


if __name__ == "__main__":
    raise SystemExit(main())
