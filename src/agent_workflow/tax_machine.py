"""Strict, adapter-local boundary for Tax Machine prompt packs.

This module intentionally does not use ``contracts``: an external pack must
never extend the runtime's global schema lookup.  Only the three fixed schema
names below and their contained local references are trusted.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import WorkflowError

ADAPTER = "tax-machine"
ADAPTER_VERSION = "1"
_FILES = ("MANIFEST.json", "schemas/job.schema.json", "schemas/completion.schema.json")


def _regular(root: Path, relative: str) -> Path:
    candidate = root / relative
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
        mode = candidate.lstat().st_mode
    except (OSError, ValueError) as exc:
        raise WorkflowError(f"Tax Machine required path is unsafe or missing: {relative}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise WorkflowError(f"Tax Machine required path must be regular and non-symlink: {relative}")
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise WorkflowError(f"invalid Tax Machine JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"Tax Machine JSON must be an object: {path}")
    return value


@dataclass(frozen=True)
class TaxMachinePack:
    root: Path
    manifest: Path
    job_schema: Path
    completion_schema: Path

    def snapshot(self, run_dir: Path, job_path: Path) -> dict[str, dict[str, str]]:
        safe_job = _regular(self.root, str(job_path.resolve().relative_to(self.root)))
        entries = {"manifest": self.manifest, "job": safe_job, "job_schema": self.job_schema,
                   "completion_schema": self.completion_schema}
        output: dict[str, dict[str, str]] = {}
        target_dir = run_dir / "external" / ADAPTER
        target_dir.mkdir(parents=True, exist_ok=True)
        for name, source in entries.items():
            data = source.read_bytes()
            target = target_dir / ("job.json" if name == "job" else source.name)
            target.write_bytes(data)
            target.chmod(0o444)
            output[name] = {"source_path": str(source), "source_sha256": hashlib.sha256(data).hexdigest(),
                            "stored_path": str(target.relative_to(run_dir)), "stored_sha256": hashlib.sha256(data).hexdigest()}
        return output


def discover(prompt_or_job: Path) -> TaxMachinePack | None:
    path = prompt_or_job.resolve()
    starts = (path, *path.parents) if path.is_dir() else (path.parent, *path.parents)
    for root in starts:
        manifest = root / "MANIFEST.json"
        if manifest.exists() or manifest.is_symlink():
            _regular(root, "MANIFEST.json")
            _read_json(manifest)
            return TaxMachinePack(root.resolve(), _regular(root, "MANIFEST.json"),
                                  _regular(root, "schemas/job.schema.json"),
                                  _regular(root, "schemas/completion.schema.json"))
    return None


def _registry(pack: TaxMachinePack):
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError as exc:
        raise WorkflowError("Tax Machine validation requires jsonschema") from exc
    resources = []
    schemas = []
    # The fixed schemas are the only resources; local references must resolve
    # within this fixed set.  Unknown/remote identifiers fail validation.
    for path in (pack.job_schema, pack.completion_schema):
        schema = _read_json(path)
        identifier = schema.get("$id")
        if not isinstance(identifier, str) or not identifier:
            raise WorkflowError(f"Tax Machine schema has missing $id: {path}")
        schemas.append((path, identifier, schema))
    allowed_ids = {identifier for _, identifier, _ in schemas}
    for path, identifier, schema in schemas:
        _check_refs(schema, path, allowed_ids)
        resources.append((identifier, Resource.from_contents(schema)))
    return Draft202012Validator, Registry().with_resources(resources)


def _check_refs(value: Any, source: Path, allowed_ids: set[str]) -> None:
    """Reject remote, absolute, and escaping references before validator setup."""
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str) and not reference.startswith("#"):
            target = reference.split("#", 1)[0]
            target_path = Path(target)
            if (target_path.is_absolute() or ".." in target_path.parts
                    or ("://" in target and target not in allowed_ids)
                    or ("://" not in target and target not in {"job.schema.json", "completion.schema.json"})):
                raise WorkflowError(f"Tax Machine schema reference escapes adapter boundary: {reference}")
        for child in value.values():
            _check_refs(child, source, allowed_ids)
    elif isinstance(value, list):
        for child in value:
            _check_refs(child, source, allowed_ids)


def _validate(pack: TaxMachinePack, data: bytes, schema_path: Path, label: str) -> dict[str, Any]:
    value = _read_json_bytes(data, label)
    Validator, registry = _registry(pack)
    schema = _read_json(schema_path)
    try:
        validator = Validator(schema, registry=registry)
        errors = sorted(validator.iter_errors(value), key=lambda item: list(item.path))
    except Exception as exc:
        raise WorkflowError(f"Tax Machine {label} schema reference rejected: {exc}") from exc
    if errors:
        details = "; ".join(f"{'.'.join(map(str, e.absolute_path)) or '$'}: {e.message}" for e in errors[:20])
        raise WorkflowError(f"invalid Tax Machine {label}: {details}")
    return value


def _read_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"invalid Tax Machine {label} JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"Tax Machine {label} must be a JSON object")
    return value


def validate_job(pack: TaxMachinePack, job_path: Path) -> dict[str, Any]:
    # Validate the caller's original path first.  Resolving it before lstat
    # would erase a symlink hop and incorrectly admit an executor-controlled
    # job link.
    try:
        raw_mode = job_path.lstat().st_mode
    except OSError as exc:
        raise WorkflowError(f"Tax Machine job is unsafe or missing: {job_path}") from exc
    if stat.S_ISLNK(raw_mode) or not stat.S_ISREG(raw_mode):
        raise WorkflowError("Tax Machine job must be a regular non-symlink file")
    try:
        relative = job_path.relative_to(pack.root)
    except ValueError as exc:
        raise WorkflowError(f"Tax Machine job escapes pack root: {job_path}") from exc
    path = _regular(pack.root, str(relative))
    return _validate(pack, path.read_bytes(), pack.job_schema, "job")


def validate_completion(pack: TaxMachinePack, data: bytes) -> dict[str, Any]:
    return _validate(pack, data, pack.completion_schema, "completion")
