"""Qualified OpenSpec 1.13.2 -> Agent-Workflow import boundary.

Phase 0 deliberately targets only the built-in package-owned spec-driven/v1
workflow in one local Git repository.  OpenSpec remains planning authority;
this module freezes the exact source bytes and lowers tasks into Agent-Workflow
owned execution contracts without treating planning prose as acceptance authority.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any, Iterable

import yaml

from . import __version__
from .contracts import validate_instance
from .errors import WorkflowError
from .eval.commands import specs_from_data
from .manifests import validate_pack, write_checksum_manifest
from .pack import scaffold
from .path import absolute_path, read_regular_file, require_directory
from .process import run
from .util import atomic_write_bytes, atomic_write_json, sha256_bytes, slug, utc_now, validate_id

OPENSPEC_VERSION = "1.13.2"
OPENSPEC_SCHEMA = "spec-driven"
OPENSPEC_SCHEMA_VERSION = 1
IMPORT_SCHEMA = "agent-workflow/source-specification-import/v1"
NATIVE_JOB_V2_SCHEMA = "agent-workflow/native-job/v2"


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _command_json(repository: Path, args: list[str]) -> tuple[Any, str]:
    result = run(
        args,
        cwd=repository,
        check=False,
        timeout_seconds=120,
        max_stdout_bytes=4 * 1024 * 1024,
        max_stderr_bytes=512 * 1024,
    )
    stdout = str(result.stdout)
    digest = sha256_bytes(stdout.encode("utf-8"))
    if result.returncode:
        detail = str(result.stderr or result.stdout).strip()
        raise WorkflowError(
            f"OpenSpec command failed ({result.returncode}): {' '.join(args)}"
            + (f"\n{detail}" if detail else "")
        )
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"OpenSpec command did not return JSON: {' '.join(args)}") from exc
    return value, digest


def _git(repository: Path, *args: str) -> str:
    result = run(["git", "-C", str(repository), *args], check=True, timeout_seconds=30)
    return str(result.stdout).strip()


def _git_state(repository: Path) -> dict[str, Any]:
    return {
        "path": str(repository),
        "revision": _git(repository, "rev-parse", "HEAD"),
        "branch": _git(repository, "rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(_git(repository, "status", "--porcelain")),
    }


def _provider_version(repository: Path) -> str:
    result = run(["openspec", "version"], cwd=repository, check=False, timeout_seconds=30)
    if result.returncode:
        raise WorkflowError("OpenSpec is required for OpenSpec import")
    match = re.search(r"(?<!\d)(\d+\.\d+\.\d+)(?!\d)", str(result.stdout or result.stderr))
    if not match:
        raise WorkflowError("could not determine OpenSpec version")
    version = match.group(1)
    if version != OPENSPEC_VERSION:
        raise WorkflowError(
            f"unsupported OpenSpec version {version}; Phase 0 requires exactly {OPENSPEC_VERSION}"
        )
    return version


def _reject_store_or_project_override(repository: Path) -> None:
    config_path = repository / "openspec" / "config.yaml"
    if not config_path.is_file():
        config_path = repository / "openspec" / "config.yml"
    if config_path.is_file():
        try:
            config = yaml.safe_load(read_regular_file(config_path).data.decode("utf-8")) or {}
        except (UnicodeDecodeError, yaml.YAMLError, WorkflowError) as exc:
            raise WorkflowError(f"cannot read OpenSpec project config: {config_path}") from exc
        if isinstance(config, dict) and config.get("store"):
            raise WorkflowError("OpenSpec stores are outside the Phase-0 import surface")
    if (repository / "openspec" / "schemas" / OPENSPEC_SCHEMA).exists():
        raise WorkflowError(
            "project-local spec-driven schema overrides are outside the Phase-0 import surface"
        )


def _qualify_schema(repository: Path) -> dict[str, Any]:
    schemas, _ = _command_json(repository, ["openspec", "schemas", "--json"])
    if not isinstance(schemas, list):
        raise WorkflowError("OpenSpec schemas --json returned an unexpected shape")
    matches = [
        item for item in schemas
        if isinstance(item, dict) and item.get("name") == OPENSPEC_SCHEMA
    ]
    if len(matches) != 1 or matches[0].get("source") != "package":
        raise WorkflowError("Phase 0 requires the package-owned spec-driven schema")

    templates, _ = _command_json(
        repository, ["openspec", "templates", "--schema", OPENSPEC_SCHEMA, "--json"]
    )
    if not isinstance(templates, dict) or not templates:
        raise WorkflowError("OpenSpec templates --json returned an unexpected shape")

    resolved_templates: dict[str, dict[str, str]] = {}
    schema_roots: set[Path] = set()
    for artifact_id, record in templates.items():
        if not isinstance(record, dict) or record.get("source") != "package":
            raise WorkflowError(
                f"OpenSpec template {artifact_id!r} is not package-owned; overrides are unsupported"
            )
        raw_path = record.get("path")
        if not isinstance(raw_path, str):
            raise WorkflowError(f"OpenSpec template {artifact_id!r} has no resolved path")
        path = Path(raw_path).expanduser().resolve()
        read = read_regular_file(path)
        schema_roots.add(path.parent.parent)
        resolved_templates[str(artifact_id)] = {
            "path": str(path),
            "sha256": read.sha256,
        }
    if len(schema_roots) != 1:
        raise WorkflowError("OpenSpec package templates resolved from multiple schema roots")
    schema_path = next(iter(schema_roots)) / "schema.yaml"
    schema_read = read_regular_file(schema_path)
    try:
        schema_value = yaml.safe_load(schema_read.data.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise WorkflowError("OpenSpec package schema.yaml is unreadable") from exc
    if (
        not isinstance(schema_value, dict)
        or schema_value.get("name") != OPENSPEC_SCHEMA
        or schema_value.get("version") != OPENSPEC_SCHEMA_VERSION
    ):
        raise WorkflowError(
            "OpenSpec resolved schema is not the qualified spec-driven schema version 1"
        )
    return {
        "name": OPENSPEC_SCHEMA,
        "version": OPENSPEC_SCHEMA_VERSION,
        "source": "package",
        "schema_sha256": schema_read.sha256,
        "templates": resolved_templates,
    }


def _extract_context_paths(context_files: Any) -> list[tuple[str, Path]]:
    records: list[tuple[str, Path]] = []

    def add(kind: str, value: Any) -> None:
        if isinstance(value, str):
            records.append((kind, Path(value).expanduser().resolve()))
        elif isinstance(value, list):
            for item in value:
                add(kind, item)
        elif isinstance(value, dict):
            path = value.get("path") or value.get("sourcePath") or value.get("outputPath")
            if isinstance(path, str):
                records.append((kind, Path(path).expanduser().resolve()))
            else:
                for child in value.values():
                    add(kind, child)

    if isinstance(context_files, dict):
        for kind, value in context_files.items():
            add(str(kind), value)
    elif isinstance(context_files, list):
        for item in context_files:
            if isinstance(item, dict):
                kind = str(item.get("id") or item.get("kind") or "context")
                add(kind, item)
            else:
                add("context", item)
    return records


def _safe_source_file(repository: Path, path: Path) -> tuple[str, bytes, str]:
    root = repository / "openspec"
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise WorkflowError(f"OpenSpec source artifact is outside the local planning root: {path}") from exc
    read = read_regular_file(path)
    source_relative = (Path("openspec") / relative).as_posix()
    stored = (Path("source") / source_relative).as_posix()
    return stored, read.data, read.sha256


def _task_id(change: str, locator: str) -> str:
    digest = hashlib.sha256(f"{change}\0{locator}".encode("utf-8")).hexdigest()[:10]
    value = f"openspec-{slug(change)}-{slug(locator)}-{digest}"
    return validate_id(value[:128], "OpenSpec-derived task ID")


def _load_acceptance_commands(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        value = json.loads(read_regular_file(path).data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
        raise WorkflowError(f"cannot read acceptance command JSON: {path}") from exc
    if not isinstance(value, list):
        raise WorkflowError("acceptance command JSON must contain an array")
    specs = specs_from_data(value)
    return [
        {
            "id": item.id,
            "argv": list(item.argv),
            "cwd": item.cwd,
            "timeout_seconds": item.timeout_seconds,
            "result_format": item.result_format,
            "junit_path": item.junit_path,
        }
        for item in specs
    ]


def import_openspec_change(
    repository: Path,
    change: str,
    destination: Path,
    *,
    allowed_paths: Iterable[str],
    forbidden_paths: Iterable[str] = (),
    acceptance_commands_path: Path | None = None,
    review_required: bool = False,
    independent_review: bool = False,
    allow_dirty: bool = False,
) -> dict[str, Any]:
    repository = require_directory(absolute_path(repository), label="OpenSpec repository")
    destination = absolute_path(destination)
    try:
        destination.relative_to(repository)
    except ValueError:
        pass
    else:
        raise WorkflowError(
            "Phase-0 OpenSpec import output must be outside the source repository so import cannot dirty its baseline"
        )
    if destination.exists() and any(destination.iterdir()):
        raise WorkflowError(f"destination is not empty: {destination}")

    allow = tuple(str(item) for item in allowed_paths)
    deny = tuple(str(item) for item in forbidden_paths)
    if not allow:
        raise WorkflowError("OpenSpec import requires at least one explicit --allow-path")
    for value in (*allow, *deny):
        candidate = Path(value)
        if candidate.is_absolute() or value in {"", "."} or any(part == ".." for part in candidate.parts):
            raise WorkflowError(f"OpenSpec import path policy must be repository-relative: {value!r}")
    if set(allow) & set(deny):
        raise WorkflowError("OpenSpec import path policy contains paths that are both allowed and forbidden")

    _reject_store_or_project_override(repository)
    provider_version = _provider_version(repository)
    workflow_schema = _qualify_schema(repository)
    before = _git_state(repository)
    if before["dirty"] and not allow_dirty:
        raise WorkflowError("source repository is dirty; pass --allow-dirty to bind that exact baseline")

    status_argv = ["openspec", "status", "--change", change, "--json"]
    status, status_sha = _command_json(repository, status_argv)
    if not isinstance(status, dict):
        raise WorkflowError("OpenSpec status returned an unexpected shape")
    if status.get("schemaName") != OPENSPEC_SCHEMA or status.get("isComplete") is not True:
        raise WorkflowError("OpenSpec planning artifacts are not complete under spec-driven")

    validation_argv = [
        "openspec", "validate", change, "--strict", "--json", "--no-interactive"
    ]
    validation, validation_sha = _command_json(repository, validation_argv)
    if not isinstance(validation, dict):
        raise WorkflowError("OpenSpec validation returned an unexpected shape")
    items = validation.get("items")
    if not isinstance(items, list) or not any(
        isinstance(item, dict) and item.get("id") == change and item.get("valid") is True
        for item in items
    ):
        raise WorkflowError("OpenSpec strict validation did not establish the requested change as valid")

    apply_argv = ["openspec", "instructions", "apply", "--change", change, "--json"]
    apply, apply_sha = _command_json(repository, apply_argv)
    if not isinstance(apply, dict) or apply.get("state") not in {"ready", "all_done"}:
        raise WorkflowError("OpenSpec apply instructions are not ready")
    root_record = apply.get("root")
    root_path = (
        Path(root_record.get("path")).expanduser().resolve()
        if isinstance(root_record, dict) and isinstance(root_record.get("path"), str)
        else None
    )
    if root_path != repository:
        raise WorkflowError("OpenSpec resolved a store or non-local planning root; Phase 0 requires the repository root")

    tasks = apply.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise WorkflowError("OpenSpec apply instructions contain no trackable tasks")

    source_records: dict[Path, str] = {}
    for kind, path in _extract_context_paths(apply.get("contextFiles")):
        source_records.setdefault(path, kind)
    for task in tasks:
        if not isinstance(task, dict):
            raise WorkflowError("OpenSpec apply task is not an object")
        source_path = task.get("sourcePath")
        if not isinstance(source_path, str):
            raise WorkflowError("OpenSpec apply task has no sourcePath")
        source_records.setdefault(Path(source_path).expanduser().resolve(), "tasks")

    artifact_payloads: list[tuple[str, str, bytes, str]] = []
    artifacts: list[dict[str, str]] = []
    for path, kind in sorted(source_records.items(), key=lambda item: str(item[0])):
        stored, data, digest = _safe_source_file(repository, path)
        source_rel = path.relative_to(repository).as_posix()
        artifact_payloads.append((kind, stored, data, digest))
        artifacts.append(
            {
                "kind": kind,
                "source_path": source_rel,
                "stored_path": stored,
                "sha256": digest,
            }
        )

    task_map: list[dict[str, Any]] = []
    for task in tasks:
        locator = str(task.get("id", "")).strip()
        description = str(task.get("description", "")).strip()
        source_path = Path(str(task["sourcePath"])).expanduser().resolve()
        line = task.get("line")
        if not locator or not description or not isinstance(line, int) or line < 1:
            raise WorkflowError("OpenSpec task is missing id, description, or source line")
        _safe_source_file(repository, source_path)
        task_map.append(
            {
                "agent_workflow_task_id": _task_id(change, locator),
                "description": description,
                "source": {
                    "artifact": "tasks",
                    "locator": locator,
                    "text_sha256": _sha_text(description),
                    "source_path": source_path.relative_to(repository).as_posix(),
                    "line": line,
                },
            }
        )

    after_observation = _git_state(repository)
    if after_observation != before:
        raise WorkflowError("source repository drifted while OpenSpec import evidence was being collected")

    receipt = {
        "schema": IMPORT_SCHEMA,
        "provider": {"name": "openspec", "version": provider_version},
        "workflow_schema": workflow_schema,
        "change": {"name": change},
        "repository": before,
        "validation": {"argv": validation_argv, "sha256": validation_sha},
        "status": {
            "argv": status_argv,
            "sha256": status_sha,
            "is_complete": True,
        },
        "apply": {
            "argv": apply_argv,
            "sha256": apply_sha,
            "state": str(apply["state"]),
        },
        "artifacts": artifacts,
        "task_map": task_map,
        "importer": {"name": "agent-workflow", "version": __version__},
        "created_at": utc_now(),
    }
    validate_instance(receipt, IMPORT_SCHEMA, artifact="OpenSpec import receipt")

    commands = _load_acceptance_commands(
        absolute_path(acceptance_commands_path) if acceptance_commands_path is not None else None
    )
    command_ids = [item["id"] for item in commands]
    destination.mkdir(parents=True, exist_ok=True)
    scaffold(destination, 1, f"openspec-{change}")

    for _kind, stored, data, digest in artifact_payloads:
        target = destination / stored
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(target, data, mode=0o444)
        if read_regular_file(target).sha256 != digest:
            raise WorkflowError(f"copied OpenSpec artifact digest mismatch: {stored}")

    receipt_path = destination / "source-specification.json"
    atomic_write_json(receipt_path, receipt, mode=0o444)
    receipt_sha = read_regular_file(receipt_path).sha256

    phase_dir = destination / "phase-0"
    tickets_dir = phase_dir / "tickets"
    jobs_dir = destination / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    pack_tasks: list[dict[str, Any]] = []
    order: list[str] = []

    artifact_lines = [
        f"- {item['kind']}: `{item['stored_path']}` (sha256 {item['sha256']})"
        for item in artifacts
    ]
    for mapping in task_map:
        task_id = mapping["agent_workflow_task_id"]
        order.append(task_id)
        prompt_rel = f"phase-0/tickets/{task_id}.md"
        prompt = [
            f"# OpenSpec task {mapping['source']['locator']}",
            "",
            f"- Agent-Workflow task: `{task_id}`",
            f"- OpenSpec change: `{change}`",
            f"- Source task locator: `{mapping['source']['locator']}`",
            f"- Source task text SHA-256: `{mapping['source']['text_sha256']}`",
            "",
            "## Task",
            mapping["description"],
            "",
            "## Frozen planning context",
            *artifact_lines,
            "",
            "## Execution boundary",
            "- Implement only this bounded task within the host-declared writable path policy.",
            "- OpenSpec planning text is source intent, not executable acceptance authority.",
            "- Do not claim checks you did not perform and do not reconstruct hidden evaluator/oracle material.",
            "- Agent-Workflow owns deterministic acceptance-command execution, evidence collection, review, and acceptance.",
            "- Stop and report a limitation if the frozen planning artifacts are insufficient or contradictory.",
            "",
        ]
        atomic_write_bytes(
            destination / prompt_rel,
            ("\n".join(prompt)).encode("utf-8"),
            mode=0o644,
        )
        criterion_id = validate_id(f"{task_id}-source-task", "criterion ID")
        criteria = [
            {
                "id": criterion_id,
                "description": mapping["description"],
                "acceptance_command_ids": command_ids,
            }
        ]
        native = {
            "schema": NATIVE_JOB_V2_SCHEMA,
            "job_id": task_id,
            "ticket_id": task_id,
            "source_specification": {
                "schema": IMPORT_SCHEMA,
                "path": "source-specification.json",
                "sha256": receipt_sha,
                "task_refs": [task_id],
            },
            "prompt_path": prompt_rel,
            "worktree_target": str(repository),
            "path_policy": {
                "allowed_paths": list(allow),
                "forbidden_paths": list(deny),
            },
            "acceptance_commands": commands,
            "criteria": criteria,
            "review_requirement": {
                "required": bool(review_required or independent_review),
                "independent": bool(independent_review),
            },
        }
        validate_instance(native, NATIVE_JOB_V2_SCHEMA, artifact=f"native job {task_id}")
        atomic_write_json(jobs_dir / f"{task_id}.json", native, mode=0o644)
        pack_tasks.append(
            {
                "id": task_id,
                "tier": "medium",
                "agent_run_id": validate_id(f"{task_id}-run", "agent run ID"),
                "prompt": prompt_rel,
                "criteria": [{"id": criterion_id, "description": mapping["description"]}],
            }
        )

    pack = {
        "schema": "agent-workflow/prompt-pack/v1",
        "pack_id": validate_id(f"openspec-{slug(change)}", "pack ID"),
        "workflow": {
            "name": "agent-workflow",
            "minimum_version": __version__,
            "requires": [
                "durable_agent_run",
                "source_specification_import",
                "source_baseline",
                "completion_report",
            ],
        },
        "phases": [
            {
                "id": "0",
                "name": f"OpenSpec {change}",
                "directory": "phase-0",
                "mandatory_order": order,
                "tasks": pack_tasks,
            }
        ],
        "backlog_items": [],
    }
    (destination / "pack.yaml").write_text(
        yaml.safe_dump(pack, sort_keys=False),
        encoding="utf-8",
    )
    write_checksum_manifest(destination)
    report = validate_pack(destination, verify_checksums=True)
    if not report.ok:
        raise WorkflowError(
            "generated OpenSpec-backed prompt pack failed validation: "
            + "; ".join(report.errors)
        )

    final_state = _git_state(repository)
    if final_state != before:
        raise WorkflowError("source repository drifted before OpenSpec import completed")

    return {
        "status": "imported",
        "repository": str(repository),
        "change": change,
        "destination": str(destination),
        "provider_version": provider_version,
        "schema": f"{OPENSPEC_SCHEMA}/v{OPENSPEC_SCHEMA_VERSION}",
        "source_specification": str(receipt_path),
        "source_specification_sha256": receipt_sha,
        "tasks": [item["agent_workflow_task_id"] for item in task_map],
        "jobs": [f"jobs/{item['agent_workflow_task_id']}.json" for item in task_map],
        "validation": report.as_dict(),
    }
