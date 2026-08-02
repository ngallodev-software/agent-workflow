from __future__ import annotations

from agent_workflow.cli import build_parser as facade_build_parser
from agent_workflow.cli_parser import build_parser
from agent_workflow.command_catalog import build_command_catalog


def test_cli_facade_exports_the_authoritative_parser_builder() -> None:
    assert facade_build_parser is build_parser


def test_extracted_parser_still_drives_the_complete_command_catalog() -> None:
    catalog = build_command_catalog(build_parser())
    top_level = {entry["path"][0] for entry in catalog["commands"] if entry["path"]}

    assert {
        "benchmark",
        "commands",
        "completion",
        "config",
        "doctor",
        "eval",
        "index",
        "launch",
        "orchestrator",
        "pack",
        "plugins",
        "status",
        "supervisor",
        "workflow",
        "worktree",
    } <= top_level
