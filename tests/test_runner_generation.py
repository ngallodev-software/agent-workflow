import shutil
import tempfile
import unittest
import json
from pathlib import Path

from agent_workflow.runner import _capture_patch
from agent_workflow.sessions import _write_runner
from run_fixtures import write_run_contracts


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
    def test_missing_executor_fails_and_seals_evidence(self):
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            work = root / "work"
            state.mkdir()
            work.mkdir()
            write_run_contracts(state, session_id="missing-executor", include_final=False)
            runner = _write_runner(state, work, ["definitely-not-an-executor"])
            result = subprocess.run([str(runner)], check=False)
            status = json.loads((state / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(result.returncode, 127)
            self.assertEqual(status["status"], "failed")
            self.assertEqual(status["failure_category"], "command_not_found")
            self.assertTrue((state / "final-receipt.json").is_file())

    def test_patch_captures_committed_and_untracked_agent_changes(self):
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            state = root / "state"
            work.mkdir()
            state.mkdir()
            subprocess.run(["git", "init", "-q", str(work)], check=True)
            subprocess.run(["git", "-C", str(work), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(work), "config", "user.email", "test@example.test"], check=True)
            tracked = work / "tracked.txt"
            tracked.write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(work), "add", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(work), "commit", "-qm", "base"], check=True)
            base = subprocess.run(
                ["git", "-C", str(work), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            (state / "source-baseline.json").write_text(
                json.dumps({"components": {"primary": {"head": base}}}),
                encoding="utf-8",
            )
            tracked.write_text("committed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(work), "commit", "-qam", "agent"], check=True)
            (work / "new.txt").write_text("untracked\n", encoding="utf-8")
            patch_path = state / "patch.diff"
            _capture_patch(work, state, patch_path)
            content = patch_path.read_text(encoding="utf-8")
            self.assertIn("tracked.txt", content)
            self.assertIn("new.txt", content)

    def test_runner_enforces_timeout_and_seals_failure(self):
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            work = root / "work"
            state.mkdir()
            work.mkdir()
            write_run_contracts(state, session_id="timeout-test", include_final=False)
            (state / "evaluation-runtime.json").write_text(
                json.dumps(
                    {
                        "schema": "agent-workflow/evaluation-runtime/v1",
                        "timeout_seconds": 0.2,
                        "scope": {},
                        "acceptance_commands": [],
                    }
                ),
                encoding="utf-8",
            )
            runner = _write_runner(
                state,
                work,
                ["python3", "-c", "import time; time.sleep(10)"],
            )
            result = subprocess.run([str(runner)], check=False)
            status = json.loads((state / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(result.returncode, 124)
            self.assertEqual(status["status"], "failed")
            self.assertEqual(status["failure_category"], "timeout")
            self.assertTrue((state / "final-receipt.json").is_file())

    def test_runner_enforces_reported_token_and_cost_budgets(self):
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            work = root / "work"
            state.mkdir()
            work.mkdir()
            write_run_contracts(state, session_id="budget-test", include_final=False)
            provenance_path = state / "run-provenance.json"
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            provenance["budgets"] = {
                "max_output_tokens": 1,
                "max_cost": 0.1,
                "currency": "USD",
            }
            provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
            event = json.dumps(
                {
                    "usage": {
                        "output_tokens": 2,
                        "cost": 0.2,
                        "currency": "USD",
                    }
                }
            )
            runner = _write_runner(
                state,
                work,
                ["python3", "-c", f"print({event!r})"],
                stream_format="codex-jsonl",
            )
            result = subprocess.run([str(runner)], check=False)
            status = json.loads((state / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(result.returncode, 1)
            self.assertEqual(status["failure_category"], "budget_exhausted")
            self.assertEqual(len(status["budget_exceeded"]), 2)

    def test_runner_records_success_and_log(self):
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            work = root / "work"
            state.mkdir()
            work.mkdir()
            write_run_contracts(state, session_id="runner-test", include_final=False)
            (state / "prompt.md").write_text("hello prompt\n", encoding="utf-8")
            (state / "launch-prompt.md").write_text("hello prompt\n", encoding="utf-8")
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
