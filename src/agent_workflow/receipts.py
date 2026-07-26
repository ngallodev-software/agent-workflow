from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .contracts import read_contract, validate_instance
from .errors import WorkflowError
from .util import atomic_write_json, fsync_directory, sha256_file, utc_now

SEALED_ARTIFACTS = (
    "prompt.md",
    "launch-prompt.md",
    "command.json",
    "source-baseline.json",
    "completion.md",
    "completion.json",
    "run-provenance.json",
    "executor-events.jsonl",
    "executor-stderr.log",
    "output.log",
    "final-status.json",
    "patch.diff",
    "collections/completion.json",
)
SEALED_TREES = ("collections", "scope")
SEALED_OPTIONAL_ARTIFACTS = (
    "result.json",
    "evaluation-runtime.json",
    "execution-metrics.json",
    "control-events.jsonl",
    "job-binding.json",
    "jobs/native-job.json",
    "agent-context.json",
    "workflow-inputs.json",
    "provider-evidence.json",
    "assignments.jsonl",
)
SEALED_OPTIONAL_TREES = ("assignments",)


@contextmanager
def _seal_lock(run_dir: Path, *, exclusive: bool) -> Iterator[None]:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "seal.lock"
    existed = path.exists() or path.is_symlink()
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise WorkflowError(f"cannot open run seal lock {path}: {exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError(f"run seal lock must be a regular file: {path}")
        if not existed:
            os.fsync(descriptor)
            fsync_directory(run_dir)
        fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _read_final_receipt(path: Path) -> tuple[dict[str, Any], str]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WorkflowError(f"cannot open final receipt {path}: {exc}") from exc
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError(f"final receipt must be a regular file: {path}")
        if info.st_mode & 0o222:
            raise WorkflowError(f"final receipt must be read-only: {path}")
        data = stream.read()
    try:
        receipt = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read final receipt {path}: {exc}") from exc
    if not isinstance(receipt, dict) or not isinstance(receipt.get("artifacts"), list):
        raise WorkflowError(f"invalid final receipt: {path}")
    validate_instance(receipt, "agent-workflow/final-receipt/v1", artifact=str(path))
    return receipt, hashlib.sha256(data).hexdigest()


def _artifact_entry(receipt: dict[str, Any], relative_path: str) -> dict[str, Any]:
    matches = [
        item
        for item in receipt.get("artifacts", [])
        if isinstance(item, dict) and item.get("path") == relative_path
    ]
    if not matches:
        raise WorkflowError(
            f"final receipt is missing an artifact entry for {relative_path}"
        )
    if any(item != matches[0] for item in matches[1:]):
        raise WorkflowError(f"conflicting final receipt entries for {relative_path}")
    return matches[0]


def _artifact_parts(relative_path: str) -> tuple[str, ...]:
    relative = Path(relative_path)
    parts = relative.parts
    if (
        not parts
        or relative.is_absolute()
        or any(part in {"", ".", ".."} for part in parts)
        or relative.as_posix() != relative_path
    ):
        raise WorkflowError(f"invalid sealed artifact path: {relative_path}")
    return parts


def _open_artifact_beneath(run_dir: Path, relative_path: str) -> int:
    """Open an artifact without following any path-component symlink."""
    parts = _artifact_parts(relative_path)
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        current = os.open(run_dir.resolve(), directory_flags)
    except OSError as exc:
        raise WorkflowError(f"cannot open sealed run directory {run_dir}: {exc}") from exc
    try:
        for component in parts[:-1]:
            try:
                next_descriptor = os.open(
                    component, directory_flags, dir_fd=current
                )
            except OSError as exc:
                raise WorkflowError(
                    f"cannot open sealed artifact directory {relative_path}: {exc}"
                ) from exc
            os.close(current)
            current = next_descriptor
        try:
            return os.open(
                parts[-1],
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=current,
            )
        except OSError as exc:
            raise WorkflowError(f"cannot open sealed artifact {relative_path}: {exc}") from exc
    finally:
        os.close(current)


def _read_artifact_descriptor(
    run_dir: Path, relative_path: str, *, capture_bytes: bool
) -> tuple[bytes | None, int, str]:
    descriptor = _open_artifact_beneath(run_dir, relative_path)
    digest = hashlib.sha256()
    total = 0
    chunks: list[bytes] | None = [] if capture_bytes else None
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise WorkflowError(
                f"sealed artifact must be a regular file: {relative_path}"
            )
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            total += len(chunk)
            if chunks is not None:
                chunks.append(chunk)
        after = os.fstat(stream.fileno())
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ctime_ns != after.st_ctime_ns
        or total != after.st_size
    ):
        raise WorkflowError(f"sealed artifact changed during read: {relative_path}")
    return (b"".join(chunks) if chunks is not None else None), total, digest.hexdigest()


def read_sealed_artifact_bytes(
    run_dir: Path, receipt: dict[str, Any], relative_path: str
) -> tuple[bytes, str]:
    """Read one artifact through stable beneath-root descriptors and match its receipt."""
    entry = _artifact_entry(receipt, relative_path)
    data, size, digest = _read_artifact_descriptor(
        run_dir, relative_path, capture_bytes=True
    )
    assert data is not None
    if entry.get("size") != size:
        raise WorkflowError(f"sealed artifact size mismatch: {relative_path}")
    if entry.get("sha256") != digest:
        raise WorkflowError(f"sealed artifact checksum mismatch: {relative_path}")
    return data, digest


def read_sealed_json(
    run_dir: Path, receipt: dict[str, Any], relative_path: str
) -> tuple[Any, str]:
    data, digest = read_sealed_artifact_bytes(run_dir, receipt, relative_path)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"invalid sealed JSON artifact {relative_path}: {exc}") from exc
    return value, digest


def read_sealed_contract(
    run_dir: Path,
    receipt: dict[str, Any],
    relative_path: str,
    schema: str,
) -> tuple[dict[str, Any], str]:
    value, digest = read_sealed_json(run_dir, receipt, relative_path)
    if not isinstance(value, dict):
        raise WorkflowError(f"sealed contract must be a JSON object: {relative_path}")
    validate_instance(value, schema, artifact=str(run_dir / relative_path))
    return value, digest


def initial_completion(
    *,
    session_id: str,
    ticket_id: str | None,
    pack_id: str | None,
    base_revision: str | None,
) -> dict[str, Any]:
    return {
        "schema": "agent-workflow/completion/v1",
        "session_id": session_id,
        "ticket_id": ticket_id,
        "pack_id": pack_id,
        "result": "blocked",
        "base_revision": base_revision,
        "head_revision": base_revision,
        "changed_files": [],
        "criteria": [],
        "commands": [],
        "unresolved": ["agent completion sidecar not finalized"],
        "usage": None,
    }


def initial_provenance(
    *,
    session_id: str,
    executor: str | None,
    argv: list[str],
    stream_format: str,
    executor_version: str | None,
    executable: dict[str, Any] | None = None,
    agent_name: str | None = None,
    agent_class: str | None = None,
    model: str | None = None,
    model_policy: dict[str, Any] | None = None,
    prompt_sha256: str,
    launch_prompt_sha256: str,
    config_sha256: str | None,
    pack_manifest_sha256: str | None,
    source_revision: str | None,
    worktree: Path,
    environment: dict[str, Any],
    retry_of_run_id: str | None = None,
    budgets: dict[str, Any] | None = None,
    job_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": "agent-workflow/run-provenance/v1",
        "session_id": session_id,
        "executor": executor,
        "agent_name": agent_name,
        "agent_class": agent_class,
        "argv": argv,
        "stream_format": stream_format,
        "executor_version": executor_version,
        "executable": executable,
        "model": model,
        "model_policy": model_policy or {
            "no_go_authorized": False,
            "authorization_source": None,
        },
        "prompt_sha256": prompt_sha256,
        "launch_prompt_sha256": launch_prompt_sha256,
        "config_sha256": config_sha256,
        "pack_manifest_sha256": pack_manifest_sha256,
        "source_revision": source_revision,
        "worktree": str(worktree),
        "environment": environment,
        "retry_of_run_id": retry_of_run_id,
        "budgets": budgets or {},
        "job_binding": job_binding,
        "usage": None,
        "provider_evidence": None,
        "started_at": utc_now(),
        "first_output_at": None,
        "finished_at": None,
        "exit_code": None,
    }


def update_provenance(run_dir: Path, **changes: Any) -> dict[str, Any]:
    path = run_dir / "run-provenance.json"
    with _seal_lock(run_dir, exclusive=True):
        final_receipt = run_dir / "final-receipt.json"
        if final_receipt.exists() or final_receipt.is_symlink():
            raise WorkflowError(f"cannot update sealed provenance: {path}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"cannot update provenance {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise WorkflowError(f"provenance must be an object: {path}")
        value.update(changes)
        atomic_write_json(path, value)
        return value


def _artifact_receipt(path: Path, root: Path) -> dict[str, Any]:
    try:
        relative_path = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise WorkflowError(f"sealed artifact escapes run root: {path}") from exc
    _, size, digest = _read_artifact_descriptor(
        root, relative_path, capture_bytes=False
    )
    return {
        "path": relative_path,
        "size": size,
        "sha256": digest,
    }


def _seal_run_unlocked(run_dir: Path, *, session_id: str) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    final_receipt = run_dir / "final-receipt.json"
    if final_receipt.exists() or final_receipt.is_symlink():
        raise WorkflowError(
            f"run is already sealed or unsafe: {final_receipt}; verify it with the recorded checksum"
        )
    artifacts = [
        _artifact_receipt(path, run_dir)
        for name in SEALED_ARTIFACTS
        if (path := run_dir / name).is_file()
    ]
    artifacts.extend(
        _artifact_receipt(path, run_dir)
        for name in SEALED_OPTIONAL_ARTIFACTS
        if (path := run_dir / name).is_file()
    )
    for tree in SEALED_OPTIONAL_TREES:
        tree_root = run_dir / tree
        if tree_root.is_dir() and not tree_root.is_symlink():
            artifacts.extend(
                _artifact_receipt(path, run_dir)
                for path in sorted(tree_root.rglob("*"))
                if path.is_file()
            )
    listed_paths = {item["path"] for item in artifacts}
    for tree in SEALED_TREES:
        tree_root = run_dir / tree
        if tree_root.is_dir() and not tree_root.is_symlink():
            artifacts.extend(
                _artifact_receipt(path, run_dir)
                for path in sorted(tree_root.rglob("*"))
                if path.is_file()
                and path.relative_to(run_dir).as_posix() not in listed_paths
            )
    task_result = run_dir / "collections" / "task-result.json"
    if task_result.is_file() and not any(
        item.get("path") == "collections/task-result.json" for item in artifacts
    ):
        artifacts.append(_artifact_receipt(task_result, run_dir))
    result = run_dir / "result.json"
    if result.is_file() and not any(item.get("path") == "result.json" for item in artifacts):
        artifacts.append(_artifact_receipt(result, run_dir))
    unique_artifacts: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        path = str(artifact["path"])
        previous = unique_artifacts.get(path)
        if previous is not None and previous != artifact:
            raise WorkflowError(f"conflicting sealed artifact entries for {path}")
        unique_artifacts[path] = artifact
    artifacts = list(unique_artifacts.values())
    required = set(SEALED_ARTIFACTS)
    present = {item["path"] for item in artifacts}
    missing = sorted(required - present)
    if missing:
        raise WorkflowError(f"cannot seal run; missing artifacts: {missing}")
    for name, schema in {
        "command.json": "agent-workflow/command/v1",
        "source-baseline.json": "agent-workflow/source-baseline/v1",
        "completion.json": "agent-workflow/completion/v1",
        "run-provenance.json": "agent-workflow/run-provenance/v1",
        "final-status.json": "agent-workflow/session-status/v2",
        "collections/completion.json": "agent-workflow/completion-collection/v1",
    }.items():
        read_contract(run_dir / name, schema)
    binding = run_dir / "job-binding.json"
    if binding.is_file():
        read_contract(binding, "agent-workflow/job-binding/v1")
    task_result_collection = run_dir / "collections" / "task-result.json"
    if task_result_collection.is_file():
        read_contract(task_result_collection, "agent-workflow/task-result-collection/v1")
    metrics = run_dir / "execution-metrics.json"
    if metrics.is_file():
        read_contract(metrics, "agent-workflow/execution-metrics/v1")
    provider_evidence = run_dir / "provider-evidence.json"
    if provider_evidence.is_file():
        read_contract(provider_evidence, "agent-workflow/provider-evidence/v1")
    controls = run_dir / "control-events.jsonl"
    if controls.is_file():
        for line_number, raw in enumerate(controls.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw:
                raise WorkflowError(f"blank control event at line {line_number}")
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise WorkflowError(f"invalid control event JSON at line {line_number}: {exc}") from exc
            validate_instance(event, "agent-workflow/control-event/v1", artifact=str(controls))
    receipt = {
        "schema": "agent-workflow/final-receipt/v1",
        "session_id": session_id,
        "sealed_at": utc_now(),
        "artifacts": artifacts,
    }
    validate_instance(
        receipt,
        "agent-workflow/final-receipt/v1",
        artifact=str(final_receipt),
    )
    atomic_write_json(final_receipt, receipt, mode=0o444)
    return receipt


def seal_run(run_dir: Path, *, session_id: str) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    with _seal_lock(run_dir, exclusive=True):
        return _seal_run_unlocked(run_dir, session_id=session_id)


def _verify_seal_unlocked(
    run_dir: Path, *, expected_sha256: str | None = None
) -> tuple[dict[str, Any], str]:
    run_dir = run_dir.resolve()
    path = run_dir / "final-receipt.json"
    receipt, actual = _read_final_receipt(path)
    if expected_sha256 is not None and actual != expected_sha256:
        raise WorkflowError(
            f"final receipt checksum mismatch: {actual}; expected {expected_sha256}"
        )
    listed = {
        item.get("path")
        for item in receipt["artifacts"]
        if isinstance(item, dict)
    }
    missing = sorted(set(SEALED_ARTIFACTS) - listed)
    if missing:
        raise WorkflowError(f"final receipt omits required artifacts: {missing}")
    for item in receipt["artifacts"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise WorkflowError(f"invalid artifact entry in {path}")
        relative_path = item["path"]
        _artifact_parts(relative_path)
        _, size, digest = _read_artifact_descriptor(
            run_dir, relative_path, capture_bytes=False
        )
        if size != item.get("size"):
            raise WorkflowError(f"sealed artifact size mismatch: {relative_path}")
        if digest != item.get("sha256"):
            raise WorkflowError(f"sealed artifact checksum mismatch: {relative_path}")
    return receipt, actual


def verify_seal_details(
    run_dir: Path, *, expected_sha256: str | None = None
) -> tuple[dict[str, Any], str]:
    """Verify one sealed run and return the receipt plus its verified-byte digest."""
    run_dir = run_dir.resolve()
    with _seal_lock(run_dir, exclusive=False):
        return _verify_seal_unlocked(run_dir, expected_sha256=expected_sha256)


def verify_seal(
    run_dir: Path, *, expected_sha256: str | None = None
) -> dict[str, Any]:
    receipt, _ = verify_seal_details(run_dir, expected_sha256=expected_sha256)
    return receipt


def final_receipt_sha256(run_dir: Path) -> str:
    run_dir = run_dir.resolve()
    with _seal_lock(run_dir, exclusive=False):
        _, digest = _read_final_receipt(run_dir / "final-receipt.json")
        return digest


def _make_file_read_only(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WorkflowError(f"cannot open sealed artifact for chmod {path}: {exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError(f"sealed artifact must be a regular file: {path}")
        os.fchmod(descriptor, info.st_mode & ~0o222)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def make_read_only(run_dir: Path) -> None:
    for name in (*SEALED_ARTIFACTS, *SEALED_OPTIONAL_ARTIFACTS):
        path = run_dir / name
        if path.exists() or path.is_symlink():
            _make_file_read_only(path)
    for tree in (*SEALED_TREES, *SEALED_OPTIONAL_TREES):
        tree_root = run_dir / tree
        if not tree_root.exists() and not tree_root.is_symlink():
            continue
        try:
            root_info = tree_root.lstat()
        except OSError as exc:
            raise WorkflowError(f"cannot inspect sealed artifact tree {tree_root}: {exc}") from exc
        if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
            raise WorkflowError(f"sealed artifact tree is unsafe: {tree_root}")
        for path in tree_root.rglob("*"):
            try:
                info = path.lstat()
            except OSError as exc:
                raise WorkflowError(f"cannot inspect sealed artifact {path}: {exc}") from exc
            if stat.S_ISLNK(info.st_mode):
                raise WorkflowError(f"sealed artifact must not be a symlink: {path}")
            if stat.S_ISREG(info.st_mode):
                _make_file_read_only(path)
