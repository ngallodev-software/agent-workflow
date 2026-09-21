from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .path import absolute_path, inventory_tree, read_regular_file, require_directory


def _schema_roots() -> tuple[Path, ...]:
    module_path = Path(__file__).resolve()
    source_root = absolute_path(module_path.parent.parent.parent / "schemas")
    # ``pip --target`` relocates data_files beside the package root rather than
    # under the interpreter's sys.prefix. Resolve that deterministic installed
    # layout before consulting prefix/user installation roots.
    package_data_root = (
        module_path.parent.parent
        / "share"
        / "agent-workflow"
        / "schemas"
    )
    prefix_root = Path(sys.prefix).expanduser().resolve()
    installed_root = prefix_root / "share" / "agent-workflow" / "schemas"
    user_data_root = (
        Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser()
        / "agent-workflow"
        / "schemas"
    )

    # Match schema authority to the installation family that supplied the
    # imported package. In particular, a stale ~/.local/share schema directory
    # must not override the current wheel inside an active virtual environment.
    # Conversely, a --user install lives outside sys.prefix and must prefer its
    # user data directory over any older system-wide schema copy.
    package_under_prefix = module_path.is_relative_to(prefix_root)
    installation_roots = (
        (installed_root, user_data_root)
        if package_under_prefix
        else (user_data_root, installed_root)
    )

    # A source checkout and an installed package are separate runtime modes.
    # Never merge multiple schema roots into one authority path.
    for root in (source_root, package_data_root, *installation_roots):
        if root.is_dir():
            return (root,)
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


AGENT_RUN_CONTRACT_SCHEMA = "agent-workflow/agent-run-contract/v1"


def validate_ticket_identity(value: dict[str, Any]) -> None:
    """Ensure the immutable identity projection agrees with the launch ticket."""
    ticket_identity = value.get("ticket_identity")
    if not isinstance(ticket_identity, dict):
        return
    ticket = value.get("ticket")
    expected_mode = "explicit" if ticket is not None else "omitted"
    if (
        ticket_identity.get("mode") != expected_mode
        or ticket_identity.get("value") != ticket
    ):
        raise WorkflowError("launch contract ticket identity does not match ticket")




def validate_criteria_catalog(value: dict[str, Any]) -> None:
    raw = value.get("criteria", [])
    if not isinstance(raw, list):
        raise WorkflowError("launch contract criterion catalog must be a list")
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise WorkflowError("launch contract criterion catalog contains a non-object")
        criterion_id = item.get("id")
        if not isinstance(criterion_id, str) or not criterion_id:
            raise WorkflowError("launch contract criterion catalog contains an empty ID")
        if criterion_id in seen:
            raise WorkflowError(f"launch contract contains duplicate criterion ID: {criterion_id}")
        seen.add(criterion_id)


def validate_agent_run_contract_value(value: dict[str, Any], *, artifact: str) -> str:
    schema_id = value.get("schema")
    if schema_id != AGENT_RUN_CONTRACT_SCHEMA:
        raise WorkflowError(f"unexpected agent run contract schema in {artifact}: {schema_id}")
    assert isinstance(schema_id, str)
    validate_instance(value, schema_id, artifact=artifact)
    validate_ticket_identity(value)
    validate_criteria_catalog(value)
    return schema_id


def read_agent_run_contract(path: Path) -> dict[str, Any]:
    """Read and validate immutable Agent Run execution authority."""
    value = read_contract(path)
    contract_schema_id = validate_agent_run_contract_value(value, artifact=str(path))
    for name, descriptor in value["schemas"].items():
        if descriptor is None:
            continue
        if not isinstance(descriptor, dict):
            raise WorkflowError("launch contract contains an invalid schema descriptor")
        descriptor_schema_id = descriptor.get("id")
        if not isinstance(descriptor_schema_id, str):
            raise WorkflowError("launch contract schema descriptor has no ID")
        if name != "task_result":
            expected = schema_descriptor(descriptor_schema_id)
            if descriptor.get("sha256") != expected["sha256"]:
                raise WorkflowError(
                    f"launch contract schema digest changed: {descriptor_schema_id}"
                )
    worktree = require_directory(Path(value["worktree"]["path"]), label="launch worktree")
    run_root = path.parent.resolve()
    handoff = Path(value["paths"]["handoff_dir"]).resolve()
    current_handoff = run_root / "handoff"
    if handoff != current_handoff.resolve():
        raise WorkflowError("launch handoff is outside the authorized runtime boundary")
    require_directory(handoff, label="launch handoff")
    if value["paths"]["workdir"] != value["worktree"]["path"]:
        raise WorkflowError("launch contract has conflicting worktree paths")
    if contract_schema_id == AGENT_RUN_CONTRACT_SCHEMA:
        command_contract = value.get("command_catalog")
        if not isinstance(command_contract, dict):
            raise WorkflowError("launch contract has no command catalog binding")
        run_dir = path.parent
        catalog_name = command_contract.get("catalog_path")
        card_name = command_contract.get("card_path")
        if catalog_name != "command-catalog.json" or card_name != "command-card.md":
            raise WorkflowError("launch command artifacts use unexpected paths")
        catalog_read = read_regular_file(run_dir / catalog_name)
        card_read = read_regular_file(run_dir / card_name)
        if catalog_read.sha256 != command_contract.get("catalog_sha256"):
            raise WorkflowError("launch command catalog changed after contract creation")
        if card_read.sha256 != command_contract.get("card_sha256"):
            raise WorkflowError("launch command card changed after contract creation")
        try:
            catalog_value = json.loads(catalog_read.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkflowError("launch command catalog is not valid JSON") from exc
        validate_instance(
            catalog_value,
            str(command_contract.get("catalog_schema")),
            artifact=str(run_dir / catalog_name),
        )
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
