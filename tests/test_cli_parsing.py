import unittest

from agent_workflow.cli import _parse_args, build_parser


class CliParsingTests(unittest.TestCase):
    def test_launch_options_can_follow_positionals(self):
        args = _parse_args(
            build_parser(),
            [
                "launch",
                "sample-p0-01",
                "/tmp/work",
                "ticket.md",
                "--ticket",
                "P0-01",
                "--pack",
                "sample-pack",
                "--job",
                "jobs/P0-01.json",
                "--executor",
                "codex",
            ],
        )
        self.assertEqual(args.ticket, "P0-01")
        self.assertEqual(args.executor, "codex")
        self.assertEqual(str(args.job), "jobs/P0-01.json")
        self.assertIsNone(args.explicit_command)

    def test_explicit_command_is_preserved_after_separator(self):
        args = _parse_args(
            build_parser(),
            [
                "launch",
                "sample-p0-01",
                "/tmp/work",
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

    def test_global_config_can_follow_subcommand(self):
        args = _parse_args(
            build_parser(), ["doctor", "--config", "/tmp/workflow.toml"]
        )
        self.assertEqual(str(args.config), "/tmp/workflow.toml")
