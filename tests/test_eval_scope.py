import subprocess
import tempfile
import unittest
from pathlib import Path

from agent_workflow.eval.scope import ScopePolicy, collect_scope, compare_scope


class ScopeCollectorTests(unittest.TestCase):
    def test_detects_ignored_mutation_and_nested_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            receipts = root / "receipts"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.test"], check=True)
            (repo / ".gitignore").write_text("private.txt\n", encoding="utf-8")
            (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
            (repo / "private.txt").write_text("secret\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
            policy = ScopePolicy(repo, writable_paths=("tracked.txt",))

            baseline = collect_scope(repo, phase="baseline", policy=policy, receipt_dir=receipts)
            (repo / "tracked.txt").write_text("allowed\n", encoding="utf-8")
            (repo / "private.txt").write_text("changed\n", encoding="utf-8")
            nested = repo / "nested"
            nested.mkdir()
            subprocess.run(["git", "init", "-q", str(nested)], check=True)
            post = collect_scope(repo, phase="post", policy=policy, receipt_dir=receipts)
            result = compare_scope(baseline, post, policy)

            self.assertIn("private.txt", result["violations"])
            self.assertIn("nested/.git", result["violations"])
            self.assertNotIn("tracked.txt", result["violations"])
            self.assertIn("private.txt", baseline["repositories"][0]["ignored"])

    def test_disposable_tree_is_explicitly_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cache").mkdir()
            (root / "cache" / "value").write_text("x", encoding="utf-8")
            policy = ScopePolicy(root, disposable_trees=("cache/",))
            result = collect_scope(root, phase="baseline", policy=policy, receipt_dir=root.parent / "receipts")
            self.assertEqual(result["inventory"], [])
            self.assertEqual(result["excluded"], ["cache/"])

    def test_commits_since_baseline_and_escaping_symlinks_are_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            receipts = root / "receipts"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.test"], check=True)
            tracked = repo / "tracked.txt"
            tracked.write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
            policy = ScopePolicy(repo, writable_paths=("tracked.txt",))
            baseline = collect_scope(repo, phase="baseline", policy=policy, receipt_dir=receipts)
            tracked.write_text("committed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "commit", "-qam", "agent"], check=True)
            outside = root / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            (repo / "escape").symlink_to(outside)
            post = collect_scope(repo, phase="post", policy=policy, receipt_dir=receipts)
            result = compare_scope(baseline, post, policy)

            self.assertIn("tracked.txt", post["repositories"][0]["committed"])
            self.assertIn("escape", result["violations"])
