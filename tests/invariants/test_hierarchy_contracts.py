from __future__ import annotations

import copy
import stat
from pathlib import Path

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.hierarchy import (
    install_contract_set,
    read_contract_set,
    seal_hierarchy_contract,
    seal_team_delegation_contract,
    validate_hierarchy_contract,
    validate_team_delegation_contract,
)

DIGEST = "sha256:" + "a" * 64


def hierarchy_input() -> dict:
    return {
        "schema": "agent-workflow/orchestration-hierarchy/v1",
        "version": 1,
        "orchestration_id": "root-001",
        "root_orchestrator_id": "orchestrator-001",
        "workflow_id": "workflow-001",
        "allowed_depth": 2,
        "tmux_session_name": "aw-root-001",
        "budgets": {
            "max_teams": 2,
            "max_total_workers": 8,
            "max_concurrent_workers": 4,
            "max_interactive_panes": 10,
            "max_retries_per_worker": 2,
            "max_wall_seconds": 7200,
        },
        "terminal_policy": {
            "allowed_modes": ["current"],
            "external_argv_prefixes": [],
        },
        "allowed": {
            "executors": ["codex", "claude"],
            "models": ["gpt-5.6", "claude-opus"],
            "agent_classes": ["implementation", "review"],
            "permissions": ["workspace-write", "read-only"],
            "commands": ["run", "status", "message"],
        },
        "allowed_routes": ["root-to-team", "team-to-root", "team-to-worker", "worker-to-team"],
        "teams": [
            {
                "team_id": "implementation",
                "team_lead_session_id": "lead-implementation",
                "parent_principal": "root",
            },
            {
                "team_id": "review",
                "team_lead_session_id": "lead-review",
                "parent_principal": "root",
            },
        ],
        "source": {
            "repository": "file:///workspace/project",
            "revision": "abc123",
            "snapshot_sha256": DIGEST,
            "prompt_pack_id": "hierarchical-multi-team-orchestration",
            "prompt_pack_sha256": DIGEST,
        },
        "created_at": "2026-08-01T20:00:00+00:00",
    }


def team_input(team_id: str, lead_id: str) -> dict:
    return {
        "schema": "agent-workflow/team-delegation/v1",
        "version": 1,
        "orchestration_id": "root-001",
        "root_orchestrator_id": "orchestrator-001",
        "team_id": team_id,
        "team_lead_session_id": lead_id,
        "objective": f"Complete bounded work for {team_id}",
        "deliverables": [f"reports/{team_id}.json"],
        "writable_scope": [f"work/{team_id}"],
        "no_go_scope": ["secrets"],
        "stop_conditions": ["authority mismatch", "budget exhausted"],
        "dependencies": [],
        "required_outputs": ["agent-workflow/task-result/v1"],
        "budgets": {
            "max_workers": 3,
            "max_concurrent_workers": 2,
            "max_interactive_panes": 4,
            "max_retries": 1,
            "max_wall_seconds": 3600,
        },
        "allowed": {
            "executors": ["codex"],
            "models": ["gpt-5.6"],
            "agent_classes": ["implementation"],
            "permissions": ["workspace-write"],
            "commands": ["run", "status"],
        },
        "message_routes": ["team-to-root", "team-to-worker", "worker-to-team"],
        "required_reviews": ["independent"],
        "required_approvals": ["root-final"],
        "parent_action_cursor": 0,
    }


def valid_contracts() -> tuple[dict, tuple[dict, dict]]:
    hierarchy = seal_hierarchy_contract(hierarchy_input())
    teams = tuple(
        seal_team_delegation_contract(team_input(item[0], item[1]), hierarchy)
        for item in (
            ("implementation", "lead-implementation"),
            ("review", "lead-review"),
        )
    )
    return hierarchy, teams  # type: ignore[return-value]


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("models", ["unapproved-model"], "widens hierarchy capability"),
        ("commands", ["shell"], "widens hierarchy capability"),
        ("permissions", ["host-admin"], "widens hierarchy capability"),
    ],
)
def test_team_capabilities_cannot_widen_parent(field: str, value: list[str], match: str) -> None:
    hierarchy = seal_hierarchy_contract(hierarchy_input())
    candidate = team_input("implementation", "lead-implementation")
    candidate["allowed"][field] = value

    with pytest.raises(WorkflowError, match=match):
        seal_team_delegation_contract(candidate, hierarchy)


def test_team_budgets_cannot_widen_parent() -> None:
    hierarchy = seal_hierarchy_contract(hierarchy_input())
    candidate = team_input("implementation", "lead-implementation")
    candidate["budgets"]["max_workers"] = 9

    with pytest.raises(WorkflowError, match="widens hierarchy"):
        seal_team_delegation_contract(candidate, hierarchy)


def test_fixed_depth_and_declared_team_identity_are_enforced() -> None:
    hierarchy_source = hierarchy_input()
    hierarchy_source["allowed_depth"] = 3
    with pytest.raises(WorkflowError, match="allowed_depth"):
        seal_hierarchy_contract(hierarchy_source)

    hierarchy = seal_hierarchy_contract(hierarchy_input())
    with pytest.raises(WorkflowError, match="undeclared team"):
        seal_team_delegation_contract(team_input("other", "lead-other"), hierarchy)


def test_duplicate_team_lead_identity_is_rejected() -> None:
    source = hierarchy_input()
    source["teams"][1]["team_lead_session_id"] = source["teams"][0]["team_lead_session_id"]

    with pytest.raises(WorkflowError, match="duplicate hierarchy authority identity"):
        seal_hierarchy_contract(source)


def test_root_and_team_authority_identity_collision_is_rejected() -> None:
    source = hierarchy_input()
    source["teams"][0]["team_id"] = source["root_orchestrator_id"]

    with pytest.raises(WorkflowError, match="duplicate hierarchy authority identity"):
        seal_hierarchy_contract(source)


def test_scope_traversal_and_digest_tamper_fail_closed() -> None:
    hierarchy = seal_hierarchy_contract(hierarchy_input())
    candidate = team_input("implementation", "lead-implementation")
    candidate["writable_scope"] = ["../outside"]
    with pytest.raises(WorkflowError, match="invalid team writable_scope path"):
        seal_team_delegation_contract(candidate, hierarchy)

    nested = team_input("implementation", "lead-implementation")
    nested["writable_scope"] = ["work"]
    nested["no_go_scope"] = ["work/secrets"]
    with pytest.raises(WorkflowError, match="writable and no-go scopes overlap"):
        seal_team_delegation_contract(nested, hierarchy)

    sealed = seal_team_delegation_contract(
        team_input("implementation", "lead-implementation"), hierarchy
    )
    sealed["objective"] = "tampered"
    with pytest.raises(WorkflowError, match="digest mismatch"):
        validate_team_delegation_contract(sealed, hierarchy)


def test_conflicting_reinstall_and_symlink_root_fail_closed(tmp_path: Path) -> None:
    hierarchy, teams = valid_contracts()
    root = tmp_path / "orchestration"
    install_contract_set(root, hierarchy, teams)

    changed = copy.deepcopy(teams[0])
    changed.pop("contract_sha256")
    changed["objective"] = "different immutable objective"
    changed = seal_team_delegation_contract(changed, hierarchy)
    with pytest.raises(WorkflowError, match="already differs"):
        install_contract_set(root, hierarchy, (changed, teams[1]))

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "linked-root"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(WorkflowError, match="not a regular directory"):
        install_contract_set(link, hierarchy, teams)
