"""Immutable contracts and capability narrowing for bounded hierarchy v1."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from ..contracts import validate_instance
from ..errors import WorkflowError
from ..path import read_regular_file, require_directory
from ..util import atomic_write_json, fsync_directory, validate_id

HIERARCHY_SCHEMA = "agent-workflow/orchestration-hierarchy/v1"
TEAM_DELEGATION_SCHEMA = "agent-workflow/team-delegation/v1"
CONTRACT_SET_SCHEMA = "agent-workflow/hierarchy-contract-set/v1"
_DIGEST_PREFIX = "sha256:"
_ALLOWED_KEYS = ("executors", "models", "agent_classes", "permissions", "commands")
_BUDGET_KEYS = (
    "max_workers",
    "max_concurrent_workers",
    "max_retries",
    "max_wall_seconds",
)


def _canonical_bytes(value: Mapping[str, Any], *, omit: str) -> bytes:
    material = copy.deepcopy(dict(value))
    material.pop(omit, None)
    return json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(value: Mapping[str, Any], *, omit: str) -> str:
    return _DIGEST_PREFIX + hashlib.sha256(_canonical_bytes(value, omit=omit)).hexdigest()


def _verify_digest(value: Mapping[str, Any], *, field: str, label: str) -> None:
    expected = _digest(value, omit=field)
    actual = value.get(field)
    if actual != expected:
        raise WorkflowError(f"{label} digest mismatch: expected {expected}, got {actual}")


def _validate_relative_path(value: str, *, label: str) -> None:
    if not isinstance(value, str) or not value or "\\" in value:
        raise WorkflowError(f"invalid {label}: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(part in {"", ".", ".."} for part in path.parts):
        raise WorkflowError(f"invalid {label}: {value!r}")


def _validate_unique_strings(values: Any, *, label: str) -> tuple[str, ...]:
    if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values):
        raise WorkflowError(f"{label} must be a list of non-empty strings")
    result = tuple(values)
    if len(result) != len(set(result)):
        raise WorkflowError(f"{label} must not contain duplicates")
    return result


def _team_map(hierarchy: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in hierarchy["teams"]:
        team_id = validate_id(item["team_id"], "team id")
        lead_id = validate_id(item["team_lead_agent_run_id"], "team lead Agent Run ID")
        if team_id in result:
            raise WorkflowError(f"duplicate team id in hierarchy contract: {team_id}")
        result[team_id] = lead_id
    return result


def _validate_unique_authority_identities(
    hierarchy: Mapping[str, Any],
    teams: Mapping[str, str],
) -> None:
    seen: dict[str, str] = {hierarchy["root_orchestrator_id"]: "root orchestrator"}
    for team_id, lead_id in teams.items():
        for identity, label in (
            (team_id, f"team {team_id}"),
            (lead_id, f"team lead for {team_id}"),
        ):
            previous = seen.get(identity)
            if previous is not None:
                raise WorkflowError(
                    f"duplicate hierarchy authority identity {identity!r}: "
                    f"used by {previous} and {label}"
                )
            seen[identity] = label


def seal_hierarchy_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a validated hierarchy contract with its canonical identity digest."""
    result = copy.deepcopy(dict(value))
    result["identity_sha256"] = _digest(result, omit="identity_sha256")
    validate_hierarchy_contract(result)
    return result


def validate_hierarchy_contract(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping):
        raise WorkflowError("hierarchy contract must be an object")
    contract = dict(value)
    validate_instance(contract, HIERARCHY_SCHEMA, artifact="hierarchy contract")
    if contract["allowed_depth"] != 2:
        raise WorkflowError("hierarchy allowed_depth must be exactly 2")
    validate_id(contract["orchestration_id"], "orchestration id")
    validate_id(contract["root_orchestrator_id"], "root orchestrator id")
    validate_id(contract["workflow_id"], "workflow id")
    teams = _team_map(contract)
    _validate_unique_authority_identities(contract, teams)
    budgets = contract["budgets"]
    if len(teams) > budgets["max_teams"]:
        raise WorkflowError("hierarchy declares more teams than max_teams")
    if budgets["max_concurrent_workers"] > budgets["max_total_workers"]:
        raise WorkflowError("hierarchy max_concurrent_workers exceeds max_total_workers")
    for key in _ALLOWED_KEYS:
        _validate_unique_strings(contract["allowed"][key], label=f"hierarchy allowed.{key}")
    _validate_unique_strings(contract["allowed_routes"], label="hierarchy allowed_routes")
    _verify_digest(contract, field="identity_sha256", label="hierarchy contract")


def seal_team_delegation_contract(
    value: Mapping[str, Any],
    hierarchy: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a narrowed, validated team contract with its canonical digest."""
    result = copy.deepcopy(dict(value))
    result["hierarchy_identity_sha256"] = hierarchy.get("identity_sha256")
    result["contract_sha256"] = _digest(result, omit="contract_sha256")
    validate_team_delegation_contract(result, hierarchy)
    return result


def validate_team_delegation_contract(
    value: Mapping[str, Any],
    hierarchy: Mapping[str, Any],
) -> None:
    if not isinstance(value, Mapping):
        raise WorkflowError("team delegation contract must be an object")
    validate_hierarchy_contract(hierarchy)
    contract = dict(value)
    validate_instance(contract, TEAM_DELEGATION_SCHEMA, artifact="team delegation contract")
    if contract["orchestration_id"] != hierarchy["orchestration_id"]:
        raise WorkflowError("team contract orchestration identity does not match hierarchy")
    if contract["root_orchestrator_id"] != hierarchy["root_orchestrator_id"]:
        raise WorkflowError("team contract root identity does not match hierarchy")
    if contract["hierarchy_identity_sha256"] != hierarchy["identity_sha256"]:
        raise WorkflowError("team contract hierarchy digest does not match hierarchy")

    team_id = validate_id(contract["team_id"], "team id")
    validate_id(contract["team_lead_agent_run_id"], "team lead Agent Run ID")
    declared = _team_map(hierarchy)
    if team_id not in declared:
        raise WorkflowError(f"team contract references undeclared team: {team_id}")
    if contract["team_lead_agent_run_id"] != declared[team_id]:
        raise WorkflowError("team lead Agent Run IDentity does not match hierarchy")

    parent_budget = hierarchy["budgets"]
    team_budget = contract["budgets"]
    comparisons = {
        "max_workers": "max_total_workers",
        "max_concurrent_workers": "max_concurrent_workers",
        "max_retries": "max_retries_per_worker",
        "max_wall_seconds": "max_wall_seconds",
    }
    for child_key, parent_key in comparisons.items():
        if team_budget[child_key] > parent_budget[parent_key]:
            raise WorkflowError(
                f"team budget {child_key}={team_budget[child_key]} widens "
                f"hierarchy {parent_key}={parent_budget[parent_key]}"
            )
    if team_budget["max_concurrent_workers"] > team_budget["max_workers"]:
        raise WorkflowError("team max_concurrent_workers exceeds max_workers")

    for key in _ALLOWED_KEYS:
        child = set(_validate_unique_strings(contract["allowed"][key], label=f"team allowed.{key}"))
        parent = set(hierarchy["allowed"][key])
        extra = sorted(child - parent)
        if extra:
            raise WorkflowError(
                f"team allowed.{key} widens hierarchy capability: {', '.join(extra)}"
            )
    routes = set(_validate_unique_strings(contract["message_routes"], label="team message_routes"))
    extra_routes = sorted(routes - set(hierarchy["allowed_routes"]))
    if extra_routes:
        raise WorkflowError(
            f"team message routes widen hierarchy capability: {', '.join(extra_routes)}"
        )

    for field in ("writable_scope", "no_go_scope"):
        for item in contract[field]:
            _validate_relative_path(item, label=f"team {field} path")
    scope_conflicts: list[str] = []
    writable_paths = [PurePosixPath(item).parts for item in contract["writable_scope"]]
    no_go_paths = [PurePosixPath(item).parts for item in contract["no_go_scope"]]
    for writable in writable_paths:
        for no_go in no_go_paths:
            shared = min(len(writable), len(no_go))
            if writable[:shared] == no_go[:shared]:
                scope_conflicts.append(
                    f"{'/'.join(writable)} <-> {'/'.join(no_go)}"
                )
    if scope_conflicts:
        raise WorkflowError(
            "team writable and no-go scopes overlap: " + ", ".join(sorted(scope_conflicts))
        )
    _verify_digest(contract, field="contract_sha256", label="team delegation contract")


def _encoded_json(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(value), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _install_immutable_json(path: Path, value: Mapping[str, Any]) -> str:
    expected = _encoded_json(value)
    if path.exists() or path.is_symlink():
        read = read_regular_file(path)
        if read.mode & 0o222:
            raise WorkflowError(f"installed hierarchy contract must be read-only: {path}")
        if read.data != expected:
            raise WorkflowError(f"immutable hierarchy contract already differs: {path}")
        return read.sha256
    atomic_write_json(path, dict(value), mode=0o400)
    read = read_regular_file(path)
    if read.mode & 0o222 or read.data != expected:
        raise WorkflowError(f"failed to install immutable hierarchy contract: {path}")
    return read.sha256


def _create_private_directory(path: Path) -> None:
    if path.exists() or path.is_symlink():
        require_directory(path, label="hierarchy contract directory")
        return
    require_directory(path.parent, label="hierarchy contract parent")
    os.mkdir(path, 0o700)
    fsync_directory(path.parent)
    require_directory(path, label="hierarchy contract directory")


def install_contract_set(
    root: Path,
    hierarchy: Mapping[str, Any],
    delegations: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Install one complete immutable HIER-001 contract set beneath *root*."""
    validate_hierarchy_contract(hierarchy)
    team_contracts = [dict(item) for item in delegations]
    by_team: dict[str, dict[str, Any]] = {}
    for contract in team_contracts:
        validate_team_delegation_contract(contract, hierarchy)
        team_id = contract["team_id"]
        if team_id in by_team:
            raise WorkflowError(f"duplicate team delegation contract: {team_id}")
        by_team[team_id] = contract
    expected_teams = set(_team_map(hierarchy))
    if set(by_team) != expected_teams:
        missing = sorted(expected_teams - set(by_team))
        extra = sorted(set(by_team) - expected_teams)
        raise WorkflowError(
            f"team contract set does not match hierarchy; missing={missing}, extra={extra}"
        )

    root = Path(root)
    _create_private_directory(root)
    teams_dir = root / "teams"
    _create_private_directory(teams_dir)
    hierarchy_file_sha256 = _install_immutable_json(root / "hierarchy.json", hierarchy)
    team_entries: list[dict[str, str]] = []
    for team_id in sorted(by_team):
        team_dir = teams_dir / team_id
        _create_private_directory(team_dir)
        path = team_dir / "delegation-contract.json"
        file_sha256 = _install_immutable_json(path, by_team[team_id])
        team_entries.append(
            {
                "team_id": team_id,
                "contract_sha256": by_team[team_id]["contract_sha256"],
                "file_sha256": _DIGEST_PREFIX + file_sha256,
                "path": f"teams/{team_id}/delegation-contract.json",
            }
        )
    manifest = {
        "schema": CONTRACT_SET_SCHEMA,
        "orchestration_id": hierarchy["orchestration_id"],
        "hierarchy_identity_sha256": hierarchy["identity_sha256"],
        "hierarchy_file_sha256": _DIGEST_PREFIX + hierarchy_file_sha256,
        "hierarchy_path": "hierarchy.json",
        "teams": team_entries,
    }
    _install_immutable_json(root / "contract-set.json", manifest)
    return manifest


def _read_readonly_json(path: Path) -> dict[str, Any]:
    read = read_regular_file(path)
    if read.mode & 0o222:
        raise WorkflowError(f"installed hierarchy contract must be read-only: {path}")
    try:
        value = json.loads(read.data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"invalid installed hierarchy JSON: {path}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"installed hierarchy artifact must be an object: {path}")
    return value


def read_contract_set(root: Path) -> tuple[dict[str, Any], tuple[dict[str, Any], ...], dict[str, Any]]:
    """Read and verify one installed immutable contract set."""
    root = require_directory(Path(root), label="hierarchy contract root")
    hierarchy = _read_readonly_json(root / "hierarchy.json")
    validate_hierarchy_contract(hierarchy)
    manifest = _read_readonly_json(root / "contract-set.json")
    if manifest.get("schema") != CONTRACT_SET_SCHEMA:
        raise WorkflowError("unexpected hierarchy contract-set schema")
    hierarchy_read = read_regular_file(root / "hierarchy.json")
    if manifest.get("hierarchy_file_sha256") != _DIGEST_PREFIX + hierarchy_read.sha256:
        raise WorkflowError("hierarchy contract-set file digest mismatch")
    if manifest.get("hierarchy_identity_sha256") != hierarchy["identity_sha256"]:
        raise WorkflowError("hierarchy contract-set identity digest mismatch")

    delegations: list[dict[str, Any]] = []
    for entry in manifest.get("teams", []):
        if not isinstance(entry, dict):
            raise WorkflowError("invalid hierarchy contract-set team entry")
        raw_team_id = entry.get("team_id")
        if not isinstance(raw_team_id, str):
            raise WorkflowError("hierarchy contract-set team entry has no string team_id")
        team_id = validate_id(raw_team_id, "team id")
        expected_path = f"teams/{team_id}/delegation-contract.json"
        if entry.get("path") != expected_path:
            raise WorkflowError("hierarchy contract-set contains an unexpected team path")
        path = root / expected_path
        contract = _read_readonly_json(path)
        validate_team_delegation_contract(contract, hierarchy)
        read = read_regular_file(path)
        if entry.get("file_sha256") != _DIGEST_PREFIX + read.sha256:
            raise WorkflowError(f"team contract file digest mismatch: {team_id}")
        if entry.get("contract_sha256") != contract["contract_sha256"]:
            raise WorkflowError(f"team contract identity digest mismatch: {team_id}")
        delegations.append(contract)
    if {item["team_id"] for item in delegations} != set(_team_map(hierarchy)):
        raise WorkflowError("installed team contract set does not match hierarchy")
    return hierarchy, tuple(delegations), manifest
