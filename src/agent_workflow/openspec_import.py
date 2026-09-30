"""Qualified OpenSpec -> Agent-Workflow import boundary.

Phase 0 deliberately supports one narrow upstream contract:
OpenSpec 1.13.2, package-owned ``spec-driven`` schema v1, local Git repository.
The imported pack is self-contained for execution; OpenSpec is not consulted after
import. Planning provenance is frozen separately from Agent-Workflow execution
policy and acceptance authority.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from . import __version__
from .contracts import validate_instance
from .errors import WorkflowError
from .manifests import write_checksum_manifest
from .pack import scaffold
from .path import absolute_path, read_regular_file, require_directory
from .process import run
from .util import atomic_write_json, sha256_file, slug, utc_now

OPENSPEC_VERSION = "1.13.2"
OPENSPEC_SCHEMA_NAME = "spec-driven"
OPENSPEC_SCHEMA_VERSION = 1
SOURCE_SPECIFICATION_SCHEMA = "agent-workflow/source-specification-import/v1"
NATIVE_JOB_V2_SCHEMA = "agent-workflow/native-job/v2"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_change_name(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or len(path.parts) != 1
        or path.parts[0] in {".", ".."}
        or path.as_posix() != value
    ):
        raise WorkflowError(f"OpenSpec change must be one direct change name: {value!r}")
    return value


def _run_json(repository: Path, args: list[str]) -> tuple[Any, bytes, Any]:
    result = run(
        ["openspec", *args],
        cwd=repository,
        check=False,
        timeout_seconds=60,
        max_stdout_bytes=8 * 1024 * 1024,
        max_stderr_bytes=2 * 1024 * 1024,
        digest_executable=True,
    )
    raw = str(result.stdout).encode("utf-8")
    try:
        value = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        detail = str(result.stderr).strip()
        raise WorkflowError(
            f"OpenSpec command did not return JSON: {' '.join(args)}"
            + (f"; {detail}" if detail else "")
        ) from exc
    if result.returncode != 0:
        raise WorkflowError(
            f"OpenSpec command failed ({result.returncode}): {' '.join(args)}; "
            f"report_sha256={_sha256(raw)}"
        )
    return value, raw, result


def _git(repository: Path, *args: str) -> str:
    return str(
        run(
            ["git", "-C", str(repository), *args],
            check=True,
            timeout_seconds=30,
            max_stdout_bytes=2 * 1024 * 1024,
            max_stderr_bytes=512 * 1024,
        ).stdout
    ).strip()


def _git_state(repository: Path) -> dict[str, Any]:
    revision = _git(repository, "rev-parse", "HEAD")
    branch = _git(repository, "rev-parse", "--abbrev-ref", "HEAD")
    dirty_text = _git(repository, "status", "--porcelain=v1", "--untracked-files=all")
    return {
        "path": str(repository),
        "revision": revision,
        "branch": branch,
        "dirty": bool(dirty_text),
    }


def _require_local_clean_repository(repository: Path) -> dict[str, Any]:
    state = _git_state(repository)
    if state["dirty"]:
        raise WorkflowError(
            "OpenSpec Phase-0 import requires a clean Git repository; "
            "commit or intentionally isolate planning changes before import"
        )
    openspec_root = repository / "openspec"
    require_directory(openspec_root, label="local OpenSpec root")
    if (repository / ".openspec-store").exists():
        raise WorkflowError("OpenSpec stores are not supported by Phase-0 import")
    return state


def _schema_qualification(
    schemas: Any,
    templates: Any,
) -> dict[str, Any]:
    if not isinstance(schemas, list):
        raise WorkflowError("OpenSpec schemas --json returned an unexpected shape")
    matches = [
        item for item in schemas
        if isinstance(item, dict) and item.get("name") == OPENSPEC_SCHEMA_NAME
    ]
    if len(matches) != 1:
        raise WorkflowError("OpenSpec package must expose exactly one spec-driven schema")
    selected = matches[0]
    if selected.get("source") != "package":
        raise WorkflowError(
            "OpenSpec Phase-0 requires package-owned spec-driven; "
            f"resolved source was {selected.get('source')!r}"
        )
    if selected.get("artifacts") != ["proposal", "specs", "design", "tasks"]:
        raise WorkflowError("OpenSpec spec-driven artifact graph differs from the qualified surface")

    if not isinstance(templates, dict):
        raise WorkflowError("OpenSpec templates --json returned an unexpected shape")
    expected = {"proposal", "specs", "design", "tasks"}
    if set(templates) != expected:
        raise WorkflowError("OpenSpec spec-driven template inventory differs from the qualified surface")
    roots: set[Path] = set()
    template_records: list[dict[str, str]] = []
    for artifact_id in sorted(expected):
        record = templates.get(artifact_id)
        if not isinstance(record, dict) or record.get("source") != "package":
            raise WorkflowError(
                f"OpenSpec template {artifact_id!r} is not package-owned"
            )
        path_value = record.get("path")
        if not isinstance(path_value, str):
            raise WorkflowError(f"OpenSpec template {artifact_id!r} has no path")
        path = Path(path_value).expanduser().resolve()
        read = read_regular_file(path)
        if path.parent.name != "templates":
            raise WorkflowError(f"OpenSpec template has unexpected package layout: {path}")
        roots.add(path.parent.parent)
        template_records.append(
            {
                "id": artifact_id,
                "path": str(path),
                "sha256": read.sha256,
            }
        )
    if len(roots) != 1:
        raise WorkflowError("OpenSpec templates resolved from multiple schema roots")
    schema_root = next(iter(roots))
    schema_path = schema_root / "schema.yaml"
    schema_read = read_regular_file(schema_path)
    try:
        schema_value = yaml.safe_load(schema_read.data.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise WorkflowError(f"cannot parse resolved OpenSpec schema: {schema_path}") from exc
    if not isinstance(schema_value, dict):
        raise WorkflowError("resolved OpenSpec schema is not a mapping")
    if (
        schema_value.get("name") != OPENSPEC_SCHEMA_NAME
        or schema_value.get("version") != OPENSPEC_SCHEMA_VERSION
    ):
        raise WorkflowError(
            "OpenSpec resolved schema identity is outside the qualified surface: "
            f"{schema_value.get('name')!r} v{schema_value.get('version')!r}"
        )
    return {
        "name": OPENSPEC_SCHEMA_NAME,
        "version": OPENSPEC_SCHEMA_VERSION,
        "source": "package",
        "schema_path": str(schema_path),
        "schema_sha256": schema_read.sha256,
        "templates": template_records,
    }


def _relative_repository_path(repository: Path, path: Path, *, label: str) -> str:
    if path.is_symlink():
        raise WorkflowError(f"{label} may not be a symlink: {path}")
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(repository)
    except ValueError as exc:
        raise WorkflowError(f"{label} is outside the source repository: {path}") from exc
    value = relative.as_posix()
    if not value or any(part in {"", ".", ".."} for part in PurePosixPath(value).parts):
        raise WorkflowError(f"{label} has an unsafe repository path: {value!r}")
    return value


def _classify_artifact(relative: str, change_prefix: str) -> str:
    if relative in {"openspec/config.yaml", "openspec/config.yml"}:
        return "config"
    if relative == f"{change_prefix}/.openspec.yaml":
        return "change_config"
    if relative == f"{change_prefix}/proposal.md":
        return "proposal"
    if relative == f"{change_prefix}/design.md":
        return "design"
    if relative == f"{change_prefix}/tasks.md":
        return "tasks"
    if relative.startswith(f"{change_prefix}/specs/") and relative.endswith("/spec.md"):
        return "spec_delta"
    if relative.startswith("openspec/specs/") and relative.endswith("/spec.md"):
        return "current_spec"
    return "planning_support"


def _planning_artifacts(repository: Path, change: str) -> list[dict[str, str]]:
    change_root = repository / "openspec" / "changes" / change
    require_directory(change_root, label="OpenSpec change root")
    change_prefix = f"openspec/changes/{change}"
    candidates: list[Path] = []
    for config_name in ("config.yaml", "config.yml"):
        candidate = repository / "openspec" / config_name
        if candidate.is_file() or candidate.is_symlink():
            candidates.append(candidate)
    candidates.extend(
        path for path in sorted(change_root.rglob("*"))
        if path.is_file() or path.is_symlink()
    )
    specs_root = repository / "openspec" / "specs"
    if specs_root.is_dir():
        candidates.extend(
            path for path in sorted(specs_root.rglob("spec.md"))
            if path.is_file() or path.is_symlink()
        )

    seen: set[str] = set()
    records: list[dict[str, str]] = []
    for path in candidates:
        relative = _relative_repository_path(
            repository, path, label="OpenSpec planning artifact"
        )
        if relative in seen:
            continue
        seen.add(relative)
        read = read_regular_file(path, max_bytes=16 * 1024 * 1024)
        records.append(
            {
                "kind": _classify_artifact(relative, change_prefix),
                "path": relative,
                "sha256": read.sha256,
            }
        )
    required = {
        f"{change_prefix}/proposal.md",
        f"{change_prefix}/design.md",
        f"{change_prefix}/tasks.md",
    }
    missing = sorted(required - seen)
    if missing:
        raise WorkflowError(
            "OpenSpec planning is marked complete but required artifacts are missing: "
            + ", ".join(missing)
        )
    return records


def _task_map(repository: Path, change: str, apply_report: Any) -> list[dict[str, Any]]:
    if not isinstance(apply_report, dict):
        raise WorkflowError("OpenSpec apply instructions returned an unexpected shape")
    if apply_report.get("taskTrackingConfigured") is not True:
        raise WorkflowError("OpenSpec spec-driven task tracking is not configured")
    if apply_report.get("unavailableTrackingFiles"):
        raise WorkflowError("OpenSpec task tracking contains unreadable files")
    state = apply_report.get("state")
    if state not in {"ready", "all_done"}:
        raise WorkflowError(f"OpenSpec change is not apply-ready: state={state!r}")
    tasks = apply_report.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise WorkflowError("OpenSpec apply instructions contain no tracked tasks")

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in tasks:
        if not isinstance(item, dict):
            raise WorkflowError("OpenSpec apply task is not an object")
        locator = str(item.get("id", "")).strip()
        description = str(item.get("description", "")).strip()
        source_value = item.get("sourcePath")
        line = item.get("line")
        if not locator or not description or not isinstance(source_value, str):
            raise WorkflowError("OpenSpec apply task is missing id, description, or sourcePath")
        if not isinstance(line, int) or isinstance(line, bool) or line < 1:
            raise WorkflowError(f"OpenSpec task {locator!r} has invalid source line")
        source_path = Path(source_value).expanduser().resolve()
        relative = _relative_repository_path(
            repository, source_path, label=f"OpenSpec task {locator} source"
        )
        expected_source = f"openspec/changes/{change}/tasks.md"
        if relative != expected_source:
            raise WorkflowError(
                f"OpenSpec Phase-0 expects tasks from {expected_source}, got {relative}"
            )
        read = read_regular_file(source_path, max_bytes=4 * 1024 * 1024)
        try:
            lines = read.data.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise WorkflowError("OpenSpec tasks.md is not UTF-8") from exc
        if line > len(lines):
            raise WorkflowError(f"OpenSpec task {locator!r} line is outside tasks.md")
        source_line = lines[line - 1]
        if locator not in source_line:
            raise WorkflowError(
                f"OpenSpec task {locator!r} source line no longer contains its locator"
            )
        aw_id = f"openspec-{slug(change)}-{slug(locator)}"
        if aw_id in seen:
            raise WorkflowError(f"OpenSpec task mapping collides on Agent-Workflow ID: {aw_id}")
        seen.add(aw_id)
        records.append(
            {
                "agent_workflow_task_id": aw_id,
                "done_at_import": bool(item.get("done", False)),
                "source": {
                    "artifact": "tasks",
                    "locator": locator,
                    "path": relative,
                    "line": line,
                    "text_sha256": _sha256((source_line + "\n").encode("utf-8")),
                },
                "description": description,
                "description_sha256": _sha256(description.encode("utf-8")),
            }
        )
    return records


def _load_job_policy(path: Path) -> dict[str, Any]:
    read = read_regular_file(absolute_path(path), max_bytes=2 * 1024 * 1024)
    try:
        value = json.loads(read.data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"invalid OpenSpec import job policy: {path}") from exc
    if not isinstance(value, dict):
        raise WorkflowError("OpenSpec import job policy must be a JSON object")
    allowed_keys = {
        "path_policy",
        "acceptance_commands",
        "criteria",
        "review_requirement",
    }
    unknown = sorted(set(value) - allowed_keys)
    if unknown:
        raise WorkflowError(
            "OpenSpec import job policy contains unsupported fields: " + ", ".join(unknown)
        )
    path_policy = value.get("path_policy")
    if not isinstance(path_policy, dict):
        raise WorkflowError("OpenSpec import job policy requires path_policy")
    allowed = path_policy.get("allowed_paths")
    if not isinstance(allowed, list) or not allowed:
        raise WorkflowError("OpenSpec import job policy requires non-empty allowed_paths")
    forbidden = path_policy.get("forbidden_paths", [])
    if not isinstance(forbidden, list):
        raise WorkflowError("OpenSpec import job policy forbidden_paths must be a list")
    for item in [*allowed, *forbidden]:
        if (
            not isinstance(item, str)
            or not item
            or Path(item).is_absolute()
            or ".." in Path(item).parts
        ):
            raise WorkflowError(f"unsafe OpenSpec import path policy entry: {item!r}")
        if item == ".":
            raise WorkflowError("OpenSpec import path policy may not authorize the repository root")
    if any(PurePosixPath(str(item)).parts[:1] == ("openspec",) for item in allowed):
        raise WorkflowError("OpenSpec planning artifacts may not be writable execution scope")
    forbidden_values = [str(item) for item in forbidden]
    if "openspec" not in forbidden_values:
        forbidden_values.append("openspec")

    commands = value.get("acceptance_commands", [])
    criteria = value.get("criteria", [])
    review = value.get("review_requirement", {"required": False, "independent": False})
    if not isinstance(commands, list) or not isinstance(criteria, list) or not isinstance(review, dict):
        raise WorkflowError("OpenSpec import job policy has invalid execution fields")
    return {
        "path_policy": {
            "allowed_paths": [str(item) for item in allowed],
            "forbidden_paths": forbidden_values,
        },
        "acceptance_commands": commands,
        "criteria": criteria,
        "review_requirement": {
            "required": bool(review.get("required", False)),
            "independent": bool(review.get("independent", False)),
        },
    }


def _report_record(name: str, raw: bytes) -> dict[str, str]:
    return {
        "id": name,
        "path": f"source-reports/{name}.json",
        "sha256": _sha256(raw),
    }


def _write_report(destination: Path, record: dict[str, str], raw: bytes) -> None:
    path = destination / record["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _prompt(change: str, task: dict[str, Any], artifact_paths: list[str]) -> str:
    source = task["source"]
    return (
        f"# OpenSpec execution task — {source['locator']}\n\n"
        f"OpenSpec change: `{change}`\n"
        f"Frozen task: {task['description']}\n"
        f"Source: `{source['path']}:{source['line']}`\n\n"
        "The OpenSpec planning artifacts are frozen inputs for this Agent-Workflow run. "
        "Do not edit `openspec/` or mark OpenSpec task checkboxes complete; Agent-Workflow "
        "owns execution lifecycle and completion evidence after import.\n\n"
        "Read the relevant frozen planning artifacts before implementing. The imported "
        "artifact inventory includes:\n"
        + "\n".join(f"- `{path}`" for path in artifact_paths)
        + "\n\n"
        "Writable scope is controlled by the native Agent-Workflow job policy. "
        "Acceptance commands, tests, and review authority are host-owned; do not infer "
        "an executable acceptance test from OpenSpec verification prose. Stop if the "
        "requested task cannot be completed within the declared scope.\n"
    )


def import_openspec(
    repository: Path,
    change: str,
    destination: Path,
    *,
    job_policy: Path,
) -> dict[str, Any]:
    """Import one qualified OpenSpec change into a native Agent-Workflow pack."""

    repository = require_directory(absolute_path(repository), label="source repository")
    change = _safe_change_name(change)
    destination = absolute_path(destination)
    try:
        destination.relative_to(repository)
    except ValueError:
        pass
    else:
        raise WorkflowError(
            "OpenSpec Phase-0 destination must be outside the source repository "
            "so importing cannot mutate the frozen source revision"
        )
    if destination.exists() and any(destination.iterdir()):
        raise WorkflowError(f"destination is not empty: {destination}")

    repository_state = _require_local_clean_repository(repository)
    policy = _load_job_policy(job_policy)

    reports: dict[str, tuple[Any, bytes, Any]] = {}
    reports["version"] = _run_json(repository, ["version", "--json"])
    version_value = reports["version"][0]
    if not isinstance(version_value, dict) or version_value.get("version") != OPENSPEC_VERSION:
        raise WorkflowError(
            f"OpenSpec Phase-0 requires exact version {OPENSPEC_VERSION}; "
            f"observed {version_value.get('version') if isinstance(version_value, dict) else None!r}"
        )

    reports["schemas"] = _run_json(repository, ["schemas", "--json"])
    reports["templates"] = _run_json(
        repository, ["templates", "--schema", OPENSPEC_SCHEMA_NAME, "--json"]
    )
    workflow_schema = _schema_qualification(
        reports["schemas"][0], reports["templates"][0]
    )

    reports["status"] = _run_json(
        repository, ["status", "--change", change, "--json"]
    )
    status_value = reports["status"][0]
    if (
        not isinstance(status_value, dict)
        or status_value.get("changeName") != change
        or status_value.get("schemaName") != OPENSPEC_SCHEMA_NAME
        or status_value.get("isComplete") is not True
    ):
        raise WorkflowError("OpenSpec change planning artifacts are not complete")

    reports["validation"] = _run_json(
        repository,
        ["validate", change, "--strict", "--json", "--no-interactive"],
    )
    validation_value = reports["validation"][0]
    if not isinstance(validation_value, dict):
        raise WorkflowError("OpenSpec strict validation returned an unexpected shape")
    items = validation_value.get("items")
    if (
        not isinstance(items, list)
        or not any(
            isinstance(item, dict)
            and item.get("id") == change
            and item.get("type") == "change"
            and item.get("valid") is True
            for item in items
        )
    ):
        raise WorkflowError("OpenSpec strict validation did not prove the selected change valid")
    root_value = validation_value.get("root")
    if (
        not isinstance(root_value, dict)
        or Path(str(root_value.get("path", ""))).expanduser().resolve() != repository
        or root_value.get("source") != "nearest"
    ):
        raise WorkflowError(
            "OpenSpec Phase-0 supports only the local repository OpenSpec root"
        )

    reports["apply"] = _run_json(
        repository,
        ["instructions", "apply", "--change", change, "--json"],
    )
    reports["show"] = _run_json(
        repository, ["show", change, "--json", "--no-interactive"]
    )
    tasks = _task_map(repository, change, reports["apply"][0])
    pending = [item for item in tasks if not item["done_at_import"]]
    if not pending:
        raise WorkflowError("OpenSpec change contains no pending tasks to import")

    artifacts = _planning_artifacts(repository, change)
    artifact_paths = [item["path"] for item in artifacts]

    if _git_state(repository) != repository_state:
        raise WorkflowError("source repository changed while OpenSpec import was being qualified")

    scaffold(destination, 1, f"openspec-{change}")
    report_records: list[dict[str, str]] = []
    for name in ("version", "schemas", "templates", "status", "validation", "apply", "show"):
        raw = reports[name][1]
        record = _report_record(name, raw)
        _write_report(destination, record, raw)
        report_records.append(record)

    version_result = reports["version"][2]
    executable_sha256 = getattr(version_result, "executable_sha256", None)
    executable_path = getattr(version_result, "resolved_executable", None)
    if not isinstance(executable_sha256, str) or len(executable_sha256) != 64:
        raise WorkflowError("OpenSpec executable identity could not be content-addressed")

    receipt: dict[str, Any] = {
        "schema": SOURCE_SPECIFICATION_SCHEMA,
        "imported_at": utc_now(),
        "importer": {"name": "agent-workflow", "version": __version__},
        "provider": {
            "name": "openspec",
            "version": OPENSPEC_VERSION,
            "executable_path": executable_path,
            "executable_sha256": executable_sha256,
        },
        "workflow_schema": workflow_schema,
        "change": {"name": change},
        "planning_root": {"path": str(repository / "openspec"), "source": "nearest"},
        "repository": repository_state,
        "validation": {
            "passed": True,
            "report": next(item for item in report_records if item["id"] == "validation"),
        },
        "status": {
            "is_complete": True,
            "report": next(item for item in report_records if item["id"] == "status"),
        },
        "apply": {
            "state": str(reports["apply"][0].get("state")),
            "report": next(item for item in report_records if item["id"] == "apply"),
        },
        "reports": report_records,
        "artifacts": artifacts,
        "task_map": tasks,
    }
    validate_instance(receipt, SOURCE_SPECIFICATION_SCHEMA, artifact="OpenSpec import receipt")
    receipt_path = destination / "source-specification.json"
    atomic_write_json(receipt_path, receipt, mode=0o444)
    receipt_sha256 = sha256_file(receipt_path)

    phase = destination / "phase-0"
    tickets = phase / "tickets"
    for path in tickets.glob("*.md"):
        path.unlink()

    jobs_dir = destination / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    manifest_tasks: list[dict[str, Any]] = []
    for task in pending:
        task_id = task["agent_workflow_task_id"]
        prompt_rel = f"phase-0/tickets/{task_id}.md"
        (destination / prompt_rel).write_text(
            _prompt(change, task, artifact_paths),
            encoding="utf-8",
        )
        job_rel = f"jobs/{task_id}.json"
        job = {
            "schema": NATIVE_JOB_V2_SCHEMA,
            "job_id": task_id,
            "ticket_id": task_id,
            "source_specification": {
                "schema": SOURCE_SPECIFICATION_SCHEMA,
                "path": "source-specification.json",
                "sha256": receipt_sha256,
                "task_refs": [task_id],
            },
            "prompt_path": prompt_rel,
            "worktree_target": ".",
            **policy,
        }
        validate_instance(job, NATIVE_JOB_V2_SCHEMA, artifact=job_rel)
        atomic_write_json(destination / job_rel, job, mode=0o444)
        manifest_tasks.append(
            {
                "id": task_id,
                "tier": "implementation",
                "agent_run_id": task_id,
                "prompt": prompt_rel,
                "criteria": [
                    {
                        "id": str(item["id"]),
                        **(
                            {"description": str(item["description"])}
                            if item.get("description") is not None
                            else {}
                        ),
                    }
                    for item in policy["criteria"]
                    if isinstance(item, dict) and item.get("id")
                ],
            }
        )

    manifest = {
        "schema": "agent-workflow/prompt-pack/v1",
        "pack_id": f"openspec-{slug(change)}",
        "workflow": {
            "name": "agent-workflow",
            "minimum_version": __version__,
            "requires": [
                "source-specification-import-v1",
                "native-job-v2",
            ],
        },
        "phases": [
            {
                "id": "0",
                "name": f"OpenSpec {change}",
                "directory": "phase-0",
                "tasks": manifest_tasks,
            }
        ],
        "backlog_items": [],
    }
    (destination / "pack.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False),
        encoding="utf-8",
    )
    write_checksum_manifest(destination)
    return {
        "provider": f"openspec@{OPENSPEC_VERSION}",
        "change": change,
        "source_revision": repository_state["revision"],
        "destination": str(destination),
        "source_specification": str(receipt_path),
        "source_specification_sha256": receipt_sha256,
        "tasks": [item["agent_workflow_task_id"] for item in pending],
        "legacy_specgen_required": False,
    }
