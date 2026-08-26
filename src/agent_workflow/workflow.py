from __future__ import annotations

import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from .contracts import read_contract, validate_instance
from .errors import WorkflowError
from .journal import JournalTransactionResult, locked_file, read_jsonl, transact_jsonl
from .util import (
    atomic_write_json,
    canonical_json_bytes,
    canonical_json_sha256,
    fsync_directory,
    utc_now,
    validate_id,
)

WORKFLOW_SNAPSHOT_SCHEMA = "agent-workflow/workflow-snapshot/v1"
WORKFLOW_NODE_BINDING_SCHEMA = "agent-workflow/workflow-node-binding/v1"
WORKFLOW_NODE_RESULT_SCHEMA = "agent-workflow/workflow-node-result/v1"
WORKFLOW_EVENT_SCHEMA = "agent-workflow/workflow-event/v1"
WORKFLOW_STATUS_SCHEMA = "agent-workflow/workflow-status/v1"
WORKFLOW_RUN_SCHEMA = "agent-workflow/workflow-run/v1"

NODE_STATES = {"blocked", "eligible", "running", "completed", "failed", "recoverable"}
TERMINAL_NODE_STATES = {"completed", "failed"}
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "blocked": {"eligible", "failed"},
    "eligible": {"running", "completed", "failed", "recoverable"},
    "running": {"completed", "failed", "recoverable"},
    "completed": set(),
    "failed": {"blocked", "eligible"},
    "recoverable": {"eligible"},
}


def workflow_snapshot_path(run_dir: Path) -> Path:
    return run_dir / "workflow-snapshot.json"


def workflow_events_path(run_dir: Path) -> Path:
    return run_dir / "workflow-events.jsonl"


def workflow_status_path(run_dir: Path) -> Path:
    return run_dir / "workflow-status.json"


def workflow_run_path(run_dir: Path) -> Path:
    return run_dir / "workflow-run.json"


def read_stored_workflow_snapshot(path: Path) -> dict[str, Any]:
    """Read the canonical snapshot through a stable non-symlink descriptor."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WorkflowError(f"cannot open workflow snapshot {path}: {exc}") from exc
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError(f"workflow snapshot must be a regular file: {path}")
        if info.st_mode & 0o222:
            raise WorkflowError(f"workflow snapshot must be read-only: {path}")
        data = stream.read()
    try:
        value = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise WorkflowError(f"workflow snapshot is not UTF-8: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid JSON in workflow snapshot {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"workflow snapshot must be a JSON object: {path}")
    if value.get("schema") != WORKFLOW_SNAPSHOT_SCHEMA:
        raise WorkflowError(
            f"unexpected workflow snapshot schema in {path}: {value.get('schema')!r}"
        )
    validate_instance(value, WORKFLOW_SNAPSHOT_SCHEMA, artifact=str(path))
    return normalize_snapshot(value)


@contextmanager
def workflow_lock(run_dir: Path, *, exclusive: bool = True) -> Iterator[None]:
    """Serialize workflow mutations and stable evidence reads."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "workflow.lock"
    with locked_file(
        path,
        exclusive=exclusive,
        create=True,
        create_parent=True,
    ):
        yield


def ensure_workflow_events_file(run_dir: Path) -> Path:
    """Create or validate the canonical workflow event journal safely."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = workflow_events_path(run_dir)
    with locked_file(path, exclusive=True, create=True, create_parent=True):
        pass
    return path


def _validate_input_bindings(value: Any, *, location: str) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise WorkflowError(f"{location}: input_bindings must be a mapping")
    if len(value) > 64:
        raise WorkflowError(f"{location}: at most 64 input bindings are allowed")
    result: dict[str, dict[str, Any]] = {}
    for name, raw in sorted(value.items(), key=lambda item: str(item[0])):
        binding_name = validate_id(str(name), "workflow input binding name")
        if not isinstance(raw, Mapping):
            raise WorkflowError(f"{location}.{binding_name}: expected mapping")
        source_node_id = validate_id(
            str(raw.get("source_node_id", "")), "workflow source node ID"
        )
        pointer = raw.get("pointer", "")
        if not isinstance(pointer, str):
            raise WorkflowError(f"{location}.{binding_name}: pointer must be a string")
        required = raw.get("required", True)
        if not isinstance(required, bool):
            raise WorkflowError(f"{location}.{binding_name}: required must be boolean")
        max_bytes = raw.get("max_bytes", 65536)
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or not 1 <= max_bytes <= 1048576:
            raise WorkflowError(
                f"{location}.{binding_name}: max_bytes must be between 1 and 1048576"
            )
        result[binding_name] = {
            "source_node_id": source_node_id,
            "pointer": pointer,
            "required": required,
            "max_bytes": max_bytes,
        }
    return result


def _validate_node(node: Mapping[str, Any], *, location: str) -> dict[str, Any]:
    if not isinstance(node, Mapping):
        raise WorkflowError(f"{location}: expected mapping")
    node_id = validate_id(str(node.get("node_id", "")), "workflow node ID")
    kind = str(node.get("kind", "task"))
    if kind not in {"task", "approval"}:
        raise WorkflowError(f"{location}: unsupported workflow node kind: {kind}")
    dependencies = node.get("dependencies", [])
    if dependencies is None:
        dependencies = []
    if not isinstance(dependencies, list) or any(
        not isinstance(item, str) or not item for item in dependencies
    ):
        raise WorkflowError(f"{location}: dependencies must be a list of node IDs")
    normalized_dependencies = [
        validate_id(str(item), "workflow dependency node ID") for item in dependencies
    ]
    if len(normalized_dependencies) != len(set(normalized_dependencies)):
        raise WorkflowError(f"{location}: duplicate dependency IDs are not allowed")
    result: dict[str, Any] = {
        "node_id": node_id,
        "kind": kind,
        "dependencies": normalized_dependencies,
    }
    if kind == "task":
        agent_run_id = validate_id(str(node.get("agent_run_id", "")), "Agent Run ID")
        prompt_path = str(node.get("prompt_path", ""))
        if not prompt_path:
            raise WorkflowError(f"{location}: prompt_path is required")
        result.update(agent_run_id=agent_run_id, prompt_path=prompt_path)
        for name in ("ticket_id", "tier", "pack_id", "role", "agent_class", "executor", "model"):
            value = node.get(name)
            if value is not None:
                result[name] = str(value)
        if result.get("role") is not None and any(
            result.get(name) is not None for name in ("agent_class", "executor", "model")
        ):
            raise WorkflowError(
                f"{location}: role cannot be combined with agent_class, executor, or model"
            )
        for name in ("interactive", "allow_no_go_model"):
            value = node.get(name)
            if value is not None:
                if not isinstance(value, bool):
                    raise WorkflowError(f"{location}: {name} must be boolean")
                result[name] = value
        routing = node.get("routing")
        if routing is not None:
            if not isinstance(routing, Mapping):
                raise WorkflowError(f"{location}: routing must be a mapping")
            encoded = canonical_json_bytes(dict(routing))
            if len(encoded) > 16384:
                raise WorkflowError(f"{location}: routing metadata exceeds 16384 bytes")
            result["routing"] = dict(routing)
        bindings = _validate_input_bindings(
            node.get("input_bindings"), location=f"{location}.input_bindings"
        )
        if bindings:
            result["input_bindings"] = bindings
    else:
        approval_for = validate_id(
            str(node.get("approval_for", "")), "approval subject node ID"
        )
        result["approval_for"] = approval_for
        if approval_for not in result["dependencies"]:
            raise WorkflowError(
                f"{location}: approval node must depend on approval_for node {approval_for}"
            )
    return result


def normalize_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise WorkflowError("workflow snapshot must be a mapping")
    workflow_id = validate_id(str(snapshot.get("workflow_id", "")), "workflow ID")
    pack_id = str(snapshot.get("pack_id", ""))
    if not pack_id:
        raise WorkflowError("workflow snapshot pack_id is required")
    pack_manifest_sha256 = str(snapshot.get("pack_manifest_sha256", ""))
    if not pack_manifest_sha256:
        raise WorkflowError("workflow snapshot pack_manifest_sha256 is required")
    nodes = snapshot.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise WorkflowError("workflow snapshot nodes must be a non-empty list")
    normalized_nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_agent_run_ids: set[str] = set()
    for index, node in enumerate(nodes):
        normalized = _validate_node(node, location=f"nodes[{index}]")
        node_id = normalized["node_id"]
        if node_id in seen:
            raise WorkflowError(f"duplicate workflow node ID: {node_id}")
        seen.add(node_id)
        if normalized["kind"] == "task":
            agent_run_id = str(normalized["agent_run_id"])
            if agent_run_id in seen_agent_run_ids:
                raise WorkflowError(f"duplicate Agent Run ID: {agent_run_id}")
            seen_agent_run_ids.add(agent_run_id)
        normalized_nodes.append(normalized)
    graph = {item["node_id"]: list(item["dependencies"]) for item in normalized_nodes}
    unknown = sorted(
        dependency
        for dependencies in graph.values()
        for dependency in dependencies
        if dependency not in graph
    )
    if unknown:
        raise WorkflowError(
            "workflow snapshot references unknown dependency IDs: "
            + ", ".join(sorted(set(unknown)))
        )
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node_id: str) -> list[str] | None:
        if node_id in visiting:
            start = stack.index(node_id)
            return stack[start:] + [node_id]
        if node_id in visited:
            return None
        visiting.add(node_id)
        stack.append(node_id)
        for dependency in graph[node_id]:
            cycle = visit(dependency)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node_id)
        visited.add(node_id)
        return None

    for node_id in sorted(graph):
        cycle = visit(node_id)
        if cycle:
            raise WorkflowError(
                "workflow snapshot contains a dependency cycle: "
                + " -> ".join(cycle)
            )
    normalized_nodes.sort(key=lambda item: item["node_id"])
    for item in normalized_nodes:
        item["dependencies"] = sorted(item["dependencies"])
    normalized = {
        "schema": WORKFLOW_SNAPSHOT_SCHEMA,
        "workflow_id": workflow_id,
        "pack_id": pack_id,
        "pack_manifest_sha256": pack_manifest_sha256,
        "nodes": normalized_nodes,
    }
    validate_instance(normalized, WORKFLOW_SNAPSHOT_SCHEMA, artifact="workflow snapshot")
    return normalized


def snapshot_sha256(snapshot: Mapping[str, Any]) -> str:
    normalized = normalize_snapshot(snapshot)
    return canonical_json_sha256(normalized)


def initial_status(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_snapshot(snapshot)
    nodes = [
        {
            "node_id": node["node_id"],
            "kind": node["kind"],
            "state": "eligible" if not node["dependencies"] else "blocked",
            "agent_run_id": None,
            "attempt": None,
            "retry_of_agent_run_id": None,
            "bound_at": None,
            "terminal_reason": None,
            "approval_receipt_sha256": None,
            "input_binding_sha256": None,
        }
        for node in normalized["nodes"]
    ]
    status = {
        "schema": WORKFLOW_STATUS_SCHEMA,
        "workflow_id": normalized["workflow_id"],
        "snapshot_sha256": snapshot_sha256(normalized),
        "event_count": 0,
        "workflow_state": _aggregate_workflow_state(nodes),
        "nodes": nodes,
    }
    validate_instance(status, WORKFLOW_STATUS_SCHEMA, artifact="workflow status")
    return status


def _aggregate_workflow_state(nodes: list[dict[str, Any]]) -> str:
    states = [str(item["state"]) for item in nodes]
    if any(state == "failed" for state in states):
        return "failed"
    if any(state == "running" for state in states):
        return "running"
    if any(state == "recoverable" for state in states):
        return "recoverable"
    if all(state == "completed" for state in states):
        return "completed"
    if any(state == "eligible" for state in states):
        return "eligible"
    return "blocked"


def _binding_record(event: Mapping[str, Any]) -> dict[str, Any]:
    binding = event.get("binding")
    if not isinstance(binding, Mapping):
        raise WorkflowError("workflow binding event missing binding record")
    required = ["agent_run_id", "attempt", "bound_at", "current"]
    missing = [name for name in required if name not in binding]
    if missing:
        raise WorkflowError(
            "workflow binding event missing fields: " + ", ".join(missing)
        )
    node_id = validate_id(str(event.get("node_id", "")), "workflow node ID")
    agent_run_id = validate_id(str(binding.get("agent_run_id", "")), "Agent Run ID")
    retry_of_agent_run_id = binding.get("retry_of_agent_run_id")
    if retry_of_agent_run_id is not None:
        retry_of_agent_run_id = validate_id(str(retry_of_agent_run_id), "retry run ID")
    attempt = binding.get("attempt")
    if not isinstance(attempt, int) or attempt < 1:
        raise WorkflowError("workflow binding attempt must be a positive integer")
    bound_at = str(binding.get("bound_at"))
    if not bound_at:
        raise WorkflowError("workflow binding bound_at is required")
    current = binding.get("current")
    if not isinstance(current, bool):
        raise WorkflowError("workflow binding current must be a boolean")
    result = {
        "schema": WORKFLOW_NODE_BINDING_SCHEMA,
        "workflow_id": str(event.get("workflow_id", "")),
        "node_id": node_id,
        "agent_run_id": agent_run_id,
        "attempt": attempt,
        "retry_of_agent_run_id": retry_of_agent_run_id,
        "bound_at": bound_at,
        "current": current,
    }
    validate_instance(result, WORKFLOW_NODE_BINDING_SCHEMA, artifact="workflow binding")
    return result


def _transition_record(event: Mapping[str, Any]) -> tuple[str, str, str]:
    previous_state = str(event.get("previous_state", ""))
    next_state = str(event.get("next_state", ""))
    reason = str(event.get("reason", ""))
    if previous_state not in NODE_STATES:
        raise WorkflowError("workflow transition has invalid previous_state")
    if next_state not in NODE_STATES:
        raise WorkflowError("workflow transition has invalid next_state")
    if not reason:
        raise WorkflowError("workflow transition reason is required")
    if next_state not in ALLOWED_TRANSITIONS[previous_state]:
        raise WorkflowError(
            f"invalid workflow transition: {previous_state} -> {next_state}"
        )
    return previous_state, next_state, reason


def _validate_workflow_event_record(value: object, line_number: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError(f"workflow event at line {line_number} must be an object")
    validate_instance(value, WORKFLOW_EVENT_SCHEMA, artifact=f"workflow event:{line_number}")
    if value.get("sequence") != line_number:
        raise WorkflowError(
            f"workflow event sequence mismatch at line {line_number}: expected {line_number}"
        )
    return value


def append_workflow_event(run_dir: Path, event: Mapping[str, Any]) -> dict[str, Any]:
    path = ensure_workflow_events_file(run_dir)

    def decide(existing: list[dict[str, Any]]) -> JournalTransactionResult[dict[str, Any]]:
        event_data = dict(event)
        event_data["schema"] = WORKFLOW_EVENT_SCHEMA
        event_data["sequence"] = len(existing) + 1
        event_data.setdefault("timestamp", utc_now())
        event_data = _validate_workflow_event_record(event_data, len(existing) + 1)
        return JournalTransactionResult(value=event_data, record=event_data)

    return transact_jsonl(
        path,
        validator=_validate_workflow_event_record,
        transaction=decide,
        sequence_field="sequence",
    )

def record_workflow_binding(
    run_dir: Path,
    *,
    workflow_id: str,
    node_id: str,
    agent_run_id: str,
    attempt: int,
    actor: str,
    reason: str,
    snapshot_sha256: str,
    retry_of_agent_run_id: str | None = None,
    current: bool = True,
) -> dict[str, Any]:
    event = append_workflow_event(
        run_dir,
        {
            "workflow_id": validate_id(workflow_id, "workflow ID"),
            "snapshot_sha256": snapshot_sha256,
            "kind": "node-bound",
            "node_id": validate_id(node_id, "workflow node ID"),
            "actor": actor,
            "reason": reason,
            "binding": {
                "agent_run_id": validate_id(agent_run_id, "Agent Run ID"),
                "attempt": attempt,
                "retry_of_agent_run_id": (
                    validate_id(retry_of_agent_run_id, "retry run ID")
                    if retry_of_agent_run_id is not None
                    else None
                ),
                "bound_at": utc_now(),
                "current": current,
            },
        },
    )
    return event


def record_workflow_transition(
    run_dir: Path,
    *,
    workflow_id: str,
    node_id: str,
    actor: str,
    reason: str,
    snapshot_sha256: str,
    previous_state: str,
    next_state: str,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    event = append_workflow_event(
        run_dir,
        {
            "workflow_id": validate_id(workflow_id, "workflow ID"),
            "snapshot_sha256": snapshot_sha256,
            "kind": "node-transition",
            "node_id": validate_id(node_id, "workflow node ID"),
            "actor": actor,
            "reason": reason,
            "previous_state": previous_state,
            "next_state": next_state,
            "details": dict(details) if details is not None else None,
        },
    )
    return event


def _parse_event_lines(lines: list[str], path: Path) -> list[dict[str, Any]]:
    # Retained for callers/tests that provide decoded lines directly. Journal
    # file reads use the shared descriptor-safe JSONL primitive below.
    data = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    from .journal import decode_jsonl

    return decode_jsonl(data, path=path, validator=_validate_workflow_event_record)


def read_workflow_events(path: Path) -> list[dict[str, Any]]:
    """Read and validate a stable workflow event journal snapshot."""
    return read_jsonl(path, validator=_validate_workflow_event_record, sequence_field="sequence")


def _read_events(path: Path) -> list[dict[str, Any]]:
    return read_workflow_events(path)

def _transition_summary(
    *,
    nodes: dict[str, dict[str, Any]],
    dependencies: dict[str, list[str]],
    kinds: dict[str, str],
    node_id: str,
    previous_state: str,
    next_state: str,
    reason: str,
) -> None:
    if node_id not in nodes:
        raise WorkflowError(f"workflow event references unknown node: {node_id}")
    current = nodes[node_id]["state"]
    if current != previous_state:
        raise WorkflowError(
            f"workflow transition mismatch for {node_id}: expected {current}, got {previous_state}"
        )
    if next_state not in ALLOWED_TRANSITIONS[previous_state]:
        raise WorkflowError(
            f"invalid workflow transition for {node_id}: {previous_state} -> {next_state}"
        )
    if (
        kinds[node_id] == "task"
        and (
            next_state in {"running", "completed"}
            or (next_state == "failed" and previous_state != "blocked")
        )
        and nodes[node_id]["agent_run_id"] is None
    ):
        raise WorkflowError(
            f"workflow node {node_id} cannot enter {next_state} without a current binding"
        )
    if previous_state == "blocked" and next_state == "eligible":
        unresolved = [dep for dep in dependencies[node_id] if nodes[dep]["state"] != "completed"]
        if unresolved:
            raise WorkflowError(
                "workflow node "
                f"{node_id} cannot become eligible before dependencies complete: "
                + ", ".join(unresolved)
            )
    if previous_state in {"failed", "recoverable"} and next_state == "eligible":
        attempt = nodes[node_id]["attempt"]
        if not isinstance(attempt, int) or attempt < 2:
            raise WorkflowError(
                f"workflow node {node_id} cannot retry before a newer current binding"
            )
    nodes[node_id]["state"] = next_state
    if next_state in TERMINAL_NODE_STATES:
        nodes[node_id]["terminal_reason"] = reason
    else:
        nodes[node_id]["terminal_reason"] = None


def reconstruct_workflow_status(
    snapshot: Mapping[str, Any],
    events_path: Path,
) -> dict[str, Any]:
    normalized = normalize_snapshot(snapshot)
    dependencies = {node["node_id"]: list(node["dependencies"]) for node in normalized["nodes"]}
    kinds = {node["node_id"]: str(node["kind"]) for node in normalized["nodes"]}
    nodes = {
        node["node_id"]: {
            "node_id": node["node_id"],
            "kind": node["kind"],
            "state": "eligible" if not node["dependencies"] else "blocked",
            "agent_run_id": None,
            "attempt": None,
            "retry_of_agent_run_id": None,
            "bound_at": None,
            "terminal_reason": None,
        }
        for node in normalized["nodes"]
    }
    event_count = 0
    seen_run_ids: set[str] = set()
    for event in _read_events(events_path):
        event_count += 1
        if event["workflow_id"] != normalized["workflow_id"]:
            raise WorkflowError("workflow event references a different workflow")
        if event["snapshot_sha256"] != snapshot_sha256(normalized):
            raise WorkflowError("workflow event snapshot digest mismatch")
        kind = event["kind"]
        node_id = str(event["node_id"])
        if kind == "node-bound":
            if node_id not in nodes:
                raise WorkflowError(f"workflow event references unknown node: {node_id}")
            binding = _binding_record(event)
            if binding["node_id"] != node_id:
                raise WorkflowError("workflow binding node mismatch")
            if not binding["current"]:
                raise WorkflowError("workflow binding record must be current")
            current_state = nodes[node_id]["state"]
            if current_state in {"blocked", "running", "completed"}:
                raise WorkflowError(
                    f"workflow node {node_id} cannot be bound while {current_state}"
                )
            prior_run_id = nodes[node_id]["agent_run_id"]
            prior_attempt = nodes[node_id]["attempt"]
            if prior_run_id is None:
                if current_state != "eligible":
                    raise WorkflowError(
                        f"workflow node {node_id} must be eligible before first binding"
                    )
                if binding["attempt"] != 1:
                    raise WorkflowError(
                        f"workflow node {node_id} first binding must use attempt 1"
                    )
                if binding["retry_of_agent_run_id"] is not None:
                    raise WorkflowError(
                        f"workflow node {node_id} first binding cannot have retry lineage"
                    )
            else:
                if current_state not in {"failed", "recoverable"}:
                    raise WorkflowError(
                        f"workflow node {node_id} retry requires failed or recoverable state"
                    )
                if not isinstance(prior_attempt, int) or binding["attempt"] != prior_attempt + 1:
                    raise WorkflowError(
                        f"workflow node {node_id} retry attempt must be the next attempt"
                    )
                if binding["retry_of_agent_run_id"] != prior_run_id:
                    raise WorkflowError(
                        f"workflow node {node_id} retry must reference the current run"
                    )
            if binding["agent_run_id"] in seen_run_ids:
                raise WorkflowError(f"Agent Run ID reused: {binding['agent_run_id']}")
            seen_run_ids.add(binding["agent_run_id"])
            nodes[node_id].update(
                agent_run_id=binding["agent_run_id"],
                attempt=binding["attempt"],
                retry_of_agent_run_id=binding["retry_of_agent_run_id"],
                bound_at=binding["bound_at"],
            )
        elif kind == "node-transition":
            previous_state, next_state, reason = _transition_record(event)
            _transition_summary(
                nodes=nodes,
                dependencies=dependencies,
                kinds=kinds,
                node_id=node_id,
                previous_state=previous_state,
                next_state=next_state,
                reason=reason,
            )
            details = event.get("details")
            if isinstance(details, Mapping):
                approval_digest = details.get("approval_receipt_sha256")
                binding_digest = details.get("input_binding_sha256")
                if isinstance(approval_digest, str):
                    nodes[node_id]["approval_receipt_sha256"] = approval_digest
                if isinstance(binding_digest, str):
                    nodes[node_id]["input_binding_sha256"] = binding_digest
        else:
            raise WorkflowError(f"unknown workflow event kind: {kind}")
    node_list = [nodes[node_id] for node_id in sorted(nodes)]
    status = {
        "schema": WORKFLOW_STATUS_SCHEMA,
        "workflow_id": normalized["workflow_id"],
        "snapshot_sha256": snapshot_sha256(normalized),
        "event_count": event_count,
        "workflow_state": _aggregate_workflow_state(node_list),
        "nodes": node_list,
    }
    validate_instance(status, WORKFLOW_STATUS_SCHEMA, artifact="workflow status")
    return status


def build_workflow_run(
    *,
    snapshot: Mapping[str, Any],
    snapshot_path: Path,
    events_path: Path,
    status_path: Path,
) -> dict[str, Any]:
    normalized = normalize_snapshot(snapshot)
    status = reconstruct_workflow_status(normalized, events_path)
    run = {
        "schema": WORKFLOW_RUN_SCHEMA,
        "workflow_id": normalized["workflow_id"],
        "snapshot_sha256": snapshot_sha256(normalized),
        "snapshot_path": str(snapshot_path),
        "events_path": str(events_path),
        "status_path": str(status_path),
        "status": status,
    }
    validate_instance(run, WORKFLOW_RUN_SCHEMA, artifact="workflow run")
    return run


def write_workflow_projection(
    *,
    snapshot: Mapping[str, Any],
    snapshot_path: Path,
    events_path: Path,
    status_path: Path,
    run_path: Path,
) -> dict[str, Any]:
    run = build_workflow_run(
        snapshot=snapshot,
        snapshot_path=snapshot_path,
        events_path=events_path,
        status_path=status_path,
    )
    atomic_write_json(status_path, run["status"])
    atomic_write_json(run_path, run)
    return run
