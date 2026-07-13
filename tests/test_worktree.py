import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from agent_workflow.config import defaults
from agent_workflow.worktrees import create, remove


@unittest.skipUnless(shutil.which("git"), "git is required")
class WorktreeTests(unittest.TestCase):
    def test_create_and_remove_clean_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "test@example.test"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "Test"],
                check=True,
            )
            (repo / "README.md").write_text("test\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-qm", "initial"],
                check=True,
            )
            settings = defaults(root / "missing.toml")
            destination = root / "worktree"
            result = create(
                settings,
                repo=repo,
                ticket_id="P0-01",
                base_ref="HEAD",
                destination=destination,
            )
            self.assertTrue(destination.is_dir())
            self.assertEqual(result["branch"], "impl/p0-01")
            removed = remove(repo, destination, delete_branch=True)
            self.assertTrue(removed["branch_deleted"])
            self.assertFalse(destination.exists())
