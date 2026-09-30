"""Validation boundary for versioned, JSON-only native prompt-pack jobs.

This module validates native job contracts without authorizing execution.
Version 1 preserves the released SpecGen/shared-contract provenance path.
Version 2 binds an Agent-Workflow-owned source-specification import receipt and
does not import or negotiate SpecGen contracts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import validate_instance
from .errors import WorkflowError
from .eval.commands import CommandSpec, specs_from_data
from .path import absolute_path, read_regular_file, require_directory
from .process import run
from .shared_contracts import negotiate_bundle


NATIVE_JOB_SCHEMA = "agent-workflow/native-job/v1"
NATIVE_JOB_V2_SCHEMA = "agent-workflow/native-job/v2"
SOURCE_SPECIFICATION_SCHEMA = "agent-workflow/source-specification-import/v1"


@dataclass(frozen=True)
class PathPolicy:
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]


@dataclass(frozen=True)
class ReviewRequirement:
    required: bool
    independent: bool


@dataclass(frozen=True)
class CriterionRequirement:
    id: str
    description: str | None = None
    acceptance_command_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceSpecificationBinding:
    schema: str
    source_path: Path
    source_bytes: bytes
    source_sha256: str
    task_refs: tuple[str, ...]
    repository_path: Path


@dataclass(frozen=True)
class ValidatedNativeJob:
    """A native job whose schema and pack-relative resources have been checked."""

    schema: str
    job_path: Path
    pack_root: Path
    job_id: str
    ticket_id: str
    prompt_path: Path
    prompt_bytes: bytes
    job_bytes: bytes
    job_sha256: str
    bundle_provenance: dict[str, Any] | None
    source_specification: SourceSpecificationBinding | None
    prompt_relative_path: str
    worktree_target: str
    worktree_path: Path
    path_policy: PathPolicy
    acceptance_commands: tuple[CommandSpec, ...]
    criteria: tuple[CriterionRequirement, ...]
    review_requirement: ReviewRequirement


def _resolve_relative(root: Path, value: str, label: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise WorkflowError(f"{label} must be a relative path without '..': {value}")
    resolved = absolute_path(root / candidate)
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


def _read_json_job(job_path: Path, raw: bytes | None = None) -> dict[str, Any]:
    if job_path.suffix.lower() != ".json":
        raise WorkflowError(f"native job must be a .json file: {job_path}")
    try:
        value = json.loads((raw if raw is not None else read_regular_file(job_path).data).decode("utf-8"))
    except (OSError, UnicodeDecodeError, WorkflowError) as exc:
        raise WorkflowError(f"cannot read native job {job_path.name}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid JSON in native job {job_path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"native job must be a JSON object: {job_path}")
    return value


def _git_state(root: Path) -> tuple[str, bool]:
    try:
        head = str(
            run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                timeout_seconds=30,
            ).stdout
        ).strip()
        dirty = bool(
            str(
                run(
                    ["git", "-C", str(root), "status", "--porcelain"],
                    check=True,
                    timeout_seconds=30,
                ).stdout
            ).strip()
        )
    except WorkflowError as exc:
        raise WorkflowError(
            f"cannot verify source-specification repository state: {root}"
        ) from exc
    return head, dirty


def _validate_source_specification(
    value: dict[str, Any],
    *,
    pack_root: Path,
) -> SourceSpecificationBinding:
    raw = value.get("source_specification")
    if not isinstance(raw, dict):
        raise WorkflowError("native-job/v2 is missing source_specification")
    if raw.get("schema") != SOURCE_SPECIFICATION_SCHEMA:
        raise WorkflowError(
            "native-job/v2 source_specification uses an unsupported schema"
        )

    relative = str(raw.get("path", ""))
    source_path = _resolve_relative(pack_root, relative, "source_specification.path")
    source_read = read_regular_file(source_path)
    expected_sha = raw.get("sha256")
    if source_read.sha256 != expected_sha:
        raise WorkflowError("source-specification import receipt digest mismatch")
    try:
        receipt = json.loads(source_read.data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError("source-specification import receipt is not valid JSON") from exc
    if not isinstance(receipt, dict):
        raise WorkflowError("source-specification import receipt must be a JSON object")
    validate_instance(
        receipt,
        SOURCE_SPECIFICATION_SCHEMA,
        artifact=str(source_path),
    )

    task_refs = tuple(str(item) for item in raw.get("task_refs", []))
    available = {
        str(item.get("agent_workflow_task_id"))
        for item in receipt.get("task_map", [])
        if isinstance(item, dict)
    }
    unknown = sorted(set(task_refs) - available)
    if unknown:
        raise WorkflowError(
            "native-job/v2 references unknown source-specification tasks: "
            + ", ".join(unknown)
        )

    repository = receipt.get("repository")
    if not isinstance(repository, dict):
        raise WorkflowError("source-specification receipt has no repository binding")
    repository_path = require_directory(
        Path(str(repository.get("path", ""))),
        label="source-specification repository",
    )
    expected_revision = repository.get("revision")
    expected_dirty = bool(repository.get("dirty"))
    head, dirty = _git_state(repository_path)
    if head != expected_revision or dirty != expected_dirty:
        raise WorkflowError(
            "source-specification repository drifted after import; create a new import lineage"
        )

    return SourceSpecificationBinding(
        schema=SOURCE_SPECIFICATION_SCHEMA,
        source_path=source_path,
        source_bytes=source_read.data,
        source_sha256=source_read.sha256,
        task_refs=task_refs,
        repository_path=repository_path,
    )


def validate_native_job(job_path: Path, *, pack_root: Path) -> ValidatedNativeJob:
    """Read and validate a native job without performing any runtime action."""

    root = require_directory(pack_root, label="pack root")
    path = absolute_path(job_path)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise WorkflowError(f"native job is outside pack root: {job_path}") from exc
    job_read = read_regular_file(path)
    value = _read_json_job(path, job_read.data)
    schema = value.get("schema")
    if schema not in {NATIVE_JOB_SCHEMA, NATIVE_JOB_V2_SCHEMA}:
        raise WorkflowError(
            f"unsupported native job schema in {path}: {schema!r}"
        )
    assert isinstance(schema, str)
    validate_instance(value, schema, artifact=str(path))

    bundle_provenance: dict[str, Any] | None = None
    source_specification: SourceSpecificationBinding | None = None
    worktree_target = str(value["worktree_target"])
    if schema == NATIVE_JOB_SCHEMA:
        # Legacy behavior is intentionally unchanged: v1 is the immutable
        # SpecGen/shared-contract handoff and negotiates the published bundle.
        bundle_provenance = negotiate_bundle(value.get("bundle_provenance"))
        _validate_policy_path(worktree_target, "worktree_target")
        worktree_path = require_directory(
            root / worktree_target,
            label="native job worktree target",
        )
    else:
        source_specification = _validate_source_specification(value, pack_root=root)
        target = Path(worktree_target).expanduser()
        if not target.is_absolute():
            raise WorkflowError(
                "native-job/v2 worktree_target must be the absolute repository path "
                "bound by source_specification"
            )
        worktree_path = require_directory(
            absolute_path(target),
            label="native-job/v2 worktree target",
        )
        if worktree_path != source_specification.repository_path:
            raise WorkflowError(
                "native-job/v2 worktree_target disagrees with source-specification repository"
            )

    prompt_relative = str(value["prompt_path"])
    prompt_path = _resolve_relative(root, prompt_relative, "prompt_path")
    try:
        prompt_read = read_regular_file(prompt_path)
    except WorkflowError as exc:
        raise WorkflowError(f"prompt_path is not a regular file: {prompt_relative}") from exc

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

    raw_criteria = value.get("criteria", [])
    criteria = tuple(
        CriterionRequirement(
            id=str(item["id"]),
            description=(str(item["description"]) if item.get("description") is not None else None),
            acceptance_command_ids=tuple(
                str(command_id) for command_id in item.get("acceptance_command_ids", [])
            ),
        )
        for item in raw_criteria
        if isinstance(item, dict)
    )
    criterion_ids = [item.id for item in criteria]
    if len(criterion_ids) != len(set(criterion_ids)):
        raise WorkflowError("criteria contains duplicate criterion IDs")
    command_id_set = set(command_ids)
    for criterion in criteria:
        unknown = sorted(set(criterion.acceptance_command_ids) - command_id_set)
        if unknown:
            raise WorkflowError(
                f"criterion {criterion.id!r} references unknown acceptance commands: "
                + ", ".join(unknown)
            )

    review_data = value["review_requirement"]
    return ValidatedNativeJob(
        schema=schema,
        job_path=path,
        pack_root=root,
        job_id=str(value["job_id"]),
        ticket_id=str(value["ticket_id"]),
        prompt_path=prompt_path,
        prompt_bytes=prompt_read.data,
        job_bytes=job_read.data,
        job_sha256=job_read.sha256,
        bundle_provenance=bundle_provenance,
        source_specification=source_specification,
        prompt_relative_path=prompt_relative,
        worktree_target=worktree_target,
        worktree_path=worktree_path,
        path_policy=PathPolicy(allowed_paths=allowed, forbidden_paths=forbidden),
        acceptance_commands=commands,
        criteria=criteria,
        review_requirement=ReviewRequirement(
            required=bool(review_data["required"]),
            independent=bool(review_data.get("independent", False)),
        ),
    )
