"""Collection of executor-produced Agent Run evidence.

Normal execution and recovery finalization share the same bounded completion,
structured-result, and patch collectors.  Keeping them outside ``runner``
prevents recovery code from importing private process-loop helpers and gives
both paths one evidence-collection implementation.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from .agent_run_paths import AgentRunPaths
from .completion import (
    completion_revision_errors,
    substantive_completion_errors,
    validate_completion_repository_closeout,
)
from .contracts import read_agent_run_contract, validate_instance
from .errors import WorkflowError
from .path import read_regular_file
from .process import redact_bytes, run, run_bytes
from .state import update_projection_path
from .util import atomic_write_bytes, atomic_write_json, utc_now

MAX_COMPLETION_HANDOFF_BYTES = 1024 * 1024
MAX_PATCH_BYTES = 16 * 1024 * 1024


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


def _worktree_head_revision(workdir: Path) -> str:
    result = run(
        ["git", "-C", str(workdir), "rev-parse", "--verify", "HEAD"],
        check=False,
        max_stdout_bytes=128,
        max_stderr_bytes=1024,
    )
    head = result.stdout.strip()
    if result.returncode != 0 or not head:
        raise WorkflowError("completion requires a readable worktree Git HEAD")
    return head


def collect_completion(
    run_dir: Path,
    workdir: Path,
    *,
    secret_values: tuple[str, ...] = (),
    expected_source_sha256: str | None = None,
) -> dict[str, Any]:
    """Collect native executor completion evidence before sealing."""
    paths = AgentRunPaths(run_dir)
    launch = read_agent_run_contract(paths.contract)
    agent_run_id = str(launch["agent_run"]["id"])
    contract_workdir = Path(str(launch["worktree"]["path"]))
    handoff_value = launch["paths"].get("handoff_dir")
    handoff = Path(handoff_value) if isinstance(handoff_value, str) else None
    source = handoff / "completion.json" if handoff is not None else None
    receipt: dict[str, Any] = {
        "schema": "agent-workflow/completion-collection/v1",
        "agent_run_id": agent_run_id,
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
        "repository_closeout_source_path": None,
        "repository_closeout_source_sha256": None,
        "repository_closeout_stored_path": None,
        "repository_closeout_payload_sha256": None,
        "repository_closeout_claims": None,
    }
    try:
        if handoff is None:
            raise FileNotFoundError("launch has no completion handoff")
        _require_real_handoff_dir(handoff, contract_workdir)
        assert source is not None
        source_data = _read_handoff_completion(source)
        if (
            expected_source_sha256 is not None
            and hashlib.sha256(source_data).hexdigest() != expected_source_sha256
        ):
            raise WorkflowError("task completion handoff changed after task-complete intent")
        data = redact_bytes(source_data, secret_values)
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
            if value.get("agent_run_id") != agent_run_id:
                raise WorkflowError("completion handoff agent_run_id does not match run")
            validate_instance(value, "agent-workflow/completion/v1", artifact=str(source))
            ticket_identity = launch.get("ticket_identity")
            expected_ticket = launch.get("ticket")
            if isinstance(ticket_identity, dict):
                expected_ticket = ticket_identity.get("value")
            semantic_errors = substantive_completion_errors(
                value,
                agent_run_id=agent_run_id,
                ticket_id=expected_ticket,
                pack_id=(
                    launch.get("pack", {}).get("id")
                    if isinstance(launch.get("pack"), dict)
                    else None
                ),
            )
            if semantic_errors:
                raise WorkflowError("; ".join(semantic_errors))
            revision_errors = completion_revision_errors(
                value,
                expected_base_revision=launch["worktree"].get("source_revision"),
                actual_head_revision=_worktree_head_revision(contract_workdir),
            )
            if revision_errors:
                raise WorkflowError("; ".join(revision_errors))
            repository_summary = validate_completion_repository_closeout(
                value,
                handoff=handoff,
                expected_worktree=contract_workdir,
            )
            repository_data = None
            if repository_summary is not None:
                repository_source = handoff / "repository-closeout.json"
                repository_data = _read_handoff_completion(repository_source)
                receipt["repository_closeout_source_path"] = str(repository_source)
                receipt["repository_closeout_source_sha256"] = hashlib.sha256(repository_data).hexdigest()
            completion_path = paths.completion
            temporary = completion_path.with_name(f".{completion_path.name}.handoff")
            temporary.write_bytes(data)
            os.replace(temporary, completion_path)
            if repository_data is not None and repository_summary is not None:
                repository_path = paths.repository_closeout
                repository_temporary = repository_path.with_name(f".{repository_path.name}.handoff")
                repository_temporary.write_bytes(repository_data)
                os.replace(repository_temporary, repository_path)
                receipt["repository_closeout_stored_path"] = "repository-closeout.json"
                receipt["repository_closeout_payload_sha256"] = repository_summary["payload_sha256"]
                receipt["repository_closeout_claims"] = repository_summary["claims"]
            receipt["stored_path"] = "completion.json"
            receipt["canonical_mapping"] = "identity"
            receipt["canonical_sha256"] = hashlib.sha256(completion_path.read_bytes()).hexdigest()
            receipt["validation_status"] = "valid"
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
            receipt["validation_status"] = "invalid"
            receipt["validation_errors"] = [str(exc)]
            # Keep the exact worker submission available for correction and
            # audit.  This is deliberately separate from the canonical
            # collection and never becomes terminal evidence.
            if source is not None:
                atomic_write_bytes(handoff / ".completion.json.rejected", source_data)
    receipt_path = paths.collections / "completion.json"
    atomic_write_json(receipt_path, receipt)
    update_projection_path(
        paths.status,
        completion_collection_path=str(receipt_path),
        completion_validation_status=receipt["validation_status"],
    )
    return receipt


def collect_task_result(
    run_dir: Path, workdir: Path, *, secret_values: tuple[str, ...] = ()
) -> dict[str, Any] | None:
    """Collect and validate an optional ticket-specific structured result."""
    paths = AgentRunPaths(run_dir)
    launch = read_agent_run_contract(paths.contract)
    agent_run_id = str(launch["agent_run"]["id"])
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
        "agent_run_id": agent_run_id,
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
        stored = paths.result
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
    receipt_path = paths.collections / "task-result.json"
    atomic_write_json(receipt_path, receipt)
    update_projection_path(
        paths.status,
        task_result_collection_path=str(receipt_path),
        task_result_validation_status=receipt["validation_status"],
    )
    return receipt


def capture_patch(workdir: Path, run_dir: Path, path: Path) -> None:
    """Capture tracked and untracked worktree changes as one bounded patch."""
    paths = AgentRunPaths(run_dir)
    baseline = None
    try:
        source = json.loads(paths.source_baseline.read_text(encoding="utf-8"))
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
        max_stdout_bytes=MAX_PATCH_BYTES,
        max_stderr_bytes=64 * 1024,
    )
    patch = bytearray(result.stdout if result.returncode == 0 else b"")
    untracked = run_bytes(
        ["git", "-C", str(workdir), "ls-files", "--others", "--exclude-standard", "-z"],
        check=False,
        timeout_seconds=60,
        max_stdout_bytes=MAX_PATCH_BYTES,
        max_stderr_bytes=64 * 1024,
    )
    if untracked.returncode == 0:
        for raw in untracked.stdout.split(b"\0"):
            if not raw:
                continue
            relative = raw.decode("utf-8", errors="surrogateescape")
            addition = run_bytes(
                [
                    "git", "-C", str(workdir), "diff", "--no-index", "--binary",
                    "--", "/dev/null", relative,
                ],
                check=False,
                timeout_seconds=60,
                max_stdout_bytes=MAX_PATCH_BYTES,
                max_stderr_bytes=64 * 1024,
            )
            if addition.returncode in {0, 1}:
                patch.extend(addition.stdout)
    path.write_bytes(patch)
