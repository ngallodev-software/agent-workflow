import importlib.util

from agent_workflow.cli_contract import BUILTIN_TOP_LEVEL_COMMANDS, EVALUATION_TEMPLATE_KINDS
from agent_workflow.cli_parser import build_parser


def test_benchmark_is_not_a_core_command_anymore():
    assert "benchmark" not in BUILTIN_TOP_LEVEL_COMMANDS
    parser = build_parser()
    command_action = next(action for action in parser._actions if getattr(action, "dest", None) == "command")
    assert "benchmark" not in command_action.choices


def test_legacy_benchmark_templates_moved_out_of_core():
    assert "benchmark-manifest" not in EVALUATION_TEMPLATE_KINDS
    assert "benchmark-report" not in EVALUATION_TEMPLATE_KINDS
    assert importlib.util.find_spec("agent_workflow.benchmarking") is None
