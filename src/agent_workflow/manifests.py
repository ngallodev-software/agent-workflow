from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from .contracts import validate_instance
from .evaluation import validate_evaluation
from .errors import WorkflowError
from .path import absolute_path, inventory_tree, read_regular_file, require_directory
from .util import atomic_write_bytes

PROMPT_PACK_SCHEMA = "agent-workflow/prompt-pack/v1"
PROMPT_PACK_V2_SCHEMA = "agent-workflow/prompt-pack/v2"
PROMPT_PACK_MANIFEST = "pack.yaml"
ARCHIVE_MANIFEST = "MANIFEST.json"


@dataclass
class ValidationReport:
    root: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    phases: int = 0
    tasks: int = 0
    inventory: tuple[Any, ...] = field(default_factory=tuple, repr=False)
    pack_format: str | None = None
    manifest_version: str | None = None
    manifest_path: str | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "ok": self.ok,
            "phase_count": self.phases,
            "task_count": self.tasks,
            "pack_format": self.pack_format,
            "manifest_version": self.manifest_version,
            "manifest_path": self.manifest_path,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _load_yaml(path: Path, report: ValidationReport) -> dict[str, Any] | None:
    try:
        text = read_regular_file(path).data.decode("utf-8")
        value = yaml.safe_load(text)
    except (OSError, UnicodeDecodeError, ValueError, WorkflowError, yaml.YAMLError) as exc:
        report.errors.append(f"{path.relative_to(report.root)}: invalid YAML: {exc}")
        return None
    if not isinstance(value, dict):
        report.errors.append(f"{path.relative_to(report.root)}: expected YAML mapping")
        return None
    return value


def load_pack_manifest(root: Path) -> dict[str, Any]:
    """Read and schema-validate the authoritative prompt-pack manifest."""
    root = require_directory(root, label="pack root")
    path = root / PROMPT_PACK_MANIFEST
    report = ValidationReport(root=root)
    value = _load_yaml(path, report)
    if value is None:
        raise WorkflowError("; ".join(report.errors))
    _validate_prompt_pack_schema(value, artifact=str(path))
    return value


def _validate_prompt_pack_schema(value: dict[str, Any], *, artifact: str) -> str:
    """Validate a pack with the authority for its declared schema version."""
    schema_id = value.get("schema")
    if schema_id == PROMPT_PACK_SCHEMA:
        validate_instance(value, PROMPT_PACK_SCHEMA, artifact=artifact)
        return PROMPT_PACK_SCHEMA
    if schema_id == PROMPT_PACK_V2_SCHEMA:
        try:
            from specgen_contracts import negotiate, validate
            from specgen_contracts.bundle import schema_digest
        except ImportError as exc:
            raise WorkflowError(
                "prompt-pack/v2 requires the specgen-agent-workflow-contracts bundle"
            ) from exc
        diagnostics = validate(PROMPT_PACK_V2_SCHEMA, value)
        if diagnostics:
            details = "; ".join(
                f"{'.'.join(str(part) for part in item.get('path', [])) or '$'}: "
                f"{item.get('message', 'invalid value')}"
                for item in diagnostics[:20]
            )
            raise WorkflowError(f"invalid {artifact}: {details}")
        provenance = value["bundle_provenance"]
        try:
            negotiated = negotiate(
                bundle_version=provenance["bundle_version"],
                schema_id=provenance["schema_id"],
                schema_digest_value=provenance["schema_digest"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowError(
                f"incompatible prompt-pack bundle provenance: {exc}"
            ) from exc
        if negotiated["schema_digest"] != schema_digest(PROMPT_PACK_V2_SCHEMA):
            raise WorkflowError("incompatible prompt-pack bundle schema digest")
        return PROMPT_PACK_V2_SCHEMA
    raise WorkflowError(
        f"unsupported prompt-pack schema: {schema_id!r}; expected "
        f"{PROMPT_PACK_SCHEMA} or {PROMPT_PACK_V2_SCHEMA}; manual migration required"
    )


def _check_required(entries: dict[str, Any], report: ValidationReport) -> None:
    required = [
        PROMPT_PACK_MANIFEST,
        "README.md",
        "EXECUTION_PROTOCOL.md",
        "DELEGATION_RUNBOOK.md",
        "templates/TICKET_COMPLETION.md",
        "templates/PHASE_GATE_REPORT.md",
        "templates/source-baseline.example.json",
    ]
    for rel in required:
        entry = entries.get(rel)
        if entry is None or entry.kind != "file":
            report.errors.append(f"missing required file: {rel}")


def _safe_pack_relative(value: str, *, location: str, report: ValidationReport) -> str | None:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != value
    ):
        report.errors.append(f"{location}: path must be a normalized pack-relative POSIX path: {value}")
        return None
    return value


def _find_dependency_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            start = stack.index(node)
            return stack[start:] + [node]
        if node in visited:
            return None
        visiting.add(node)
        stack.append(node)
        for dependency in graph.get(node, []):
            cycle = visit(dependency)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in graph:
        cycle = visit(node)
        if cycle:
            return cycle
    return None


def _task_records(manifest: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for phase in manifest.get("phases", []):
        if not isinstance(phase, dict):
            continue
        for task in phase.get("tasks", []):
            if isinstance(task, dict):
                records.append((phase, task))
    return records


def task_result_contract(root: Path, ticket_id: str | None) -> dict[str, Any] | None:
    """Return the result contract declared for one prompt-pack ticket."""
    if not ticket_id:
        return None
    manifest = load_pack_manifest(root)
    for _phase, task in _task_records(manifest):
        if task.get("id") != ticket_id:
            continue
        contract = task.get("result_contract")
        return dict(contract) if isinstance(contract, dict) else None
    return None


def _validate_phase(
    root: Path,
    entries: dict[str, Any],
    phase: dict[str, Any],
    phase_index: int,
    report: ValidationReport,
    ticket_ids: set[str],
    agent_run_ids: set[str],
    dependencies: dict[str, list[str]],
    locations: dict[str, str],
) -> None:
    phase_location = f"pack.yaml phases[{phase_index}]"
    directory = str(phase.get("directory", ""))
    directory = _safe_pack_relative(directory, location=f"{phase_location}.directory", report=report) or ""
    if directory:
        directory_entry = entries.get(directory)
        if directory_entry is None or directory_entry.kind != "directory":
            report.errors.append(f"{phase_location}: phase directory not found: {directory}")
        elif "/" in directory:
            report.errors.append(f"{phase_location}: phase directory must be top-level: {directory}")
        for rel, kind in (
            ("README.md", "file"),
            ("MASTER_IMPLEMENTATION_PROMPT.md", "file"),
            ("tickets", "directory"),
        ):
            path = f"{directory}/{rel}"
            entry = entries.get(path)
            if entry is None or entry.kind != kind:
                report.errors.append(f"missing phase item: {path}")

    report.phases += 1
    local_ids: list[str] = []
    tasks = phase.get("tasks", [])
    for task_index, task in enumerate(tasks if isinstance(tasks, list) else []):
        report.tasks += 1
        location = f"{phase_location} tasks[{task_index}]"
        if not isinstance(task, dict):
            # JSON Schema normally catches this; keep domain traversal fail-closed.
            report.errors.append(f"{location}: expected mapping")
            continue
        task_id = str(task.get("id", ""))
        agent_run_id = str(task.get("agent_run_id", ""))
        local_ids.append(task_id)
        if task_id in ticket_ids:
            report.errors.append(f"{location}: duplicate ticket ID: {task_id}")
        ticket_ids.add(task_id)
        if agent_run_id in agent_run_ids:
            report.errors.append(f"{location}: duplicate agent run ID: {agent_run_id}")
        agent_run_ids.add(agent_run_id)
        locations[task_id] = location

        prompt_rel = str(task.get("prompt", ""))
        safe_prompt = _safe_pack_relative(prompt_rel, location=f"{location}.prompt", report=report)
        if safe_prompt:
            prompt_entry = entries.get(safe_prompt)
            if prompt_entry is None or prompt_entry.kind != "file":
                report.errors.append(f"{location}: prompt not found: {safe_prompt}")
            else:
                text = read_regular_file(root / safe_prompt).data.decode("utf-8", errors="replace").lower()
                absent = [concept for concept in ("writable", "acceptance", "test", "stop") if concept not in text]
                if absent:
                    report.warnings.append(
                        f"{safe_prompt}: prompt may lack explicit " + ", ".join(absent)
                    )
            if directory and not safe_prompt.startswith(f"{directory}/tickets/"):
                report.warnings.append(
                    f"{location}: prompt is outside the phase tickets directory: {safe_prompt}"
                )

        raw_dependencies = task.get("dependencies", []) or []
        dependencies[task_id] = list(raw_dependencies) if isinstance(raw_dependencies, list) else []

        result_contract = task.get("result_contract")
        if isinstance(result_contract, dict):
            schema_rel = str(result_contract.get("schema", ""))
            safe_schema = _safe_pack_relative(
                schema_rel,
                location=f"{location}.result_contract.schema",
                report=report,
            )
            if safe_schema:
                schema_entry = entries.get(safe_schema)
                if schema_entry is None or schema_entry.kind != "file":
                    report.errors.append(f"{location}: result contract schema not found: {safe_schema}")
                else:
                    try:
                        schema_value = json.loads(
                            read_regular_file(root / safe_schema).data.decode("utf-8")
                        )
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
                        report.errors.append(f"{location}: invalid result contract schema: {exc}")
                    else:
                        if not isinstance(schema_value, dict):
                            report.errors.append(f"{location}: result contract schema must be a JSON object")

    order = phase.get("mandatory_order", []) or []
    if isinstance(order, list):
        ordered = {str(item) for item in order}
        unknown = [str(item) for item in order if str(item) not in local_ids]
        omitted = [item for item in local_ids if item not in ordered]
        if unknown:
            report.errors.append(f"{phase_location}: unknown ordered tickets: {unknown}")
        if omitted:
            report.warnings.append(f"{phase_location}: unordered tickets: {omitted}")


def _validate_checksum_manifest(
    root: Path,
    inventory: tuple[Any, ...],
    entries: dict[str, Any],
    report: ValidationReport,
    verify_checksums: bool,
) -> None:
    checksum_file = root / "MANIFEST.sha256"
    if verify_checksums and entries.get("MANIFEST.sha256") is not None:
        listed: dict[str, str] = {}
        for line_number, line in enumerate(
            read_regular_file(checksum_file).data.decode("utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            checksum, separator, rel = line.partition("  ")
            if not separator or len(checksum) != 64:
                report.errors.append(f"MANIFEST.sha256:{line_number}: invalid checksum line")
                continue
            if rel in listed:
                report.errors.append(f"MANIFEST.sha256:{line_number}: duplicate path: {rel}")
            listed[rel] = checksum
        actual = {
            entry.path: str(entry.sha256)
            for entry in inventory
            if entry.kind == "file" and entry.path != "MANIFEST.sha256"
        }
        for rel in sorted(actual.keys() - listed.keys()):
            report.errors.append(f"MANIFEST.sha256: missing file: {rel}")
        for rel in sorted(listed.keys() - actual.keys()):
            report.errors.append(f"MANIFEST.sha256: lists nonexistent file: {rel}")
        for rel in sorted(actual.keys() & listed.keys()):
            if actual[rel] != listed[rel]:
                report.errors.append(f"MANIFEST.sha256: checksum mismatch: {rel}")
    elif verify_checksums:
        report.errors.append("MANIFEST.sha256: missing")




def _validate_archive_manifest(
    root: Path,
    inventory: tuple[Any, ...],
    entries: dict[str, Any],
    report: ValidationReport,
) -> None:
    entry = entries.get(ARCHIVE_MANIFEST)
    if entry is None:
        return
    if entry.kind != "file":
        report.errors.append(f"{ARCHIVE_MANIFEST}: expected file")
        return
    try:
        value = json.loads(read_regular_file(root / ARCHIVE_MANIFEST).data.decode("utf-8"))
        validate_instance(value, "agent-workflow/pack-manifest/v1", artifact=ARCHIVE_MANIFEST)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
        report.errors.append(f"{ARCHIVE_MANIFEST}: invalid archive integrity manifest: {exc}")
        return
    declared = {
        str(item.get("path")): item
        for item in value.get("entries", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    actual = {
        item.path: item
        for item in inventory
        if item.path not in {ARCHIVE_MANIFEST, "MANIFEST.sha256"}
    }
    missing = sorted(actual.keys() - declared.keys())
    extra = sorted(declared.keys() - actual.keys())
    for rel in missing:
        report.errors.append(f"{ARCHIVE_MANIFEST}: missing archive entry: {rel}")
    for rel in extra:
        report.errors.append(f"{ARCHIVE_MANIFEST}: lists nonexistent archive entry: {rel}")
    for rel in sorted(actual.keys() & declared.keys()):
        item = actual[rel]
        recorded = declared[rel]
        if recorded.get("type") != item.kind:
            report.errors.append(f"{ARCHIVE_MANIFEST}: type mismatch: {rel}")
            continue
        if recorded.get("size") != item.size:
            report.errors.append(f"{ARCHIVE_MANIFEST}: size mismatch: {rel}")
        if item.kind == "file" and recorded.get("sha256") != item.sha256:
            report.errors.append(f"{ARCHIVE_MANIFEST}: checksum mismatch: {rel}")

def validate_pack(root: Path, verify_checksums: bool = False) -> ValidationReport:
    root = absolute_path(root)
    report = ValidationReport(root=root)
    try:
        require_directory(root, label="pack root")
        inventory = inventory_tree(root)
    except WorkflowError as exc:
        report.errors.append(str(exc))
        return report
    entries = {entry.path: entry for entry in inventory}
    report.inventory = inventory
    report.pack_format = "prompt-pack"
    report.manifest_version = None
    report.manifest_path = PROMPT_PACK_MANIFEST

    _validate_archive_manifest(root, inventory, entries, report)
    _check_required(entries, report)

    manifest_entry = entries.get(PROMPT_PACK_MANIFEST)
    if manifest_entry is None or manifest_entry.kind != "file":
        _validate_checksum_manifest(root, inventory, entries, report, verify_checksums)
        return report

    manifest = _load_yaml(root / PROMPT_PACK_MANIFEST, report)
    if manifest is None:
        _validate_checksum_manifest(root, inventory, entries, report, verify_checksums)
        return report
    try:
        schema_id = _validate_prompt_pack_schema(manifest, artifact=PROMPT_PACK_MANIFEST)
    except WorkflowError as exc:
        report.errors.append(str(exc))
        _validate_checksum_manifest(root, inventory, entries, report, verify_checksums)
        return report
    report.manifest_version = schema_id.rsplit("/", 1)[-1]

    ticket_ids: set[str] = set()
    agent_run_ids: set[str] = set()
    dependencies: dict[str, list[str]] = {}
    locations: dict[str, str] = {}
    phases = manifest.get("phases", [])
    for phase_index, phase in enumerate(phases if isinstance(phases, list) else []):
        if isinstance(phase, dict):
            _validate_phase(
                root,
                entries,
                phase,
                phase_index,
                report,
                ticket_ids,
                agent_run_ids,
                dependencies,
                locations,
            )

    for ticket_id, required in dependencies.items():
        unknown = sorted(set(required) - ticket_ids)
        if unknown:
            report.errors.append(f"{locations.get(ticket_id, ticket_id)}: unknown dependencies: {unknown}")
        if ticket_id in required:
            report.errors.append(f"{locations.get(ticket_id, ticket_id)}: ticket cannot depend on itself")
    graph = {
        ticket_id: [dependency for dependency in required if dependency in ticket_ids]
        for ticket_id, required in dependencies.items()
    }
    cycle = _find_dependency_cycle(graph)
    if cycle:
        report.errors.append("dependency cycle: " + " -> ".join(cycle))

    evaluation_path = root / "evals" / "evaluation.json"
    if entries.get("evals/evaluation.json") is not None:
        try:
            validate_evaluation(evaluation_path, pack_root=root, task_ids=ticket_ids)
        except WorkflowError as exc:
            report.errors.append(str(exc))

    _validate_checksum_manifest(root, inventory, entries, report, verify_checksums)
    return report


def write_checksum_manifest(root: Path) -> Path:
    root = require_directory(root, label="pack root")
    output = root / "MANIFEST.sha256"
    inventory = inventory_tree(root)
    lines = [
        f"{entry.sha256}  {entry.path}"
        for entry in inventory
        if entry.kind == "file" and entry.path != "MANIFEST.sha256"
    ]
    atomic_write_bytes(output, ("\n".join(lines) + "\n").encode("utf-8"), mode=0o644)
    return output
