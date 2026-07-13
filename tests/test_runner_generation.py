import shutil
import tempfile
import unittest
from pathlib import Path

from agent_workflow.sessions import _write_runner


@unittest.skipUnless(shutil.which("bash"), "bash is required")
class RunnerTests(unittest.TestCase):
    def test_runner_is_syntax_valid_and_quotes_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            work = root / "work dir"
            state.mkdir()
            work.mkdir()
            (state / "prompt.md").write_text("prompt\n", encoding="utf-8")
            (state / "output.log").touch()
            (state / "status.json").write_text("{}\n", encoding="utf-8")
            runner = _write_runner(
                state, work, ["printf", "%s", "hello world"]
            )
            self.assertIn(
                "'hello world'", runner.read_text(encoding="utf-8")
            )

class RunnerExecutionTests(unittest.TestCase):
    def test_runner_records_success_and_log(self):
        import json
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            work = root / "work"
            state.mkdir()
            work.mkdir()
            (state / "prompt.md").write_text("hello prompt\n", encoding="utf-8")
            (state / "output.log").touch()
            (state / "status.json").write_text(
                '{"status": "launched"}\n', encoding="utf-8"
            )
            runner = _write_runner(
                state,
                work,
                [
                    "python3",
                    "-c",
                    "import sys; print(sys.stdin.read().strip())",
                ],
            )
            result = subprocess.run([str(runner)], check=False)
            self.assertEqual(result.returncode, 0)
            status = json.loads((state / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "completed")
            self.assertEqual(status["exit_code"], 0)
            self.assertIn(
                "hello prompt",
                (state / "output.log").read_text(encoding="utf-8"),
            )
