from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]


class InstallUninstallTests(unittest.TestCase):
    def _run(self, script: str, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
        dependency_root = str(Path(jsonschema.__file__).resolve().parents[1])
        inherited = os.environ.get("PYTHONPATH")
        pythonpath = dependency_root + (os.pathsep + inherited if inherited else "")
        env = {**os.environ, "HOME": str(home), "PYTHONPATH": pythonpath}
        return subprocess.run(
            [str(ROOT / script), *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_install_and_uninstall_owned_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            installed = self._run("install.sh", home, "--no-deps")
            self.assertEqual(installed.returncode, 0, installed.stderr)
            launcher = home / ".local/bin/agent-workflow"
            self.assertEqual(launcher.resolve(), (ROOT / "bin/agent-workflow").resolve())
            for root in (
                home / ".agents/skills",
                home / ".codex/skills",
                home / ".claude/skills",
            ):
                for skill in (
                    "agent-workflow-orchestrator",
                    "delegated-implementation",
                    "prompt-pack-builder",
                    "phase-gate-review",
                ):
                    self.assertEqual((root / skill).resolve(), (ROOT / "skills" / skill).resolve())

            removed = self._run("uninstall.sh", home)
            self.assertEqual(removed.returncode, 0, removed.stderr)
            self.assertFalse(launcher.exists())
            self.assertFalse(any((home / ".agents/skills").iterdir()))
            self.assertFalse(any((home / ".codex/skills").iterdir()))
            self.assertFalse(any((home / ".claude/skills").iterdir()))

    def test_install_is_idempotent_and_refuses_unrelated_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            first = self._run("install.sh", home, "--no-deps")
            self.assertEqual(first.returncode, 0, first.stderr)
            second = self._run("install.sh", home, "--no-deps")
            self.assertEqual(second.returncode, 0, second.stderr)

            target = home / ".codex/skills/agent-workflow-orchestrator"
            target.unlink()
            target.write_text("user-owned\n", encoding="utf-8")
            refused = self._run("install.sh", home, "--no-deps")
            self.assertEqual(refused.returncode, 2)
            self.assertIn("refusing to replace non-symlink path", refused.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), "user-owned\n")

    def test_uninstall_preserves_unrelated_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            launcher = home / ".local/bin/agent-workflow"
            launcher.parent.mkdir(parents=True)
            launcher.write_text("user-owned\n", encoding="utf-8")
            skill = home / ".agents/skills/delegated-implementation"
            skill.parent.mkdir(parents=True)
            skill.symlink_to(home / "unrelated-skill")

            result = self._run("uninstall.sh", home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(launcher.read_text(encoding="utf-8"), "user-owned\n")
            self.assertTrue(skill.is_symlink())
            self.assertIn("preserved unrelated path", result.stderr)
