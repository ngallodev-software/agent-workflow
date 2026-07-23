from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import stat
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, BinaryIO

from .errors import WorkflowError
from .events import append_lifecycle_event
from .diagnostics import classify_failure
from .eval.commands import collect_commands, specs_from_data
from .eval.scope import ScopePolicy, collect_scope
from .executors import event_text, event_usage, parse_event
from .receipts import make_read_only, seal_run, update_provenance
from .util import atomic_write_json, sha256_file, utc_now


MAX_COMPLETION_HANDOFF_BYTES = 1024 * 1024


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


def _collect_completion(run_dir: Path, workdir: Path) -> dict[str, Any]:
    """Collect native executor evidence before downstream collectors and sealing."""
    status = _read_status(run_dir / "status.json")
    handoff_value = status.get("handoff_dir")
    handoff = Path(handoff_value) if isinstance(handoff_value, str) else None
    source = handoff / "completion.json" if handoff is not None else None
    adapter = str(status.get("pack_adapter") or "native")
    receipt: dict[str, Any] = {
        "schema": "agent-workflow/completion-collection/v1",
        "session_id": str(status["session_id"]),
        "adapter": adapter,
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
        _require_real_handoff_dir(handoff, workdir)
        assert source is not None
        data = _read_handoff_completion(source)
    except FileNotFoundError as exc:
        receipt["validation_errors"] = [str(exc)]
    except WorkflowError as exc:
        receipt["validation_status"] = "invalid"
        receipt["validation_errors"] = [str(exc)]
    else:
        receipt["source_sha256"] = hashlib.sha256(data).hexdigest()
        try:
            if adapter == "tax-machine":
                from .tax_machine import discover, validate_completion
                root_value = status.get("prompt_pack_root")
                pack = discover(Path(root_value)) if isinstance(root_value, str) else None
                if pack is None:
                    raise WorkflowError("Tax Machine pack cannot be rediscovered for collection")
                validate_completion(pack, data)
                stored = run_dir / "external" / "tax-machine" / "completion.json"
                stored.parent.mkdir(parents=True, exist_ok=True)
                stored.write_bytes(data)
                stored.chmod(0o444)
                receipt["stored_path"] = str(stored.relative_to(run_dir))
                # The current Tax contract has no deterministic complete native
                # result/revision/criteria/command mapping. Preserve evidence but
                # deliberately retain the native placeholder.
                receipt["canonical_mapping"] = "not_mappable_current_schema"
            else:
                value = json.loads(data.decode("utf-8"))
                if not isinstance(value, dict):
                    raise WorkflowError("completion handoff must be a JSON object")
                if value.get("session_id") != status["session_id"]:
                    raise WorkflowError("completion handoff session_id does not match run")
                from .contracts import validate_instance
                validate_instance(value, "agent-workflow/completion/v1", artifact=str(source))
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


def _capture_patch(workdir: Path, run_dir: Path, path: Path) -> None:
    baseline = None
    try:
        source = json.loads(
            (run_dir / "source-baseline.json").read_text(encoding="utf-8")
        )
        baseline = source.get("components", {}).get("primary", {}).get("head")
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    result = subprocess.run(
        [
            "git",
            "-C",
            str(workdir),
            "diff",
            "--binary",
            "--full-index",
            str(baseline or "HEAD"),
        ],
        capture_output=True,
        check=False,
    )
    patch = bytearray(result.stdout if result.returncode == 0 else b"")
    untracked = subprocess.run(
        [
            "git",
            "-C",
            str(workdir),
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        capture_output=True,
        check=False,
    )
    if untracked.returncode == 0:
        for raw in untracked.stdout.split(b"\0"):
            if not raw:
                continue
            relative = raw.decode("utf-8", errors="surrogateescape")
            addition = subprocess.run(
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
                capture_output=True,
                check=False,
            )
            if addition.returncode in {0, 1}:
                patch.extend(addition.stdout)
    path.write_bytes(patch)


def execute(
    run_dir: Path,
    workdir: Path,
    command: list[str],
    *,
    stream_format: str,
    heartbeat_seconds: float = 5.0,
) -> int:
    run_dir = run_dir.resolve()
    workdir = workdir.resolve()
    status_path = run_dir / "status.json"
    prompt = (run_dir / "launch-prompt.md").read_bytes()
    output_path = run_dir / "output.log"
    events_path = run_dir / "executor-events.jsonl"
    stderr_path = run_dir / "executor-stderr.log"
    heartbeat_path = run_dir / "heartbeat.json"
    lock = threading.Lock()
    usage: dict[str, Any] | None = None
    first_output_at: str | None = None
    last_normalized_text: str | None = None
    pump_errors: list[str] = []
    wall_started = time.monotonic()
    runtime_path = run_dir / "evaluation-runtime.json"
    runtime = (
        json.loads(runtime_path.read_text(encoding="utf-8"))
        if runtime_path.is_file()
        else None
    )
    provenance_initial = json.loads(
        (run_dir / "run-provenance.json").read_text(encoding="utf-8")
    )
    initial_budgets = provenance_initial.get("budgets", {})
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
    try:
        process = subprocess.Popen(
            command,
            cwd=workdir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        finished_at = utc_now()
        update_provenance(
            run_dir,
            finished_at=finished_at,
            exit_code=127,
        )
        _capture_patch(workdir, run_dir, run_dir / "patch.diff")
        _collect_completion(run_dir, workdir)
        current = _read_status(status_path)
        final_status = {
            **current,
            "status": "failed",
            "finished_at": finished_at,
            "exit_code": 127,
            "failure_category": classify_failure(
                exit_code=127, stderr=str(exc)
            ),
            "updated_at": finished_at,
        }
        atomic_write_json(run_dir / "final-status.json", final_status)
        receipt = seal_run(run_dir, session_id=str(current["session_id"]))
        receipt_hash = sha256_file(run_dir / "final-receipt.json")
        _update_status(
            status_path,
            **final_status,
            final_receipt_path=str(run_dir / "final-receipt.json"),
            final_receipt_sha256=receipt_hash,
            sealed_artifact_count=len(receipt["artifacts"]),
        )
        make_read_only(run_dir)
        return 127
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    process.stdin.write(prompt)
    process.stdin.close()

    def forward_signal(signum: int, _frame: Any) -> None:
        if process.poll() is None:
            os.killpg(process.pid, signum)

    signal.signal(signal.SIGINT, forward_signal)
    signal.signal(signal.SIGTERM, forward_signal)

    def stdout_pump() -> None:
        nonlocal usage, first_output_at, last_normalized_text
        try:
            with output_path.open("ab") as output, events_path.open("ab") as events:
                for raw in iter(process.stdout.readline, b""):
                    if first_output_at is None:
                        first_output_at = utc_now()
                    if stream_format == "text":
                        with lock:
                            _write_bytes(output, raw)
                    else:
                        _write_bytes(events, raw)
                        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                        event = parse_event(line, stream_format)
                        if event is None:
                            with lock:
                                _write_bytes(output, raw)
                            continue
                        event_usage_value = event_usage(event)
                        if event_usage_value is not None:
                            usage = event_usage_value
                        for text in event_text(event, stream_format):
                            normalized = text.rstrip()
                            if normalized == last_normalized_text:
                                continue
                            last_normalized_text = normalized
                            with lock:
                                _write_bytes(output, (normalized + "\n").encode())
        except Exception as exc:  # pragma: no cover - defensive thread boundary
            pump_errors.append(f"stdout: {exc}")

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
        except Exception as exc:  # pragma: no cover - defensive thread boundary
            pump_errors.append(f"stderr: {exc}")

    threads = [
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
        wait_seconds = max(0.1, heartbeat_seconds)
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    return_code = process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    return_code = process.wait()
                break
            wait_seconds = min(wait_seconds, remaining)
        try:
            return_code = process.wait(timeout=wait_seconds)
            break
        except subprocess.TimeoutExpired:
            continue
    for thread in threads:
        thread.join(timeout=5)
    if any(thread.is_alive() for thread in threads):
        pump_errors.append("stream drain deadline exceeded")
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        process.stdout.close()
        process.stderr.close()
        for thread in threads:
            thread.join(timeout=2)
        if any(thread.is_alive() for thread in threads):
            pump_errors.append("stream pump did not stop after descriptor close")
    if pump_errors:
        return_code = return_code or 1

    _collect_completion(run_dir, workdir)

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
    )
    current = _read_status(status_path)
    final_status = {
        **current,
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
    try:
        receipt = seal_run(run_dir, session_id=str(current["session_id"]))
        receipt_hash = sha256_file(run_dir / "final-receipt.json")
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
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--stream-format", default="text")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("missing command after --")
    return execute(
        args.run_dir,
        args.workdir,
        command,
        stream_format=args.stream_format,
    )


if __name__ == "__main__":
    raise SystemExit(main())
