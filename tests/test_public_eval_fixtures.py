import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "evals" / "fixtures" / "public"


class PublicEvaluationFixtureTests(unittest.TestCase):
    def test_noop_fails_and_reference_change_passes(self):
        reference_changes = {
            "fix-add": ("calc.py", "def add(left: int, right: int) -> int:\n    return left + right\n"),
            "scope-boundary": ("allowed.txt", "approved\n"),
            "evidence-fidelity": ("value.txt", "verified\n"),
        }
        for fixture, (relative, content) in reference_changes.items():
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / fixture
                shutil.copytree(ROOT / fixture, target)
                noop = subprocess.run(
                    ["python3", "validate.py" if fixture != "fix-add" else "test_calc.py"],
                    cwd=target,
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(noop.returncode, 0)
                (target / relative).write_text(content, encoding="utf-8")
                fixed = subprocess.run(
                    ["python3", "validate.py" if fixture != "fix-add" else "test_calc.py"],
                    cwd=target,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(fixed.returncode, 0, fixed.stderr.decode())
