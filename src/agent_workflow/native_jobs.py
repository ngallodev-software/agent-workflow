"""Validation boundary for versioned, JSON-only native prompt-pack jobs.

This module deliberately validates only the native job contract.  It does not
discover external packs, create runtime state, or authorize command execution.
Those responsibilities begin with the Phase-B2 launch binding.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import validate_instance
from .errors import WorkflowError
from .eval.commands import CommandSpec, specs_from_data


NATIVE_JOB_SCHEMA = "agent-workflow/native-job/v1"


@dataclass(frozen=True)
class PathPolicy:
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]


@dataclass(frozen=True)
class ReviewRequirement:
    required: bool
    independent: bool


@dataclass(frozen=True)
class ValidatedNativeJob:
    """A native job whose schema and pack-relative paths have been checked."""

    schema: str
    job_path: Path
    pack_root: Path
    job_id: str
    ticket_id: str
    prompt_path: Path
    prompt_relative_path: str
    worktree_target: str
    path_policy: PathPolicy
    acceptance_commands: tuple[CommandSpec, ...]
    review_requirement: ReviewRequirement


def _resolve_relative(root: Path, value: str, label: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise WorkflowError(f"{label} must be a relative path without '..': {value}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise WorkflowError(f"{label} escapes pack root: {value}") from exc
    return resolved


def _validate_policy_path(value: str, label: str) -> str:
    path = Path(value)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise WorkflowError(f"{label} must be a relative path without '..': {value}")
    if value in ("", "."):
        raise WorkflowError(f"{label} must name a path, not the worktree root")
    return value


def _read_json_job(job_path: Path) -> dict[str, Any]:
    if job_path.suffix.lower() != ".json":
        raise WorkflowError(f"native job must be a .json file: {job_path}")
    try:
        value = json.loads(job_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise WorkflowError(f"cannot read native job {job_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid JSON in native job {job_path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"native job must be a JSON object: {job_path}")
    return value


def validate_native_job(job_path: Path, *, pack_root: Path) -> ValidatedNativeJob:
    """Read and validate a native job without performing any runtime action.

    ``prompt_path`` is resolved against ``pack_root`` and must name an existing
    regular file. ``worktree_target`` and path-policy entries are constrained to
    relative, traversal-free paths; B2 binds them to a selected worktree.
    """

    root = pack_root.resolve()
    if not root.is_dir():
        raise WorkflowError(f"pack root is not a directory: {pack_root}")
    path = job_path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise WorkflowError(f"native job is outside pack root: {job_path}") from exc
    value = _read_json_job(path)
    if value.get("schema") != NATIVE_JOB_SCHEMA:
        raise WorkflowError(
            f"unsupported native job schema in {path}: {value.get('schema')!r}"
        )
    validate_instance(value, NATIVE_JOB_SCHEMA, artifact=str(path))

    prompt_relative = str(value["prompt_path"])
    prompt_path = _resolve_relative(root, prompt_relative, "prompt_path")
    if not prompt_path.is_file():
        raise WorkflowError(f"prompt_path is not a file under pack root: {prompt_relative}")

    worktree_target = str(value["worktree_target"])
    _validate_policy_path(worktree_target, "worktree_target")
    policy_data = value["path_policy"]
    allowed = tuple(
        _validate_policy_path(str(item), "allowed_paths entry")
        for item in policy_data["allowed_paths"]
    )
    forbidden = tuple(
        _validate_policy_path(str(item), "forbidden_paths entry")
        for item in policy_data.get("forbidden_paths", [])
    )
    if set(allowed) & set(forbidden):
        raise WorkflowError("path_policy contains paths that are both allowed and forbidden")

    commands = tuple(specs_from_data(value["acceptance_commands"]))
    command_ids = [command.id for command in commands]
    if len(command_ids) != len(set(command_ids)):
        raise WorkflowError("acceptance_commands contains duplicate command IDs")
    review_data = value["review_requirement"]
    return ValidatedNativeJob(
        schema=NATIVE_JOB_SCHEMA,
        job_path=path,
        pack_root=root,
        job_id=str(value["job_id"]),
        ticket_id=str(value["ticket_id"]),
        prompt_path=prompt_path,
        prompt_relative_path=prompt_relative,
        worktree_target=worktree_target,
        path_policy=PathPolicy(allowed_paths=allowed, forbidden_paths=forbidden),
        acceptance_commands=commands,
        review_requirement=ReviewRequirement(
            required=bool(review_data["required"]),
            independent=bool(review_data.get("independent", False)),
        ),
    )
