from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .contracts import read_contract, validate_instance
from .errors import WorkflowError
from .util import atomic_write_json, sha256_file, utc_now

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
    "evaluation-runtime.json",
    "execution-metrics.json",
    "control-events.jsonl",
    "job-binding.json",
    "jobs/native-job.json",
    "external/tax-machine/MANIFEST.json",
    "external/tax-machine/job.json",
    "external/tax-machine/job.schema.json",
    "external/tax-machine/completion.schema.json",
    "external/tax-machine/completion.json",
)


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
    prompt_sha256: str,
    launch_prompt_sha256: str,
    config_sha256: str | None,
    pack_manifest_sha256: str | None,
    source_revision: str | None,
    worktree: Path,
    environment: dict[str, Any],
    budgets: dict[str, Any] | None = None,
    job_binding: dict[str, Any] | None = None,
    external_snapshots: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": "agent-workflow/run-provenance/v1",
        "session_id": session_id,
        "executor": executor,
        "argv": argv,
        "stream_format": stream_format,
        "executor_version": executor_version,
        "model": None,
        "prompt_sha256": prompt_sha256,
        "launch_prompt_sha256": launch_prompt_sha256,
        "config_sha256": config_sha256,
        "pack_manifest_sha256": pack_manifest_sha256,
        "source_revision": source_revision,
        "worktree": str(worktree),
        "environment": environment,
        "budgets": budgets or {},
        "job_binding": job_binding,
        "external_snapshots": external_snapshots,
        "usage": None,
        "started_at": utc_now(),
        "first_output_at": None,
        "finished_at": None,
        "exit_code": None,
    }


def update_provenance(run_dir: Path, **changes: Any) -> dict[str, Any]:
    path = run_dir / "run-provenance.json"
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
    if path.is_symlink():
        raise WorkflowError(f"sealed artifact must not be a symlink: {path}")
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise WorkflowError(f"sealed artifact escapes run root: {path}") from exc
    return {
        "path": rel.as_posix(),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def seal_run(run_dir: Path, *, session_id: str) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    final_receipt = run_dir / "final-receipt.json"
    if final_receipt.exists():
        raise WorkflowError(
            f"run is already sealed: {final_receipt}; verify it with the recorded checksum"
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
    metrics = run_dir / "execution-metrics.json"
    if metrics.is_file():
        read_contract(metrics, "agent-workflow/execution-metrics/v1")
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
    atomic_write_json(final_receipt, receipt)
    validate_instance(
        receipt,
        "agent-workflow/final-receipt/v1",
        artifact=str(final_receipt),
    )
    final_receipt.chmod(0o444)
    return receipt


def verify_seal(
    run_dir: Path, *, expected_sha256: str
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    path = run_dir / "final-receipt.json"
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read final receipt {path}: {exc}") from exc
    if not isinstance(receipt, dict) or not isinstance(receipt.get("artifacts"), list):
        raise WorkflowError(f"invalid final receipt: {path}")
    validate_instance(
        receipt, "agent-workflow/final-receipt/v1", artifact=str(path)
    )
    actual = sha256_file(path)
    if actual != expected_sha256:
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
        artifact = run_dir / item["path"]
        try:
            artifact.resolve().relative_to(run_dir)
        except ValueError as exc:
            raise WorkflowError(f"receipt artifact escapes run root: {artifact}") from exc
        if not artifact.is_file() or artifact.is_symlink():
            raise WorkflowError(f"sealed artifact missing or unsafe: {artifact}")
        if artifact.stat().st_size != item.get("size"):
            raise WorkflowError(f"sealed artifact size mismatch: {artifact}")
        if sha256_file(artifact) != item.get("sha256"):
            raise WorkflowError(f"sealed artifact checksum mismatch: {artifact}")
    return receipt


def final_receipt_sha256(run_dir: Path) -> str:
    return sha256_file(run_dir / "final-receipt.json")


def make_read_only(run_dir: Path) -> None:
    for name in (*SEALED_ARTIFACTS, *SEALED_OPTIONAL_ARTIFACTS):
        path = run_dir / name
        if path.is_file():
            os.chmod(path, path.stat().st_mode & ~0o222)
    for tree in SEALED_TREES:
        tree_root = run_dir / tree
        if tree_root.is_dir():
            for path in tree_root.rglob("*"):
                if path.is_file():
                    os.chmod(path, path.stat().st_mode & ~0o222)
