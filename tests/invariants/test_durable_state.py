from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from agent_workflow.cli import build_parser
from agent_workflow.command_catalog import build_command_catalog, filter_catalog
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.messages import append_message, replay_messages
from agent_workflow.routing import advise_routing
from agent_workflow.scheduler import calculate_eligibility, plan_launches


def test_message_log_is_contiguous_replayable_and_fail_closed(tmp_path: Path) -> None:
    records = [
        append_message(tmp_path, session_id="run", direction="parent_to_child", kind="steer", actor="parent", content="inspect"),
        append_message(tmp_path, session_id="run", direction="child_to_parent", kind="progress", actor="child", content="working"),
    ]
    assert [item["sequence"] for item in records] == [1, 2]
    assert replay_messages(tmp_path, after_sequence=1) == [records[1]]

    path = tmp_path / "messages.jsonl"
    path.write_text(path.read_text() + "not-json\n", encoding="utf-8")
    with pytest.raises(WorkflowError):
        replay_messages(tmp_path)


def test_scheduler_capacity_and_dependency_release_are_graph_invariants() -> None:
    snapshot = {
        "nodes": [
            {"node_id": "a", "kind": "task", "dependencies": []},
            {"node_id": "b", "kind": "task", "dependencies": ["a"]},
            {"node_id": "c", "kind": "task", "dependencies": []},
        ]
    }
    status = {
        "nodes": [
            {"node_id": "a", "state": "completed"},
            {"node_id": "b", "state": "eligible"},
            {"node_id": "c", "state": "running"},
        ]
    }
    assert calculate_eligibility(snapshot, status) == ["b"]
    assert plan_launches(snapshot, status, max_parallelism=1) == []
    assert plan_launches(snapshot, status, max_parallelism=2) == ["b"]


def test_routing_is_deterministic_advisory_and_cannot_override_enforced_policy() -> None:
    metadata = {"task_type": "review", "risk": "high", "interactive": True}
    enforced = {"agent_class": "implementation", "executor": "codex", "model": "gpt-5.6-luna", "interactive": False}
    settings = defaults()
    first = advise_routing(metadata, settings, enforced_selection=enforced)
    second = advise_routing(dict(metadata), settings, enforced_selection=dict(enforced))
    assert first == second
    recommendation = first["recommendation"]
    assert recommendation["agent_class"] in settings.agent_classes
    assert recommendation["executor"] in settings.executors
    assert first["enforced_selection"] == enforced
    assert first["policy_disagreements"]


def test_invalid_scheduler_parallelism_is_rejected() -> None:
    with pytest.raises(WorkflowError):
        plan_launches({"nodes": []}, {"nodes": []}, max_parallelism=0)


def test_parser_command_catalog_is_complete_deterministic_and_role_scoped() -> None:
    parser = build_parser()

    def leaves(current: argparse.ArgumentParser, prefix: tuple[str, ...] = ()) -> set[str]:
        subparsers = [
            action
            for action in current._actions
            if isinstance(action, argparse._SubParsersAction)
        ]
        if not subparsers:
            return {" ".join(prefix)}
        result: set[str] = set()
        for action in subparsers:
            seen: set[int] = set()
            for name, child in action.choices.items():
                if id(child) in seen:
                    continue
                seen.add(id(child))
                result.update(leaves(child, (*prefix, name)))
        return result

    first = build_command_catalog(parser)
    second = build_command_catalog(build_parser())
    assert first == second
    represented = {item["command"] for item in first["commands"]}
    assert represented == leaves(parser)
    assert all("[-h]" not in item["synopsis"] for item in first["commands"])
    implementation = {
        item["command"] for item in filter_catalog(first, "implementation")["commands"]
    }
    assert {"progress", "ack", "agent task-complete"} <= implementation
    assert "worktree remove" not in implementation
    orchestrator = {
        item["command"] for item in filter_catalog(first, "orchestrator")["commands"]
    }
    assert "archive" in orchestrator
    assert "archive" not in implementation
