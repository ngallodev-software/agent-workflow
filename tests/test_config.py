import tempfile
import unittest
from pathlib import Path

from agent_workflow.config import load_settings


class ConfigTests(unittest.TestCase):
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
