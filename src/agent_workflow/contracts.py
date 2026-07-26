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
