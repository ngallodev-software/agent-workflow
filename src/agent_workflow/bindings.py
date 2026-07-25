from __future__ import annotations

import json
import hashlib
import os
import stat
from pathlib import Path
from typing import Any, Mapping

from .contracts import read_contract, validate_instance
from .errors import WorkflowError
from .receipts import read_sealed_contract, read_sealed_json, verify_seal_details
from .state import run_dir as session_run_dir
from .workflow import snapshot_sha256
from .util import atomic_write_json, sha256_file, utc_now

WORKFLOW_INPUT_BINDINGS_SCHEMA = "agent-workflow/workflow-input-bindings/v1"
MAX_TOTAL_BINDING_BYTES = 4 * 1024 * 1024
_MISSING = object()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _decode_token(token: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(token):
        if token[index] != "~":
            result.append(token[index])
            index += 1
            continue
        if index + 1 >= len(token) or token[index + 1] not in {"0", "1"}:
            raise WorkflowError("JSON Pointer contains an invalid escape")
        result.append("~" if token[index + 1] == "0" else "/")
        index += 2
    return "".join(result)


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    """Resolve the RFC 6901 data-model subset used by workflow bindings."""
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise WorkflowError("JSON Pointer must be empty or start with '/'")
    current = document
    for raw in pointer[1:].split("/"):
        token = _decode_token(raw)
        if isinstance(current, Mapping):
            if token not in current:
                return _MISSING
            current = current[token]
        elif isinstance(current, list):
            if token == "-" or not token.isdigit():
                return _MISSING
            if len(token) > 1 and token.startswith("0"):
                return _MISSING
            index = int(token)
            if index >= len(current):
                return _MISSING
            current = current[index]
        else:
            return _MISSING
    return current


def _ancestor_nodes(snapshot: Mapping[str, Any], node_id: str) -> set[str]:
    graph = {str(node["node_id"]): list(node["dependencies"]) for node in snapshot["nodes"]}
    result: set[str] = set()
    pending = list(graph[node_id])
    while pending:
        current = pending.pop()
        if current in result:
            continue
        result.add(current)
        pending.extend(graph[current])
    return result


def _read_sealed_result(run_dir: Path) -> tuple[Any, str, str]:
    receipt, expected = verify_seal_details(run_dir)
    if receipt.get("session_id") != run_dir.name:
        raise WorkflowError(f"source final receipt belongs to another run: {run_dir.name}")
    try:
        collection, _ = read_sealed_contract(
            run_dir,
            receipt,
            "collections/task-result.json",
            "agent-workflow/task-result-collection/v1",
        )
        if collection.get("validation_status") != "valid":
            raise WorkflowError(f"source run has no valid task result: {run_dir.name}")
    except WorkflowError as exc:
        # Older sealed runs may contain the validated result but lack the
        # collection receipt. The result artifact remains integrity-checked by
        # the final receipt, so preserve workflow resumption for those runs.
        if "task-result.json" not in str(exc):
            raise
    document, digest = read_sealed_json(run_dir, receipt, "result.json")
    if "collection" in locals() and collection.get("stored_sha256") != digest:
        raise WorkflowError(f"source task-result collection digest mismatch: {run_dir.name}")
    return document, digest, expected


def resolve_node_inputs(
    *,
    snapshot: Mapping[str, Any],
    status: Mapping[str, Any],
    node: Mapping[str, Any],
    settings: Any,
    workflow_run_dir: Path,
    attempt: int,
) -> dict[str, Any] | None:
    declarations = node.get("input_bindings")
    if not isinstance(declarations, Mapping) or not declarations:
        return None
    node_id = str(node["node_id"])
    ancestors = _ancestor_nodes(snapshot, node_id)
    states = {str(item["node_id"]): item for item in status["nodes"]}
    records: list[dict[str, Any]] = []
    total = 0
    for name, declaration in sorted(declarations.items()):
        source_node_id = str(declaration["source_node_id"])
        if source_node_id not in ancestors:
            raise WorkflowError(
                f"input binding {name} may reference only a predecessor node"
            )
        source = states.get(source_node_id)
        if not isinstance(source, Mapping) or source.get("state") != "completed":
            raise WorkflowError(f"input binding source is not completed: {source_node_id}")
        source_run_id = source.get("run_id")
        if not isinstance(source_run_id, str):
            raise WorkflowError(f"input binding source has no bound run: {source_node_id}")
        source_dir = session_run_dir(settings, source_run_id)
        document, result_digest, final_digest = _read_sealed_result(source_dir)
        pointer = str(declaration["pointer"])
        value = resolve_json_pointer(document, pointer)
        present = value is not _MISSING
        if not present and bool(declaration["required"]):
            raise WorkflowError(
                f"required input binding {name} is missing at pointer {pointer!r}"
            )
        selected = None if not present else value
        encoded = _canonical(selected)
        max_bytes = int(declaration["max_bytes"])
        if len(encoded) > max_bytes:
            raise WorkflowError(
                f"input binding {name} exceeds its {max_bytes}-byte limit"
            )
        total += len(encoded)
        if total > MAX_TOTAL_BINDING_BYTES:
            raise WorkflowError(
                f"workflow input bindings exceed {MAX_TOTAL_BINDING_BYTES} bytes"
            )
        records.append(
            {
                "name": str(name),
                "source_node_id": source_node_id,
                "source_run_id": source_run_id,
                "pointer": pointer,
                "required": bool(declaration["required"]),
                "present": present,
                "value": selected,
                "value_size_bytes": len(encoded),
                "value_sha256": hashlib.sha256(encoded).hexdigest(),
                "source_result_sha256": result_digest,
                "source_final_receipt_sha256": final_digest,
            }
        )
    artifact = {
        "schema": WORKFLOW_INPUT_BINDINGS_SCHEMA,
        "workflow_id": str(snapshot["workflow_id"]),
        "snapshot_sha256": snapshot_sha256(snapshot),
        "node_id": node_id,
        "attempt": attempt,
        "bindings": records,
    }
    root = workflow_run_dir / "bindings"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{node_id}-attempt-{attempt}.json"
    if path.exists():
        try:
            info = path.lstat()
        except OSError as exc:
            raise WorkflowError(f"cannot inspect workflow input binding snapshot {path}: {exc}") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise WorkflowError(f"workflow input binding snapshot is unsafe: {path}")
        if info.st_mode & 0o222:
            raise WorkflowError(f"workflow input binding snapshot must be read-only: {path}")
        existing = read_contract(path, WORKFLOW_INPUT_BINDINGS_SCHEMA)
        expected = dict(artifact)
        actual = dict(existing)
        actual.pop("created_at", None)
        if _canonical(actual) != _canonical(expected):
            raise WorkflowError(f"workflow input binding snapshot already exists: {path}")
        artifact = existing
    else:
        artifact["created_at"] = utc_now()
        validate_instance(
            artifact,
            WORKFLOW_INPUT_BINDINGS_SCHEMA,
            artifact="workflow input bindings",
        )
        atomic_write_json(path, artifact, mode=0o444)
    return {
        "artifact": artifact,
        "path": str(path),
        "sha256": sha256_file(path),
    }
