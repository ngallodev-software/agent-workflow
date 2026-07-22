import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.sessions import kill, launch, restart
from agent_workflow.state import write_status
from agent_workflow.tmux import PaneInfo


class SessionLaunchTests(unittest.TestCase):
    def test_restart_preserves_structured_executor_and_prompt_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workdir = root / "worktree"
            workdir.mkdir()
            pack = root / "pack"
            prompt = pack / "prompts" / "ticket.md"
            prompt.parent.mkdir(parents=True)
            (pack / "pack.yaml").write_text("id: p\n", encoding="utf-8")
            prompt.write_text("task\n", encoding="utf-8")
            evaluation = pack / "evals" / "evaluation.json"
            evaluation.parent.mkdir()
            evaluation.write_text(
                json.dumps(
                    {
                        "schema": "agent-workflow/evaluation-plan/v1",
                        "dataset_split": "development",
                        "task_ids": ["P0-01"],
                        "repetitions": 1,
                        "timeout_seconds": 30,
                        "scorers": ["writable_scope"],
                        "sandbox": "docker",
                        "budgets": {"max_output_tokens": 100},
                        "scope": {"writable_trees": ["src/"]},
                    }
                ),
                encoding="utf-8",
            )
            settings = defaults(root / "missing.toml")
            settings = settings.__class__(
                **{**settings.__dict__, "state_root": root / "state"}
            )
            with (
                patch("agent_workflow.sessions.tmux.session_exists", return_value=False),
                patch("agent_workflow.sessions.tmux.create_session"),
                patch("agent_workflow.sessions.tmux.pane_info", return_value=None),
                patch("agent_workflow.sessions.executor_version", return_value="test"),
            ):
                launch(
                    settings,
                    session_id="structured",
                    workdir=workdir,
                    prompt_path=prompt,
                    executor="codex",
                    structured=True,
                    ticket_id="P0-01",
                    evaluation_path=evaluation,
                )
                retry = restart(settings, "structured", "structured-retry")

            command = json.loads(Path(retry["command_path"]).read_text(encoding="utf-8"))
            self.assertEqual(command["executor"], "codex")
            self.assertEqual(command["stream_format"], "codex-jsonl")
            self.assertEqual(retry["prompt_source"], str(prompt))
            self.assertEqual(retry["prompt_pack_root"], str(pack))
            retry_run = Path(retry["prompt_path"]).parent
            self.assertTrue((retry_run / "evaluation-runtime.json").is_file())
            provenance = json.loads(
                (retry_run / "run-provenance.json").read_text(encoding="utf-8")
            )
            self.assertEqual(provenance["budgets"]["max_output_tokens"], 100)

    def test_launch_prepares_durable_evidence_and_worktree_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workdir = root / "worktree"
            workdir.mkdir()
            prompt = root / "ticket.md"
            prompt.write_text("# Ticket\n", encoding="utf-8")
            settings = defaults(root / "missing-config.toml")
            settings = settings.__class__(
                **{
                    **settings.__dict__,
                    "state_root": root / "state",
                }
            )
            with (
                patch("agent_workflow.sessions.tmux.session_exists", return_value=False),
                patch("agent_workflow.sessions.tmux.create_session") as create_session,
                patch(
                    "agent_workflow.sessions.tmux.pane_info",
                    return_value=PaneInfo(pid=1234, dead=False, command="bash"),
                ),
            ):
                result = launch(
                    settings,
                    session_id="sample-p0-01",
                    workdir=workdir,
                    prompt_path=prompt,
                    explicit_command=["cat"],
                    ticket_id="P0-01",
                    pack_id="sample-pack",
                )
            run_dir = root / "state" / "runs" / "sample-p0-01"
            self.assertEqual(result["status"], "launched")
            self.assertTrue((run_dir / "prompt.md").is_file())
            self.assertTrue((run_dir / "source-baseline.json").is_file())
            self.assertTrue((run_dir / "completion.md").is_file())
            self.assertTrue((run_dir / "completion.json").is_file())
            self.assertTrue((run_dir / "run-provenance.json").is_file())
            self.assertTrue((run_dir / "executor-events.jsonl").is_file())
            self.assertEqual(
                (workdir / ".delegations" / "sample-p0-01").resolve(),
                run_dir.resolve(),
            )
            handoff = workdir / ".agent-workflow-handoff" / "sample-p0-01"
            self.assertTrue(handoff.is_dir())
            self.assertFalse(handoff.is_symlink())
            self.assertFalse(handoff.resolve().is_relative_to(run_dir.resolve()))
            self.assertEqual(result["handoff_dir"], str(handoff.resolve()))
            create_session.assert_called_once()

    def test_explicit_codex_launch_records_structured_executor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workdir = root / "worktree"
            workdir.mkdir()
            prompt = root / "ticket.md"
            prompt.write_text("# Ticket\n", encoding="utf-8")
            codex = root / "codex"
            codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            codex.chmod(0o755)
            settings = defaults(root / "missing-config.toml")
            settings = settings.__class__(
                **{**settings.__dict__, "state_root": root / "state"}
            )
            with (
                patch("agent_workflow.sessions.tmux.session_exists", return_value=False),
                patch("agent_workflow.sessions.tmux.create_session"),
                patch("agent_workflow.sessions.tmux.pane_info", return_value=None),
                patch("agent_workflow.sessions.executor_version", return_value="test"),
            ):
                result = launch(
                    settings,
                    session_id="explicit-codex",
                    workdir=workdir,
                    prompt_path=prompt,
                    explicit_command=[str(codex), "exec", "-"],
                    structured=True,
                )
            command = json.loads(Path(result["command_path"]).read_text(encoding="utf-8"))
            provenance = json.loads(
                (Path(result["command_path"]).parent / "run-provenance.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(command["executor"], "codex")
            self.assertEqual(command["stream_format"], "codex-jsonl")
            self.assertEqual(command["argv"], [str(codex), "exec", "--json", "-"])
            self.assertEqual(provenance["executor"], "codex")
            self.assertEqual(provenance["stream_format"], "codex-jsonl")

    def test_launch_process_receives_durable_task_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workdir = root / "worktree"
            workdir.mkdir()
            pack = root / "prompt-pack"
            prompt = pack / "prompts" / "ticket.md"
            prompt.parent.mkdir(parents=True)
            (pack / "pack.yaml").write_text("id: sample-pack\n", encoding="utf-8")
            prompt.write_text("# Original ticket\n", encoding="utf-8")
            result_path = root / "received.json"
            receiver = (
                "import json, os, pathlib, sys; "
                "handoff = pathlib.Path(os.environ['AGENT_WORKFLOW_HANDOFF_DIR']); "
                "handoff.joinpath('completion.json').write_text(json.dumps({"
                "'schema': 'agent-workflow/completion/v1', "
                "'session_id': os.environ['AGENT_WORKFLOW_SESSION_ID'], "
                "'ticket_id': None, 'pack_id': None, 'result': 'completed', "
                "'base_revision': None, 'head_revision': None, 'changed_files': [], "
                "'criteria': [], 'commands': [], 'unresolved': [], 'usage': None})); "
                f"pathlib.Path({str(result_path)!r}).write_text(json.dumps({{"
                "'session_id': os.environ['AGENT_WORKFLOW_SESSION_ID'], "
                "'prompt_source': os.environ['AGENT_WORKFLOW_PROMPT_SOURCE'], "
                "'pack_root': os.environ['AGENT_WORKFLOW_PROMPT_PACK_ROOT'], "
                "'handoff_dir': os.environ['AGENT_WORKFLOW_HANDOFF_DIR'], "
                "'stdin': sys.stdin.read()}, sort_keys=True))"
            )
            settings = defaults(root / "missing-config.toml")
            settings = settings.__class__(
                **{**settings.__dict__, "state_root": root / "state"}
            )
            with (
                patch("agent_workflow.sessions.tmux.session_exists", return_value=False),
                patch("agent_workflow.sessions.tmux.create_session") as create_session,
                patch("agent_workflow.sessions.tmux.pane_info", return_value=None),
            ):
                result = launch(
                    settings,
                    session_id="context-p0-01",
                    workdir=workdir,
                    prompt_path=prompt,
                    explicit_command=["python3", "-c", receiver],
                )
            runner = Path(create_session.call_args.args[2])
            subprocess.run([str(runner)], check=True, capture_output=True, text=True)
            received = json.loads(result_path.read_text(encoding="utf-8"))

            self.assertEqual(received["session_id"], "context-p0-01")
            self.assertEqual(received["prompt_source"], str(prompt))
            self.assertEqual(received["pack_root"], str(pack))
            self.assertEqual(received["handoff_dir"], result["handoff_dir"])
            self.assertTrue(Path(received["handoff_dir"]).is_dir())
            self.assertFalse(
                Path(received["handoff_dir"]).is_relative_to(
                    Path(result["completion_json_path"]).parent
                )
            )
            self.assertIn("session_id: `context-p0-01`", received["stdin"])
            self.assertIn("# Original ticket", received["stdin"])
            self.assertEqual(
                result["prompt_sha256"],
                hashlib.sha256(prompt.read_bytes()).hexdigest(),
            )
            self.assertTrue((Path(result["completion_json_path"])).is_file())
            final_status = json.loads(
                (Path(result["prompt_path"]).parent / "status.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(Path(final_status["final_receipt_path"]).is_file())
            self.assertEqual(final_status["completion_validation_status"], "valid")
            completion = json.loads(Path(result["completion_json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(completion["result"], "completed")

    def test_kill_preserves_terminal_durable_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = defaults(root / "missing-config.toml")
            settings = settings.__class__(
                **{**settings.__dict__, "state_root": root / "state"}
            )
            write_status(
                settings,
                "finished-p0-01",
                {"session_id": "finished-p0-01", "status": "completed", "exit_code": 0},
            )
            with patch("agent_workflow.sessions.tmux.session_exists", return_value=False):
                result = kill(settings, "finished-p0-01")

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["exit_code"], 0)
            self.assertNotIn("killed_by_operator", result)

    @unittest.skipUnless(shutil.which("git"), "git is required")
    def test_dirty_git_worktree_requires_explicit_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workdir = root / "worktree"
            workdir.mkdir()
            subprocess.run(["git", "init", "-q", str(workdir)], check=True)
            subprocess.run(
                ["git", "-C", str(workdir), "config", "user.email", "test@example.test"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(workdir), "config", "user.name", "Test"],
                check=True,
            )
            tracked = workdir / "tracked.txt"
            tracked.write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(workdir), "add", "tracked.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(workdir), "commit", "-qm", "initial"],
                check=True,
            )
            tracked.write_text("dirty\n", encoding="utf-8")
            prompt = root / "ticket.md"
            prompt.write_text("# Ticket\n", encoding="utf-8")
            settings = defaults(root / "missing-config.toml")
            settings = settings.__class__(
                **{**settings.__dict__, "state_root": root / "state"}
            )
            with patch(
                "agent_workflow.sessions.tmux.session_exists", return_value=False
            ):
                with self.assertRaisesRegex(WorkflowError, "worktree is dirty"):
                    launch(
                        settings,
                        session_id="dirty-p0-01",
                        workdir=workdir,
                        prompt_path=prompt,
                        explicit_command=["cat"],
                    )

            with (
                patch("agent_workflow.sessions.tmux.session_exists", return_value=False),
                patch("agent_workflow.sessions.tmux.create_session"),
                patch(
                    "agent_workflow.sessions.tmux.pane_info",
                    return_value=PaneInfo(pid=5678, dead=False, command="bash"),
                ),
            ):
                result = launch(
                    settings,
                    session_id="dirty-p0-01-allowed",
                    workdir=workdir,
                    prompt_path=prompt,
                    explicit_command=["cat"],
                    allow_dirty=True,
                )
            self.assertTrue(result["dirty_at_launch"])
