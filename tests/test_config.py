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
        self.assertTrue(defaults().mouse)
        self.assertEqual(defaults().orchestrator_side, "left")
        self.assertEqual(defaults().max_interactive_agent_width, 2)
        self.assertEqual(defaults().max_interactive_agent_vertical, 3)
        self.assertEqual(defaults().max_interactive_agent_panes, 6)
        self.assertEqual(defaults().executor_policies["codex"].default_model, "gpt-5.4-mini")
        self.assertEqual(
            defaults().executor_policies["claude"].interactive_permission_args,
            ("--permission-mode", "manual"),
        )
        self.assertIn("haiku", defaults().executor_policies["claude"].models)
        self.assertIn("fable", defaults().executor_policies["claude"].no_go_models)
        self.assertFalse(defaults().agent_classes["exploratory"].interactive)
        self.assertEqual(
            defaults().agent_classes["exploratory"].allowed_models,
            {"claude": ("haiku",), "codex": ("gpt-5.4-mini",)},
        )
        self.assertFalse(defaults().agent_classes["review"].interactive)
        self.assertTrue(defaults().agent_classes["implementation"].interactive)

    def test_executor_and_paths_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.toml"
            config.write_text(
                f'''[paths]\nstate_root = "{root / 'state'}"\nworktree_root = "{root / 'worktrees'}"\n\n[terminal]\nstall_minutes = 7\nmax_interactive_agent_width = 4\nmax_interactive_agent_vertical = 2\n\n[executors.test]\ncommand = ["cat"]\ninteractive_command = ["cat"]\nmodels = ["small", "large"]\ndefault_model = "small"\nno_go_models = ["large"]\nmodel_arg = ["--model"]\npermission_args = ["--safe"]\n''',
                encoding="utf-8",
            )
            settings = load_settings(config)
            self.assertEqual(settings.stall_minutes, 7)
            self.assertEqual(settings.max_interactive_agent_width, 4)
            self.assertEqual(settings.max_interactive_agent_vertical, 2)
            self.assertEqual(settings.max_interactive_agent_panes, 8)
            self.assertEqual(settings.executors["test"], ["cat"])
            self.assertEqual(settings.executor_policies["test"].models, ("small", "large"))
            self.assertEqual(
                settings.executor_policies["test"].interactive_permission_args,
                ("--safe",),
            )
            self.assertEqual(
                settings.executor_policies["test"].non_interactive_permission_args,
                ("--safe",),
            )
            self.assertEqual(settings.state_root, root / "state")

    def test_default_model_must_be_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.toml"
            config.write_text(
                '[executors.test]\ncommand=["cat"]\nmodels=["small"]\ndefault_model="large"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(WorkflowError, "must be listed"):
                load_settings(config)

    def test_invalid_numeric_and_boolean_values_raise_workflow_error(self):
        invalid_values = (
            ("[terminal]\nstall_minutes = \"many\"\n", "must be an integer"),
            ("[terminal]\ncapture_lines = true\n", "must be an integer"),
            ("[git]\nrequire_clean_source = \"false\"\n", "must be a boolean"),
            ("[pack]\nwrite_sha256 = 1\n", "must be a boolean"),
            ("[terminal]\nmax_interactive_agent_width = 0\n", "invalid stall_minutes"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.toml"
            for content, message in invalid_values:
                with self.subTest(content=content):
                    config.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(WorkflowError, message):
                        load_settings(config)
