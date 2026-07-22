import tempfile
import unittest
from pathlib import Path

from agent_workflow.config import defaults, load_settings
from agent_workflow.errors import WorkflowError


class ConfigTests(unittest.TestCase):
    def test_default_codex_command_uses_workspace_write_sandbox(self):
        self.assertEqual(
            defaults().executors["codex"],
            [
                "codex",
                "exec",
                "--sandbox",
                "workspace-write",
                "--skip-git-repo-check",
                "-",
            ],
        )

    def test_executor_and_paths_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.toml"
            config.write_text(
                f'''[paths]\nstate_root = "{root / 'state'}"\nworktree_root = "{root / 'worktrees'}"\n\n[terminal]\nstall_minutes = 7\n\n[executors.test]\ncommand = ["cat"]\n''',
                encoding="utf-8",
            )
            settings = load_settings(config)
            self.assertEqual(settings.stall_minutes, 7)
            self.assertEqual(settings.executors["test"], ["cat"])
            self.assertEqual(settings.state_root, root / "state")

    def test_invalid_numeric_and_boolean_values_raise_workflow_error(self):
        invalid_values = (
            ("[terminal]\nstall_minutes = \"many\"\n", "must be an integer"),
            ("[terminal]\ncapture_lines = true\n", "must be an integer"),
            ("[git]\nrequire_clean_source = \"false\"\n", "must be a boolean"),
            ("[pack]\nwrite_sha256 = 1\n", "must be a boolean"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.toml"
            for content, message in invalid_values:
                with self.subTest(content=content):
                    config.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(WorkflowError, message):
                        load_settings(config)
