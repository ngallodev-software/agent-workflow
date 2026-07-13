import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.sessions import launch
from agent_workflow.tmux import PaneInfo


class SessionLaunchTests(unittest.TestCase):
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
            self.assertEqual(
                (workdir / ".delegations" / "sample-p0-01").resolve(),
                run_dir.resolve(),
            )
            create_session.assert_called_once()

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
