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

    def test_workflow_commands_parse_paths(self):
        validate = _parse_args(build_parser(), ["workflow", "validate", "snapshot.json"])
        start = _parse_args(build_parser(), ["workflow", "start", "run", "snapshot.json"])
        status = _parse_args(build_parser(), ["workflow", "status", "run", "snapshot.json"])
        resume = _parse_args(build_parser(), ["workflow", "resume", "run", "snapshot.json"])
        self.assertEqual((validate.command, validate.workflow_command), ("workflow", "validate"))
        self.assertEqual(str(start.run_dir), "run")
        self.assertEqual(str(status.run_dir), "run")
        self.assertEqual(str(resume.snapshot), "snapshot.json")

    def test_workflow_validate_uses_default_service_root(self):
        result = {
            "schema": "agent-workflow/workflow-node-result/v1",
            "workflow_id": "wf-1",
            "action": "validate",
            "result": {"snapshot_sha256": "abc", "node_count": 1},
        }
        with (
            patch("agent_workflow.cli.WorkflowService.validate", return_value=result) as validate,
            patch("agent_workflow.cli._print_json") as print_json,
            patch("agent_workflow.cli._print_mapping") as print_mapping,
        ):
            self.assertEqual(main(["workflow", "validate", "snapshot.json", "--json"]), 0)
        validate.assert_called_once()
        self.assertEqual(str(validate.call_args.args[0]), "snapshot.json")
        print_json.assert_called_once_with(result)
        print_mapping.assert_not_called()

    def test_workflow_validate_human_output_uses_default_service_root(self):
        result = {
            "schema": "agent-workflow/workflow-node-result/v1",
            "workflow_id": "wf-1",
            "action": "validate",
            "result": {"snapshot_sha256": "abc", "node_count": 1},
        }
        with (
            patch("agent_workflow.cli.WorkflowService.validate", return_value=result) as validate,
            patch("agent_workflow.cli._print_json") as print_json,
            patch("agent_workflow.cli._print_mapping") as print_mapping,
        ):
            self.assertEqual(main(["workflow", "validate", "snapshot.json"]), 0)
        validate.assert_called_once()
        self.assertEqual(str(validate.call_args.args[0]), "snapshot.json")
        print_mapping.assert_called_once_with(result)
        print_json.assert_not_called()
