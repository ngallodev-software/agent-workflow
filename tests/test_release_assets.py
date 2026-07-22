from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseAssetTests(unittest.TestCase):
    def test_release_asset_audit_passes(self) -> None:
        result = subprocess.run(
            ["python3", str(ROOT / "scripts/audit-release-assets.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_skill_has_yaml_frontmatter(self) -> None:
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), path)
            self.assertIn("\nname:", text.split("---", 2)[1], path)
            self.assertIn("\ndescription:", text.split("---", 2)[1], path)
