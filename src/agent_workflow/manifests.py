from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - covered through forced fallback test
    yaml = None

from .miniyaml import MiniYamlError, load_task_manifest
from .evaluation import validate_evaluation
from .errors import WorkflowError
from .util import sha256_file


@dataclass
class ValidationReport:
    root: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    phases: int = 0
    tasks: int = 0

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
        text = path.read_text(encoding="utf-8")
        if yaml is not None:
            value = yaml.safe_load(text)
        else:
            value = load_task_manifest(text)
    except (OSError, MiniYamlError, ValueError) as exc:
        report.errors.append(f"{path.relative_to(report.root)}: invalid YAML: {exc}")
        return None
    except Exception as exc:
        if yaml is not None and exc.__class__.__module__.startswith("yaml"):
            report.errors.append(
                f"{path.relative_to(report.root)}: invalid YAML: {exc}"
            )
            return None
        raise
    if not isinstance(value, dict):
        report.errors.append(f"{path.relative_to(report.root)}: expected YAML mapping")
        return None
    return value


def _check_required(root: Path, report: ValidationReport) -> None:
    required = [
        "README.md",
        "EXECUTION_PROTOCOL.md",
        "DELEGATION_RUNBOOK.md",
        "templates/TICKET_COMPLETION.md",
        "templates/PHASE_GATE_REPORT.md",
        "templates/source-baseline.example.json",
    ]
    for rel in required:
        if not (root / rel).is_file():
            report.errors.append(f"missing required file: {rel}")


def validate_pack(root: Path, verify_checksums: bool = True) -> ValidationReport:
    root = root.resolve()
    report = ValidationReport(root=root)
    if not root.is_dir():
        report.errors.append(f"not a directory: {root}")
        return report
    _check_required(root, report)

    phase_dirs = sorted(path for path in root.glob("phase-*") if path.is_dir())
    if not phase_dirs:
        report.errors.append("no phase-* directories found")

    sessions: set[str] = set()
    ticket_ids: set[str] = set()
    for phase_dir in phase_dirs:
        report.phases += 1
        for rel in [
            "README.md",
            "MASTER_IMPLEMENTATION_PROMPT.md",
            "task-manifest.yaml",
            "tickets",
        ]:
            path = phase_dir / rel
            exists = path.is_dir() if rel == "tickets" else path.is_file()
            if not exists:
                report.errors.append(f"missing phase item: {path.relative_to(root)}")
        manifest_path = phase_dir / "task-manifest.yaml"
        if not manifest_path.is_file():
            continue
        manifest = _load_yaml(manifest_path, report)
        if manifest is None:
            continue
        tasks = manifest.get("tasks")
        order = manifest.get("mandatory_order", [])
        if not isinstance(tasks, list) or not tasks:
            report.errors.append(
                f"{manifest_path.relative_to(root)}: tasks must be a non-empty list"
            )
            continue

        local_ids: list[str] = []
        for index, task in enumerate(tasks):
            report.tasks += 1
            location = f"{manifest_path.relative_to(root)} task[{index}]"
            if not isinstance(task, dict):
                report.errors.append(f"{location}: expected mapping")
                continue
            missing = [
                key for key in ("id", "tier", "session", "prompt") if not task.get(key)
            ]
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
            prompt_path = (phase_dir / prompt_rel).resolve()
            try:
                prompt_display = prompt_path.relative_to(root)
            except ValueError:
                report.errors.append(
                    f"{location}: prompt escapes pack root: {prompt_rel}"
                )
                continue
            if not prompt_path.is_file():
                report.errors.append(f"{location}: prompt not found: {prompt_display}")
            else:
                text = prompt_path.read_text(encoding="utf-8", errors="replace").lower()
                concepts = ["writable", "acceptance", "test", "stop"]
                absent = [concept for concept in concepts if concept not in text]
                if absent:
                    report.warnings.append(
                        f"{prompt_display}: prompt may lack explicit "
                        + ", ".join(absent)
                    )

        if order:
            if not isinstance(order, list):
                report.errors.append(
                    f"{manifest_path.relative_to(root)}: mandatory_order must be a list"
                )
            else:
                ordered = {str(item) for item in order}
                unknown = [str(item) for item in order if str(item) not in local_ids]
                omitted = [item for item in local_ids if item not in ordered]
                if unknown:
                    report.errors.append(
                        f"{manifest_path.relative_to(root)}: unknown ordered tickets: {unknown}"
                    )
                if omitted:
                    report.warnings.append(
                        f"{manifest_path.relative_to(root)}: unordered tickets: {omitted}"
                    )

    evaluation_path = root / "evals" / "evaluation.json"
    if evaluation_path.is_file():
        try:
            validate_evaluation(
                evaluation_path,
                pack_root=root,
                task_ids=ticket_ids,
            )
        except WorkflowError as exc:
            report.errors.append(str(exc))

    checksum_file = root / "MANIFEST.sha256"
    if verify_checksums and checksum_file.is_file():
        listed: dict[str, str] = {}
        for line_number, line in enumerate(
            checksum_file.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            checksum, separator, rel = line.partition("  ")
            if not separator or len(checksum) != 64:
                report.errors.append(
                    f"MANIFEST.sha256:{line_number}: invalid checksum line"
                )
                continue
            if rel in listed:
                report.errors.append(
                    f"MANIFEST.sha256:{line_number}: duplicate path: {rel}"
                )
            listed[rel] = checksum

        actual = {
            path.relative_to(root).as_posix(): sha256_file(path)
            for path in _checksum_files(root, checksum_file)
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

    for path in root.rglob("*"):
        if path.is_symlink():
            try:
                path.resolve().relative_to(root)
            except (OSError, ValueError):
                report.errors.append(
                    f"symlink escapes pack root: {path.relative_to(root)}"
                )
    return report


def _checksum_files(root: Path, output: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path != output
        and not path.is_symlink()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    ]


def write_checksum_manifest(root: Path) -> Path:
    root = root.resolve()
    output = root / "MANIFEST.sha256"
    lines: list[str] = []
    for path in _checksum_files(root, output):
        lines.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
