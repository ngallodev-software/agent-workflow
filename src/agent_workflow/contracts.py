from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from .errors import WorkflowError


def _schema_roots() -> tuple[Path, ...]:
    return (
        Path(__file__).resolve().parents[2] / "schemas",
        Path(sys.prefix) / "share" / "agent-workflow" / "schemas",
    )


@lru_cache(maxsize=1)
def _schema_index() -> dict[str, Path]:
    result: dict[str, Path] = {}
    for root in _schema_roots():
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            schema_id = value.get("$id") if isinstance(value, dict) else None
            if isinstance(schema_id, str):
                result.setdefault(schema_id, path)
    return result


def load_schema(schema_id: str) -> dict[str, Any]:
    path = _schema_index().get(schema_id)
    if path is None:
        raise WorkflowError(f"unknown contract schema: {schema_id}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read contract schema {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"contract schema must be an object: {path}")
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
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise WorkflowError(f"cannot read contract {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid JSON in {path}: {exc}") from exc
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
