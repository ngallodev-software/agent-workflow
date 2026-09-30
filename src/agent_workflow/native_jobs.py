"""Validation boundary for versioned, JSON-only native prompt-pack jobs.

``native-job/v1`` remains the immutable SpecGen/shared-bundle compatibility
contract. ``native-job/v2`` is Agent-Workflow-owned and binds a frozen source
specification import without requiring the SpecGen contract bundle.
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
    """Legacy native-job/v1 path policy."""

    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]


@dataclass(frozen=True)
class ExecutionScope:
    """Agent-Workflow-native v2 scope vocabulary."""

    writable_paths: tuple[str, ...]
    writable_trees: tuple[str, ...]
    disposable_trees: tuple[str, ...]


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
    path: Path
    relative_path: str
    data: bytes
    sha256: str
    task_refs: tuple[str, ...]
    receipt: dict[str, Any]


@dataclass(frozen=True)
class ValidatedNativeJob:
    """A native job whose schema and pack-relative paths have been checked."""

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
    path_policy: PathPolicy | None
    scope: ExecutionScope | None
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
        raise WorkflowError(f"{label} escapes authorized root: {value}") from exc
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


def _source_specification(
    value: dict[str, Any],
    *,
    pack_root: Path,
) -> SourceSpecificationBinding:
    binding = value.get("source_specification")
    if not isinstance(binding, dict):
        raise WorkflowError("native-job/v2 is missing source_specification")
    relative = str(binding.get("path", ""))
    path = _resolve_relative(pack_root, relative, "source_specification.path")
    read = read_regular_file(path, max_bytes=8 * 1024 * 1024)
    expected_sha = str(binding.get("sha256", ""))
    if read.sha256 != expected_sha:
        raise WorkflowError(
            "native-job/v2 source specification digest mismatch: "
            f"expected {expected_sha}, got {read.sha256}"
        )
    try:
        receipt = json.loads(read.data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError("source specification receipt is not valid JSON") from exc
    if not isinstance(receipt, dict):
        raise WorkflowError("source specification receipt must be a JSON object")
    validate_instance(receipt, SOURCE_SPECIFICATION_SCHEMA, artifact=str(path))

    for report in receipt.get("reports", []):
        if not isinstance(report, dict):
            raise WorkflowError("source specification receipt contains invalid report metadata")
        report_path = _resolve_relative(pack_root, str(report.get("path", "")), "source report")
        report_read = read_regular_file(report_path, max_bytes=8 * 1024 * 1024)
        if report_read.sha256 != report.get("sha256"):
            raise WorkflowError(
                f"source specification report digest mismatch: {report.get('id')}"
            )

    task_refs = tuple(str(item) for item in binding.get("task_refs", []))
    known = {
        str(item.get("agent_workflow_task_id"))
        for item in receipt.get("task_map", [])
        if isinstance(item, dict)
    }
    unknown = sorted(set(task_refs) - known)
    if unknown:
        raise WorkflowError(
            "native-job/v2 references unknown source specification tasks: "
            + ", ".join(unknown)
        )
    return SourceSpecificationBinding(
        schema=SOURCE_SPECIFICATION_SCHEMA,
        path=path,
        relative_path=relative,
        data=read.data,
        sha256=read.sha256,
        task_refs=task_refs,
        receipt=receipt,
    )


def _git(workdir: Path, *args: str) -> str:
    return str(
        run(
            ["git", "-C", str(workdir), *args],
            check=True,
            timeout_seconds=30,
            max_stdout_bytes=2 * 1024 * 1024,
            max_stderr_bytes=512 * 1024,
        ).stdout
    ).strip()


def validate_source_specification_worktree(
    job: ValidatedNativeJob,
    workdir: Path,
) -> None:
    """Bind a v2 job to a clean checkout of the imported planning revision.

    The original absolute import path is provenance only. A delegated worktree
    may live elsewhere, but it must be the same clean Git revision and contain
    byte-identical planning inputs. OpenSpec itself is not required here.
    """

    source = job.source_specification
    if source is None:
        return
    root = require_directory(absolute_path(workdir), label="native-job/v2 source worktree")
    repository = source.receipt["repository"]
    head = _git(root, "rev-parse", "HEAD")
    if head != repository["revision"]:
        raise WorkflowError(
            "native-job/v2 worktree revision does not match frozen OpenSpec import: "
            f"{head} != {repository['revision']}"
        )
    dirty = bool(_git(root, "status", "--porcelain=v1", "--untracked-files=all"))
    if dirty:
        raise WorkflowError(
            "native-job/v2 source worktree must be clean at launch; "
            "prepare a fresh worktree from the imported revision"
        )
    for artifact in source.receipt.get("artifacts", []):
        if not isinstance(artifact, dict):
            raise WorkflowError("source specification contains invalid artifact metadata")
        relative = str(artifact.get("path", ""))
        path = _resolve_relative(root, relative, "source specification artifact")
        read = read_regular_file(path, max_bytes=16 * 1024 * 1024)
        if read.sha256 != artifact.get("sha256"):
            raise WorkflowError(
                "source specification artifact drifted since import: " + relative
            )


def validate_native_job(job_path: Path, *, pack_root: Path) -> ValidatedNativeJob:
    """Read and validate a v1 or v2 native job without starting execution."""

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
            f"unsupported native job schema in {path}: {schema!r}; "
            f"expected {NATIVE_JOB_SCHEMA} or {NATIVE_JOB_V2_SCHEMA}"
        )
    assert isinstance(schema, str)
    validate_instance(value, schema, artifact=str(path))

    bundle_provenance: dict[str, Any] | None = None
    source_specification: SourceSpecificationBinding | None = None
    if schema == NATIVE_JOB_SCHEMA:
        bundle_provenance = negotiate_bundle(value.get("bundle_provenance"))
    else:
        source_specification = _source_specification(value, pack_root=root)

    prompt_relative = str(value["prompt_path"])
    prompt_path = _resolve_relative(root, prompt_relative, "prompt_path")
    try:
        prompt_read = read_regular_file(prompt_path)
    except WorkflowError as exc:
        raise WorkflowError(f"prompt_path is not a regular file: {prompt_relative}") from exc

    worktree_target = str(value["worktree_target"])
    if schema == NATIVE_JOB_SCHEMA:
        _validate_policy_path(worktree_target, "worktree_target")
    elif worktree_target != ".":
        raise WorkflowError("native-job/v2 Phase-0 worktree_target must be '.'")

    path_policy: PathPolicy | None = None
    execution_scope: ExecutionScope | None = None
    if schema == NATIVE_JOB_SCHEMA:
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
        path_policy = PathPolicy(allowed_paths=allowed, forbidden_paths=forbidden)
    else:
        scope_data = value["scope"]
        writable_paths = tuple(
            _validate_policy_path(str(item), "writable_paths entry")
            for item in scope_data.get("writable_paths", [])
        )
        writable_trees = tuple(
            _validate_policy_path(str(item), "writable_trees entry")
            for item in scope_data.get("writable_trees", [])
        )
        disposable_trees = tuple(
            _validate_policy_path(str(item), "disposable_trees entry")
            for item in scope_data.get("disposable_trees", [])
        )
        protected = (*writable_paths, *writable_trees, *disposable_trees)
        if any(Path(item).parts[:1] == ("openspec",) for item in protected):
            raise WorkflowError(
                "native-job/v2 may not authorize OpenSpec planning artifacts as writable or disposable"
            )
        execution_scope = ExecutionScope(
            writable_paths=writable_paths,
            writable_trees=writable_trees,
            disposable_trees=disposable_trees,
        )

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
        path_policy=path_policy,
        scope=execution_scope,
        acceptance_commands=commands,
        criteria=criteria,
        review_requirement=ReviewRequirement(
            required=bool(review_data["required"]),
            independent=bool(review_data.get("independent", False)),
        ),
    )
