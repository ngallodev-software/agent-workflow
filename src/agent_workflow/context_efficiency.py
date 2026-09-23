"""Compact executor-context projection and BM4 amplification telemetry."""

from __future__ import annotations

import hashlib
import json
import math
import shlex
from pathlib import Path
from typing import Any, Mapping

from .util import atomic_write_json, sha256_file, utc_now

SCHEMA = "agent-workflow/executor-context/v1"
HOST_DETERMINISTIC_GATES = (
    "schema_validation",
    "lifecycle_transition",
    "policy_and_scope",
    "completion_predicate",
    "hashing_and_provenance",
    "evidence_collection",
    "sealing",
)
_TOOL_ITEM_TYPES = frozenset({"command_execution", "tool_call", "function_call", "mcp_tool_call", "web_search"})


def _estimated_tokens(byte_count: int) -> int:
    return int(math.ceil(max(0, byte_count) / 4.0))


def _diagnostics(path: Path) -> dict[str, int | str]:
    data = path.read_bytes()
    return {"bytes": len(data), "estimated_tokens": _estimated_tokens(len(data)), "sha256": hashlib.sha256(data).hexdigest()}


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_executor_context(
    state_dir: Path, *, agent_run_id: str, role_id: str, role_digest: str,
    prompt_path: Path, launch_prompt_path: Path, handoff_dir: Path,
    command_artifacts: Mapping[str, Any],
    criteria: tuple[dict[str, str | None], ...] = (),
    result_contract: Mapping[str, Any] | None = None,
    source_baseline_path: Path | None = None,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    prompt, launch = _diagnostics(prompt_path), _diagnostics(launch_prompt_path)
    card = _diagnostics(state_dir / str(command_artifacts["card_path"]))
    catalog = _diagnostics(state_dir / str(command_artifacts["catalog_path"]))
    injected_bytes = max(0, int(launch["bytes"]) - int(prompt["bytes"]))
    projection: dict[str, Any] = {
        "agent_run_id": agent_run_id,
        "role": {"id": role_id, "digest": role_digest},
        "criteria_ids": [str(item["id"]) for item in criteria],
        "result_schema": str(result_contract.get("schema")) if isinstance(result_contract, Mapping) and result_contract.get("schema") else None,
        "host_deterministic_gates": list(HOST_DETERMINISTIC_GATES),
        "references": {
            "command_card": {"path": str(command_artifacts["card_path"]), "sha256": str(command_artifacts["card_sha256"])},
            "command_catalog": {"path": str(command_artifacts["catalog_path"]), "sha256": str(command_artifacts["catalog_sha256"])},
            "task_prompt": {"path": "prompt.md", "sha256": str(prompt["sha256"])},
            "launch_prompt": {"path": "launch-prompt.md", "sha256": str(launch["sha256"])},
            "source_baseline": (
                {"path": "source-baseline.json", "sha256": sha256_file(source_baseline_path)}
                if source_baseline_path is not None and source_baseline_path.is_file() else None
            ),
        },
    }
    projection_sha256 = _canonical_sha256(projection)
    value = {
        "schema": SCHEMA,
        "context_id": f"ctx-{projection_sha256[:24]}",
        "projection_sha256": projection_sha256,
        "projection": projection,
        "measurements": {
            "task_prompt": prompt,
            "launch_prompt": launch,
            "injected_context": {"bytes": injected_bytes, "estimated_tokens": _estimated_tokens(injected_bytes)},
            "command_card": card,
            "command_catalog": catalog,
            "token_estimate_method": "ceil(utf8_bytes/4); diagnostic estimate, not provider usage",
        },
        "runtime": {
            "measurement_source": "provider-events", "provider_event_count": 0,
            "model_turn_count": None, "tool_call_count": None, "command_execution_count": None,
            "tool_call_types": {}, "command_families": {},
            "protocol_command_counts": {}, "message_kind_counts": {},
            "acceptance_command_executions": 0, "verification_cache_hits": 0,
            "verification_cache_misses": 0, "finish_attempts": 0,
            "finish_outcomes": {},
            "input_tokens_per_turn": None, "cached_input_tokens_per_turn": None,
            "cached_input_ratio": None, "updated_at": None,
        },
    }
    atomic_write_json(state_dir / "executor-context.json", value)
    atomic_write_json(handoff_dir / "executor-context.json", value, mode=0o444)
    return value


def _command_family(item: Mapping[str, Any]) -> str:
    """Return a bounded, argument-free command family for amplification telemetry."""
    raw = item.get("argv")
    tokens: list[str] = []
    if isinstance(raw, list):
        tokens = [str(value) for value in raw if str(value)]
    else:
        raw = item.get("command", item.get("cmd"))
        if isinstance(raw, str) and raw.strip():
            try:
                tokens = shlex.split(raw)
            except ValueError:
                tokens = raw.strip().split()
    if not tokens:
        return "unknown"
    first = Path(tokens[0]).name
    if first in {"bash", "sh", "zsh"} and "-lc" in tokens:
        try:
            inner = tokens[tokens.index("-lc") + 1]
            inner_tokens = shlex.split(inner)
            if inner_tokens:
                tokens = inner_tokens
                first = Path(tokens[0]).name
        except (IndexError, ValueError):
            pass
    if first.startswith("agent-workflow"):
        return " ".join(["agent-workflow", *tokens[1:3]])
    if first.startswith("python") and len(tokens) >= 3 and tokens[1] == "-m":
        module = tokens[2]
        if module.startswith("agent_workflow"):
            return "python -m agent_workflow"
        return f"python -m {module}"
    return first


def _event_runtime(events_path: Path) -> dict[str, Any]:
    event_count = 0
    completed_turns: set[str] = set()
    anonymous_turns = 0
    tool_ids: set[str] = set()
    anonymous_tools = 0
    command_ids: set[str] = set()
    anonymous_commands = 0
    tool_types: dict[str, int] = {}
    command_families: dict[str, int] = {}
    if not events_path.is_file():
        return {
            "provider_event_count": 0,
            "model_turn_count": None,
            "tool_call_count": None,
            "command_execution_count": None,
            "tool_call_types": {},
            "command_families": {},
        }
    for sequence, raw in enumerate(events_path.read_bytes().splitlines(), start=1):
        if not raw:
            continue
        event_count += 1
        try:
            event = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type", ""))
        if event_type == "turn.completed":
            identity = event.get("turn_id", event.get("id"))
            if isinstance(identity, (str, int)) and not isinstance(identity, bool):
                completed_turns.add(str(identity))
            else:
                anonymous_turns += 1
        item = event.get("item")
        if not isinstance(item, dict) or event_type not in {"item.completed", "tool.completed", "command.completed"}:
            continue
        item_type = str(item.get("type", ""))
        identity = item.get("id", event.get("item_id", event.get("id")))
        identity_text = str(identity) if isinstance(identity, (str, int)) and not isinstance(identity, bool) else f"anonymous-{sequence}"
        if item_type in _TOOL_ITEM_TYPES:
            tool_types[item_type] = tool_types.get(item_type, 0) + 1
            if identity_text.startswith("anonymous-"):
                anonymous_tools += 1
            else:
                tool_ids.add(identity_text)
        if item_type == "command_execution":
            family = _command_family(item)
            command_families[family] = command_families.get(family, 0) + 1
            if identity_text.startswith("anonymous-"):
                anonymous_commands += 1
            else:
                command_ids.add(identity_text)
    turns = len(completed_turns) + anonymous_turns
    tools = len(tool_ids) + anonymous_tools
    commands = len(command_ids) + anonymous_commands
    return {
        "provider_event_count": event_count,
        "model_turn_count": turns or None,
        "tool_call_count": tools or None,
        "command_execution_count": commands or None,
        "tool_call_types": dict(sorted(tool_types.items())),
        "command_families": dict(sorted(command_families.items())),
    }


def _protocol_runtime(state_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "protocol_command_counts": {},
        "message_kind_counts": {},
        "acceptance_command_executions": 0,
        "verification_cache_hits": 0,
        "verification_cache_misses": 0,
        "finish_attempts": 0,
        "finish_outcomes": {},
    }
    telemetry_path = state_dir / "handoff" / "protocol-telemetry.json"
    if telemetry_path.is_file():
        try:
            value = json.loads(telemetry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {}
        if isinstance(value, dict):
            counts = value.get("cli_command_counts")
            if isinstance(counts, dict):
                result["protocol_command_counts"] = {
                    str(key): int(number)
                    for key, number in counts.items()
                    if isinstance(number, int) and not isinstance(number, bool)
                }
            acceptance = value.get("acceptance")
            if isinstance(acceptance, dict):
                result["acceptance_command_executions"] = int(acceptance.get("executed", 0) or 0)
                result["verification_cache_hits"] = int(acceptance.get("cache_hits", 0) or 0)
                result["verification_cache_misses"] = int(acceptance.get("cache_misses", 0) or 0)
            finish = value.get("finish")
            if isinstance(finish, dict):
                result["finish_attempts"] = int(finish.get("attempts", 0) or 0)
                outcomes = finish.get("outcomes")
                if isinstance(outcomes, dict):
                    result["finish_outcomes"] = {
                        str(key): int(number)
                        for key, number in outcomes.items()
                        if isinstance(number, int) and not isinstance(number, bool)
                    }
    messages_path = state_dir / "messages.jsonl"
    if messages_path.is_file():
        counts: dict[str, int] = {}
        try:
            rows = messages_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            rows = []
        for raw in rows:
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict):
                kind = str(message.get("kind", "unknown"))
                counts[kind] = counts.get(kind, 0) + 1
        result["message_kind_counts"] = dict(sorted(counts.items()))
    return result


def update_executor_context_runtime(
    state_dir: Path, *, events_path: Path, provider_evidence: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    path = state_dir / "executor-context.json"
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    runtime = _event_runtime(events_path)
    runtime.update(_protocol_runtime(state_dir))
    aggregate = provider_evidence.get("aggregate") if isinstance(provider_evidence, Mapping) and isinstance(provider_evidence.get("aggregate"), Mapping) else {}
    turns = runtime.get("model_turn_count")
    input_tokens, cached_tokens = aggregate.get("input_tokens"), aggregate.get("cached_input_tokens")
    runtime["input_tokens_per_turn"] = round(float(input_tokens) / turns, 3) if isinstance(turns, int) and turns > 0 and isinstance(input_tokens, (int, float)) and not isinstance(input_tokens, bool) else None
    runtime["cached_input_tokens_per_turn"] = round(float(cached_tokens) / turns, 3) if isinstance(turns, int) and turns > 0 and isinstance(cached_tokens, (int, float)) and not isinstance(cached_tokens, bool) else None
    runtime["cached_input_ratio"] = (
        round(float(cached_tokens) / float(input_tokens), 6)
        if isinstance(input_tokens, (int, float)) and not isinstance(input_tokens, bool) and float(input_tokens) > 0
        and isinstance(cached_tokens, (int, float)) and not isinstance(cached_tokens, bool) else None
    )
    runtime["measurement_source"] = "provider-events"
    runtime["updated_at"] = utc_now()
    value["runtime"] = runtime
    atomic_write_json(path, value)
    return value
