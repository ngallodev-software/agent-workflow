from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - covered through forced fallback test
    yaml = None

from .miniyaml import MiniYamlError, load_task_manifest
from .evaluation import validate_evaluation
from .errors import WorkflowError
from .path import absolute_path, inventory_tree, read_regular_file, require_directory
from .util import atomic_write_bytes


@dataclass
class ValidationReport:
    root: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    phases: int = 0
    tasks: int = 0
    inventory: tuple[Any, ...] = field(default_factory=tuple, repr=False)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "ok": self.ok,
            "phase_count": self.phases,
            "task_count": self.tasks,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _load_yaml(path: Path, report: ValidationReport) -> dict[str, Any] | None:
    try:
        text = read_regular_file(path).data.decode("utf-8")
        value = yaml.safe_load(text) if yaml is not None else load_task_manifest(text)
    except (OSError, UnicodeDecodeError, MiniYamlError, ValueError, WorkflowError) as exc:
        report.errors.append(f"{path.relative_to(report.root)}: invalid YAML: {exc}")
        return None
    except Exception as exc:
        if yaml is not None and exc.__class__.__module__.startswith("yaml"):
            report.errors.append(f"{path.relative_to(report.root)}: invalid YAML: {exc}")
            return None
        raise
    if not isinstance(value, dict):
        report.errors.append(f"{path.relative_to(report.root)}: expected YAML mapping")
        return None
    return value


def _check_required(root: Path, entries: dict[str, Any], report: ValidationReport) -> None:
    required = [
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


def task_result_contract(root: Path, ticket_id: str | None) -> dict[str, Any] | None:
    """Return the validated result contract declaration for one pack ticket."""
    if not ticket_id:
        return None
    root = require_directory(root, label="pack root")
    entries = {entry.path: entry for entry in inventory_tree(root)}
    for relative in sorted(
        path for path, entry in entries.items()
        if entry.kind == "file" and path.startswith("phase-") and path.count("/") == 1 and path.endswith("/task-manifest.yaml")
    ):
        manifest_path = root / relative
        report = ValidationReport(root=root)
        manifest = _load_yaml(manifest_path, report)
        if manifest is None:
            continue
        tasks = manifest.get("tasks")
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if not isinstance(task, dict) or str(task.get("id")) != ticket_id:
                continue
            contract = task.get("result_contract")
            return dict(contract) if isinstance(contract, dict) else None
    return None


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
    _check_required(root, entries, report)

    phase_dirs = sorted(
        root / entry.path
        for entry in inventory
        if entry.kind == "directory" and "/" not in entry.path and entry.path.startswith("phase-")
    )
    if not phase_dirs:
        report.errors.append("no phase-* directories found")

    sessions: set[str] = set()
    ticket_ids: set[str] = set()
    dependencies_by_ticket: dict[str, list[str]] = {}
    dependency_locations: dict[str, str] = {}
    for phase_dir in phase_dirs:
        report.phases += 1
        for rel in ["README.md", "MASTER_IMPLEMENTATION_PROMPT.md", "task-manifest.yaml", "tickets"]:
            path = phase_dir / rel
            relative = path.relative_to(root).as_posix()
            expected_kind = "directory" if rel == "tickets" else "file"
            if relative not in entries or entries[relative].kind != expected_kind:
                report.errors.append(f"missing phase item: {relative}")
        manifest_path = phase_dir / "task-manifest.yaml"
        manifest_rel = manifest_path.relative_to(root).as_posix()
        if manifest_rel not in entries or entries[manifest_rel].kind != "file":
            continue
        manifest = _load_yaml(manifest_path, report)
        if manifest is None:
            continue
        tasks = manifest.get("tasks")
        order = manifest.get("mandatory_order", [])
        if not isinstance(tasks, list) or not tasks:
            report.errors.append(f"{manifest_rel}: tasks must be a non-empty list")
            continue

        local_ids: list[str] = []
        for index, task in enumerate(tasks):
            report.tasks += 1
            location = f"{manifest_rel} task[{index}]"
            if not isinstance(task, dict):
                report.errors.append(f"{location}: expected mapping")
                continue
            missing = [key for key in ("id", "tier", "session", "prompt") if not task.get(key)]
            if missing:
                report.errors.append(f"{location}: missing {', '.join(missing)}")
                continue
            task_id = str(task["id"])
            session = str(task["session"])
            prompt_rel = str(task["prompt"])
            local_ids.append(task_id)
            if task_id in ticket_ids:
                report.errors.append(f"duplicate ticket ID across pack: {task_id}")
            ticket_ids.add(task_id)
            if session in sessions:
                report.errors.append(f"duplicate session ID across pack: {session}")
            sessions.add(session)
            prompt_path = phase_dir / prompt_rel
            try:
                prompt_display = prompt_path.relative_to(root).as_posix()
            except ValueError:
                report.errors.append(f"{location}: prompt escapes pack root: {prompt_rel}")
                continue
            prompt_entry = entries.get(prompt_display)
            if prompt_entry is None or prompt_entry.kind != "file":
                report.errors.append(f"{location}: prompt not found: {prompt_display}")
            else:
                text = read_regular_file(prompt_path).data.decode("utf-8", errors="replace").lower()
                absent = [concept for concept in ("writable", "acceptance", "test", "stop") if concept not in text]
                if absent:
                    report.warnings.append(f"{prompt_display}: prompt may lack explicit " + ", ".join(absent))

            dependencies = task.get("dependencies", [])
            if dependencies is None:
                dependencies = []
            if not isinstance(dependencies, list) or any(not isinstance(item, str) for item in dependencies):
                report.errors.append(f"{location}: dependencies must be a list of ticket IDs")
                dependencies = []
            dependencies_by_ticket[task_id] = list(dependencies)
            dependency_locations[task_id] = location

            result_contract = task.get("result_contract")
            if result_contract is not None:
                if not isinstance(result_contract, dict):
                    report.errors.append(f"{location}: result_contract must be a mapping")
                else:
                    schema_rel = result_contract.get("schema")
                    if not isinstance(schema_rel, str) or not schema_rel:
                        report.errors.append(f"{location}: result_contract.schema is required")
                    else:
                        schema_path = root / schema_rel
                        try:
                            schema_display = schema_path.relative_to(root).as_posix()
                        except ValueError:
                            report.errors.append(f"{location}: result contract schema escapes pack root: {schema_rel}")
                            schema_display = ""
                        schema_entry = entries.get(schema_display)
                        if schema_entry is None or schema_entry.kind != "file":
                            report.errors.append(f"{location}: result contract schema not found: {schema_rel}")
                        else:
                            try:
                                schema_value = json.loads(read_regular_file(schema_path).data.decode("utf-8"))
                            except (OSError, UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
                                report.errors.append(f"{location}: invalid result contract schema: {exc}")
                            else:
                                if not isinstance(schema_value, dict):
                                    report.errors.append(f"{location}: result contract schema must be a JSON object")

        if order:
            if not isinstance(order, list):
                report.errors.append(f"{manifest_rel}: mandatory_order must be a list")
            else:
                ordered = {str(item) for item in order}
                unknown = [str(item) for item in order if str(item) not in local_ids]
                omitted = [item for item in local_ids if item not in ordered]
                if unknown:
                    report.errors.append(f"{manifest_rel}: unknown ordered tickets: {unknown}")
                if omitted:
                    report.warnings.append(f"{manifest_rel}: unordered tickets: {omitted}")

    for ticket_id, dependencies in dependencies_by_ticket.items():
        unknown = sorted(set(dependencies) - ticket_ids)
        if unknown:
            report.errors.append(f"{dependency_locations[ticket_id]}: unknown dependencies: {unknown}")
        if ticket_id in dependencies:
            report.errors.append(f"{dependency_locations[ticket_id]}: ticket cannot depend on itself")
    known_graph = {ticket_id: [item for item in deps if item in ticket_ids] for ticket_id, deps in dependencies_by_ticket.items()}
    cycle = _find_dependency_cycle(known_graph)
    if cycle:
        report.errors.append("dependency cycle: " + " -> ".join(cycle))

    evaluation_path = root / "evals" / "evaluation.json"
    if entries.get("evals/evaluation.json") is not None:
        try:
            validate_evaluation(evaluation_path, pack_root=root, task_ids=ticket_ids)
        except WorkflowError as exc:
            report.errors.append(str(exc))

    checksum_file = root / "MANIFEST.sha256"
    if verify_checksums and entries.get("MANIFEST.sha256") is not None:
        listed: dict[str, str] = {}
        for line_number, line in enumerate(read_regular_file(checksum_file).data.decode("utf-8").splitlines(), 1):
            if not line.strip():
                continue
            checksum, separator, rel = line.partition("  ")
            if not separator or len(checksum) != 64:
                report.errors.append(f"MANIFEST.sha256:{line_number}: invalid checksum line")
                continue
            if rel in listed:
                report.errors.append(f"MANIFEST.sha256:{line_number}: duplicate path: {rel}")
            listed[rel] = checksum
        actual = {entry.path: str(entry.sha256) for entry in inventory if entry.kind == "file" and entry.path != "MANIFEST.sha256"}
        for rel in sorted(actual.keys() - listed.keys()):
            report.errors.append(f"MANIFEST.sha256: missing file: {rel}")
        for rel in sorted(listed.keys() - actual.keys()):
            report.errors.append(f"MANIFEST.sha256: lists nonexistent file: {rel}")
        for rel in sorted(actual.keys() & listed.keys()):
            if actual[rel] != listed[rel]:
                report.errors.append(f"MANIFEST.sha256: checksum mismatch: {rel}")
    elif verify_checksums:
        report.errors.append("MANIFEST.sha256: missing")
    return report


def write_checksum_manifest(root: Path) -> Path:
    root = require_directory(root, label="pack root")
    output = root / "MANIFEST.sha256"
    inventory = inventory_tree(root)
    lines = [f"{entry.sha256}  {entry.path}" for entry in inventory if entry.kind == "file" and entry.path != "MANIFEST.sha256"]
    atomic_write_bytes(output, ("\n".join(lines) + "\n").encode("utf-8"), mode=0o644)
    return output
