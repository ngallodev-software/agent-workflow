import shutil
import tempfile
import unittest
import json
from pathlib import Path

from agent_workflow.eval.scoring import score_trial
from agent_workflow.util import sha256_file
from agent_workflow.runner import MAX_COMPLETION_HANDOFF_BYTES, _capture_patch, _collect_completion
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
    def test_native_job_post_receipts_report_scope_and_command_failures(self):
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, work = root / "state", root / "work"
            state.mkdir()
            work.mkdir()
            write_run_contracts(state, session_id="native-post", include_final=False)
            handoff = work / ".agent-workflow-handoff" / "native-post"
            handoff.mkdir(parents=True)
            status_path = state / "status.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status["handoff_dir"] = str(handoff)
            status_path.write_text(json.dumps(status), encoding="utf-8")
            (state / "evaluation-runtime.json").write_text(
                json.dumps(
                    {
                        "schema": "agent-workflow/evaluation-runtime/v1",
                        "acceptance_commands": [
                            {"id": "reject", "argv": ["python3", "-c", "raise SystemExit(1)"]}
                        ],
                        "scope": {
                            "writable_paths": ["allowed.txt"],
                            "disposable_trees": [".agent-workflow-handoff/"],
                        },
                        "scorers": [],
                        "native_job_binding_sha256": "bound",
                    }
                ),
                encoding="utf-8",
            )
            from agent_workflow.eval.scope import ScopePolicy, collect_scope

            collect_scope(
                work,
                phase="baseline",
                policy=ScopePolicy(work, writable_paths=("allowed.txt",), disposable_trees=(".agent-workflow-handoff/",)),
                receipt_dir=state / "scope",
            )
            writer = (
                "import json, os, pathlib; pathlib.Path('outside.txt').write_text('no'); "
                "p=pathlib.Path(os.environ['AGENT_WORKFLOW_HANDOFF_DIR']); "
                "p.joinpath('completion.json').write_text(json.dumps({'schema':'agent-workflow/completion/v1',"
                "'session_id':'native-post','ticket_id':None,'pack_id':None,'result':'completed',"
                "'base_revision':None,'head_revision':None,'changed_files':[],'criteria':[],'commands':[],"
                "'unresolved':[],'usage':None}))"
            )
            runner = _write_runner(state, work, ["python3", "-c", writer], handoff_dir=handoff)
            self.assertEqual(subprocess.run([str(runner)], check=False).returncode, 0)
            post = json.loads((state / "collections" / "commands-post.json").read_text(encoding="utf-8"))
            self.assertEqual(post["commands"][0]["exit_code"], 1)
            scope = json.loads((state / "scope" / "scope-post.json").read_text(encoding="utf-8"))
            self.assertEqual(scope["policy"]["writable_paths"], ["allowed.txt"])
            scores = score_trial(
                state,
                output_dir=state / "scores",
                expected_final_receipt_sha256=sha256_file(state / "final-receipt.json"),
            )
            by_id = {item["scorer"]["id"]: item["verdict"] for item in scores["scores"]}
            self.assertEqual(by_id["acceptance_commands"], "fail")
            self.assertEqual(by_id["writable_scope"], "fail")

    def test_runner_collects_valid_handoff_before_seal(self):
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, work = root / "state", root / "work"
            state.mkdir()
            work.mkdir()
            write_run_contracts(state, session_id="handoff-valid", include_final=False)
            handoff = work / ".agent-workflow-handoff" / "handoff-valid"
            handoff.mkdir(parents=True)
            status_path = state / "status.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status["handoff_dir"] = str(handoff)
            status_path.write_text(json.dumps(status), encoding="utf-8")
            writer = (
                "import json, os, pathlib; p=pathlib.Path(os.environ['AGENT_WORKFLOW_HANDOFF_DIR']); "
                "p.joinpath('completion.json').write_text(json.dumps({'schema':'agent-workflow/completion/v1',"
                "'session_id':'handoff-valid','ticket_id':None,'pack_id':None,'result':'completed',"
                "'base_revision':None,'head_revision':None,'changed_files':[],'criteria':[],'commands':[],"
                "'unresolved':[],'usage':None}))"
            )
            runner = _write_runner(
                state, work, ["python3", "-c", writer], handoff_dir=handoff
            )
            self.assertNotIn("AGENT_WORKFLOW_PROVENANCE_PATH", runner.read_text(encoding="utf-8"))
            self.assertEqual(subprocess.run([str(runner)], check=False).returncode, 0)
            completion = json.loads((state / "completion.json").read_text(encoding="utf-8"))
            collection = json.loads((state / "collections" / "completion.json").read_text(encoding="utf-8"))
            self.assertEqual(completion["result"], "completed")
            self.assertEqual(collection["validation_status"], "valid")
            self.assertEqual(collection["adapter_version"], "1")
            self.assertEqual(collection["canonical_mapping"], "identity")
            self.assertEqual(collection["canonical_sha256"], collection["source_sha256"])
            final = json.loads((state / "final-receipt.json").read_text(encoding="utf-8"))
            self.assertIn("collections/completion.json", {item["path"] for item in final["artifacts"]})

    def test_invalid_handoff_preserves_placeholder_and_seals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, work = root / "state", root / "work"
            state.mkdir()
            work.mkdir()
            write_run_contracts(state, session_id="handoff-invalid", include_final=False)
            handoff = work / ".agent-workflow-handoff" / "handoff-invalid"
            handoff.mkdir(parents=True)
            (handoff / "completion.json").symlink_to(work / "outside.json")
            status_path = state / "status.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status["handoff_dir"] = str(handoff)
            status_path.write_text(json.dumps(status), encoding="utf-8")
            collection = _collect_completion(state, work)
            self.assertEqual(collection["validation_status"], "invalid")
            self.assertEqual(
                json.loads((state / "completion.json").read_text(encoding="utf-8"))["result"],
                "blocked",
            )

    def test_oversized_handoff_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, work = root / "state", root / "work"
            state.mkdir()
            work.mkdir()
            write_run_contracts(state, session_id="handoff-large", include_final=False)
            handoff = work / ".agent-workflow-handoff" / "handoff-large"
            handoff.mkdir(parents=True)
            (handoff / "completion.json").write_bytes(b"x" * (MAX_COMPLETION_HANDOFF_BYTES + 1))
            status_path = state / "status.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status["handoff_dir"] = str(handoff)
            status_path.write_text(json.dumps(status), encoding="utf-8")
            self.assertEqual(_collect_completion(state, work)["validation_status"], "invalid")

    def test_missing_malformed_and_escaping_handoffs_seal_with_receipts(self):
        import subprocess

        cases = (("missing", "missing"), ("malformed", "invalid"), ("escape", "invalid"))
        for name, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                state, work = root / "state", root / "work"
                state.mkdir()
                work.mkdir()
                session_id = f"handoff-{name}"
                write_run_contracts(state, session_id=session_id, include_final=False)
                handoff = work / ".agent-workflow-handoff" / session_id
                handoff.mkdir(parents=True)
                if name == "malformed":
                    (handoff / "completion.json").write_text("{not json", encoding="utf-8")
                if name == "escape":
                    handoff = state
                status_path = state / "status.json"
                status = json.loads(status_path.read_text(encoding="utf-8"))
                status["handoff_dir"] = str(handoff)
                status_path.write_text(json.dumps(status), encoding="utf-8")
                runner = _write_runner(state, work, ["true"])
                self.assertEqual(subprocess.run([str(runner)], check=False).returncode, 0)
                collection = json.loads(
                    (state / "collections" / "completion.json").read_text(encoding="utf-8")
                )
                self.assertEqual(collection["validation_status"], expected)
                self.assertIsNone(collection["canonical_mapping"])
                self.assertIsNone(collection["canonical_sha256"])
                completion = json.loads((state / "completion.json").read_text(encoding="utf-8"))
                self.assertEqual(completion["result"], "blocked")
                self.assertTrue((state / "final-receipt.json").is_file())

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
