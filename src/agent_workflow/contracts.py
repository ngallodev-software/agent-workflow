from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .path import absolute_path, inventory_tree, read_regular_file, require_directory


def _schema_roots() -> tuple[Path, ...]:
    source_root = absolute_path(Path(__file__).parent.parent.parent / "schemas")
    installed_root = Path(sys.prefix) / "share" / "agent-workflow" / "schemas"
    # A source checkout and an installed package are separate runtime modes.
    # Never merge ambient user/site-package roots into the authority path.
    if source_root.is_dir():
        return (source_root,)
    if installed_root.is_dir():
        return (installed_root,)
    return ()


@lru_cache(maxsize=1)
def _schema_index() -> dict[str, tuple[Path, str]]:
    roots = _schema_roots()
    if len(roots) != 1:
        raise WorkflowError("packaged contract schema directory is missing")
    root = require_directory(roots[0], label="packaged schema root")
    result: dict[str, tuple[Path, str]] = {}
    for entry in inventory_tree(root):
        if entry.kind != "file" or not entry.path.endswith(".json"):
            continue
        path = root / entry.path
        try:
            value = json.loads(read_regular_file(path).data.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
            raise WorkflowError(f"invalid packaged contract schema: {entry.path}") from exc
        schema_id = value.get("$id") if isinstance(value, dict) else None
        if not isinstance(schema_id, str) or not schema_id:
            raise WorkflowError(f"packaged contract schema has no string $id: {entry.path}")
        if schema_id in result:
            prior = result[schema_id][0].relative_to(root).as_posix()
            raise WorkflowError(f"duplicate packaged contract schema ID {schema_id!r}: {prior}, {entry.path}")
        result[schema_id] = (path, str(entry.sha256))
    return result


def load_schema(schema_id: str) -> dict[str, Any]:
    indexed = _schema_index().get(schema_id)
    if indexed is None:
        raise WorkflowError(f"unknown contract schema: {schema_id}")
    path, expected_sha256 = indexed
    try:
        read = read_regular_file(path)
        if read.sha256 != expected_sha256:
            raise WorkflowError(f"packaged contract schema changed during use: {path.name}")
        value = json.loads(read.data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
        raise WorkflowError(f"cannot read contract schema {path.name}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"contract schema must be an object: {path.name}")
    return value


def schema_descriptor(schema_id: str) -> dict[str, str]:
    """Return the packaged schema identity bound into an immutable contract."""
    indexed = _schema_index().get(schema_id)
    if indexed is None:
        raise WorkflowError(f"unknown contract schema: {schema_id}")
    return {"id": schema_id, "sha256": indexed[1]}


def validate_instance(
    value: Any,
    schema_id: str,
    *,
    artifact: str = "artifact",
) -> None:
    try:
        import jsonschema
    except ImportError as exc:
        raise WorkflowError(
            "JSON Schema instance validation requires the base jsonschema dependency: "
            "pip install 'jsonschema>=4.18,<5'"
        ) from exc
    validator = jsonschema.Draft202012Validator(load_schema(schema_id))
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.path))
    if not errors:
        return
    details: list[str] = []
    for error in errors[:20]:
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        details.append(f"{location}: {error.message}")
    raise WorkflowError(f"invalid {artifact}: " + "; ".join(details))


def read_contract(path: Path, expected_schema: str | None = None) -> dict[str, Any]:
    try:
        value = json.loads(read_regular_file(path).data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, WorkflowError) as exc:
        raise WorkflowError(f"cannot read contract {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid JSON in {path.name}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"contract must be a JSON object: {path}")
    schema_id = value.get("schema")
    if not isinstance(schema_id, str):
        raise WorkflowError(f"contract missing string schema: {path}")
    if expected_schema is not None and schema_id != expected_schema:
        raise WorkflowError(
            f"unexpected contract schema in {path}: {schema_id}; "
            f"expected {expected_schema}"
        )
    validate_instance(value, schema_id, artifact=str(path))
    return value


def read_launch_contract(path: Path) -> dict[str, Any]:
    """Read the launch authority through the bounded contract reader."""
    value = read_contract(path, "agent-workflow/launch-contract/v1")
    for name, descriptor in value["schemas"].items():
        if descriptor is None:
            continue
        if not isinstance(descriptor, dict):
            raise WorkflowError("launch contract contains an invalid schema descriptor")
        schema_id = descriptor.get("id")
        if not isinstance(schema_id, str):
            raise WorkflowError("launch contract schema descriptor has no ID")
        if name != "task_result":
            expected = schema_descriptor(schema_id)
            if descriptor.get("sha256") != expected["sha256"]:
                raise WorkflowError(f"launch contract schema digest changed: {schema_id}")
    worktree = require_directory(Path(value["worktree"]["path"]), label="launch worktree")
    handoff = Path(value["paths"]["handoff_dir"])
    try:
        handoff.relative_to(worktree)
    except ValueError as exc:
        raise WorkflowError("launch handoff escapes launch worktree") from exc
    require_directory(handoff, label="launch handoff")
    if value["paths"]["workdir"] != value["worktree"]["path"]:
        raise WorkflowError("launch contract has conflicting worktree paths")
    pack_root = value["pack"].get("root")
    if pack_root is not None:
        require_directory(Path(pack_root), label="launch pack root")
        result_contract = value["paths"].get("result_contract")
        if isinstance(result_contract, dict):
            schema_path = result_contract.get("schema")
            if not isinstance(schema_path, str) or not schema_path:
                raise WorkflowError("launch result contract has no schema path")
            relative = Path(schema_path)
            if (
                relative.is_absolute()
                or any(part in {"", ".", ".."} for part in relative.parts)
                or relative.as_posix() != schema_path
            ):
                raise WorkflowError("launch result schema path is not pack-contained")
            actual = read_regular_file(Path(pack_root) / relative)
            expected = value["schemas"].get("task_result")
            if not isinstance(expected, dict) or actual.sha256 != expected.get("sha256"):
                raise WorkflowError("launch result schema changed after contract creation")
        manifest_digest = value["pack"].get("manifest_sha256")
        if manifest_digest is not None:
            manifest = read_regular_file(Path(pack_root) / "MANIFEST.sha256")
            if manifest.sha256 != manifest_digest:
                raise WorkflowError("launch pack manifest changed after contract creation")
    return value
