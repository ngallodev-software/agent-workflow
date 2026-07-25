from __future__ import annotations

import importlib.util
import subprocess
import unittest
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "scripts" / "audit-release-assets.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("audit_release_assets", AUDIT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseAssetTests(unittest.TestCase):
    def test_release_asset_audit_passes(self) -> None:
        result = subprocess.run(
            ["python3", str(AUDIT_SCRIPT)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_release_files_excludes_git_control_paths(self) -> None:
        module = _load_audit_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "keep.txt").write_text("keep", encoding="utf-8")

            git_dir = root / ".git"
            git_dir.mkdir()
            (git_dir / "config").write_text("config", encoding="utf-8")
            (git_dir / "objects").mkdir()
            (git_dir / "objects" / "obj").write_text("obj", encoding="utf-8")

            self.assertEqual(
                [path.relative_to(root).as_posix() for path in module.release_files(root)],
                ["keep.txt"],
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "keep.txt").write_text("keep", encoding="utf-8")
            (root / ".git").write_text("gitdir: /tmp/repo/.git/worktrees/demo\n", encoding="utf-8")

            self.assertEqual(
                [path.relative_to(root).as_posix() for path in module.release_files(root)],
                ["keep.txt"],
            )

    def test_every_skill_has_yaml_frontmatter(self) -> None:
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), path)
            self.assertIn("\nname:", text.split("---", 2)[1], path)
            self.assertIn("\ndescription:", text.split("---", 2)[1], path)
