import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_workflow.cli import _parse_args, build_parser, main
from agent_workflow.errors import InteractiveCapacityError


class CliParsingTests(unittest.TestCase):
    def test_launch_options_can_follow_positionals(self):
        args = _parse_args(
            build_parser(),
            [
                "launch",
                "sample-p0-01",
                "worktree",
                "ticket.md",
                "--ticket",
                "P0-01",
                "--pack",
                "sample-pack",
                "--job",
                "jobs/P0-01.json",
                "--executor",
                "codex",
                "--model",
                "gpt-5.4-mini",
            ],
        )
        self.assertEqual(args.ticket, "P0-01")
        self.assertEqual(args.executor, "codex")
        self.assertEqual(args.model, "gpt-5.4-mini")
        self.assertEqual(str(args.job), "jobs/P0-01.json")
        self.assertIsNone(args.explicit_command)

    def test_explicit_command_is_preserved_after_separator(self):
        args = _parse_args(
            build_parser(),
            [
                "launch",
                "sample-p0-01",
                "worktree",
                "ticket.md",
                "--ticket",
                "P0-01",
                "--",
                "codex",
                "exec",
                "--sandbox",
                "workspace-write",
                "-",
            ],
        )
        self.assertEqual(
            args.explicit_command,
            ["codex", "exec", "--sandbox", "workspace-write", "-"],
        )

    def test_global_json_can_follow_subcommand(self):
        args = _parse_args(build_parser(), ["doctor", "--json"])
        self.assertEqual(args.command, "doctor")
        self.assertTrue(args.json)

    def test_interactive_model_policy_flags_parse(self):
        args = _parse_args(
            build_parser(),
            [
                "launch", "run", "work", "prompt.md", "--executor", "claude",
                "--model", "opus", "--interactive", "--allow-no-go-model",
            ],
        )
        self.assertTrue(args.interactive)
        self.assertTrue(args.allow_no_go_model)
        self.assertEqual(args.model, "opus")

    def test_pane_limit_action_parses(self):
        args = _parse_args(
            build_parser(),
            ["launch", "run", "work", "prompt", "--pane-limit-action", "close-idle"],
        )
        self.assertEqual(args.pane_limit_action, "close-idle")

    def test_prompt_can_choose_detached_non_interactive_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            work.mkdir()
            prompt = root / "prompt.md"
            prompt.write_text("task", encoding="utf-8")
            capacity = InteractiveCapacityError(count=3, maximum=3, idle_sessions=[])
            with (
                patch("agent_workflow.cli.launch_session", side_effect=[capacity, {"status": "launched"}]) as launch,
                patch("agent_workflow.cli.sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="n"),
            ):
                self.assertEqual(
                    main(["launch", "run", str(work), str(prompt), "--executor", "codex"]),
                    0,
                )
            self.assertIsNone(launch.call_args_list[0].kwargs["interactive"])
            self.assertFalse(launch.call_args_list[1].kwargs["interactive"])

    def test_explicit_close_idle_action_closes_only_required_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            work.mkdir()
            prompt = root / "prompt.md"
            prompt.write_text("task", encoding="utf-8")
            capacity = InteractiveCapacityError(
                count=3,
                maximum=3,
                idle_sessions=[
                    {"session_id": "idle-1", "agent_name": "larry", "state": "idle_reusable"}
                ],
            )
            with (
                patch("agent_workflow.cli.launch_session", side_effect=[capacity, {"status": "launched"}]),
                patch("agent_workflow.cli.kill_session") as kill,
            ):
                self.assertEqual(
                    main([
                        "launch", "run", str(work), str(prompt), "--executor", "codex",
                        "--pane-limit-action", "close-idle",
                    ]),
                    0,
                )
            kill.assert_called_once()
            self.assertEqual(kill.call_args.args[1], "idle-1")

    def test_global_config_can_follow_subcommand(self):
        args = _parse_args(
            build_parser(), ["doctor", "--config", "workflow.toml"]
        )
        self.assertEqual(str(args.config), "workflow.toml")

    def test_control_commands_preserve_message_contract_inputs(self):
        steer = _parse_args(
            build_parser(), ["steer", "run-1", "inspect tests", "--actor", "parent"]
        )
        watch = _parse_args(
            build_parser(), ["watch", "run-1", "--after", "7", "--timeout", "1.5"]
        )
        self.assertEqual((steer.command, steer.actor, steer.content), ("steer", "parent", "inspect tests"))
        self.assertEqual((watch.command, watch.after, watch.timeout), ("watch", 7, 1.5))
