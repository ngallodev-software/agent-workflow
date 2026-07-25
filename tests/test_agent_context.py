from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_workflow.agent_context import (
    auto_reuse,
    candidates,
    complete_task,
    initialize,
    read,
    request_reuse,
)
from agent_workflow.config import defaults
from agent_workflow.sessions import acknowledge
from agent_workflow.state import run_dir, write_status


class AgentContextTests(unittest.TestCase):
    def _run(self, root: Path, *, ticket: str = "T-1", interactive: bool = True):
        settings = defaults(root / "missing.toml")
        settings = settings.__class__(
            **{**settings.__dict__, "state_root": root / "state", "reuse_stale_minutes": 120}
        )
        worktree = root / "worktree"
        worktree.mkdir(exist_ok=True)
        state_dir = run_dir(settings, "run-1")
        state_dir.mkdir(parents=True, exist_ok=True)
        prompt = state_dir / "prompt.md"
        prompt.write_text("task one", encoding="utf-8")
        status = {
            "schema": "agent-workflow/session-status/v2",
            "session_id": "run-1",
            "ticket_id": ticket,
            "pack_id": "pack-1",
            "retry_of": None,
            "agent_name": "curly",
            "agent_class": "implementation",
            "executor": "codex",
            "status": "running",
            "created_at": "2026-07-24T00:00:00+00:00",
            "workdir": str(worktree),
            "prompt_path": str(prompt),
            "prompt_sha256": "0" * 64,
            "log_path": str(state_dir / "output.log"),
            "repository_root": str(worktree),
            "source_revision": "abc",
            "tmux_session": "host",
            "tmux_target": "host:0.1",
        }
        write_status(settings, "run-1", status)
        initialize(
            state_dir,
            session_id="run-1",
            status=status,
            command={"interactive": interactive, "model": "gpt-5.4-mini"},
        )
        return settings, worktree, state_dir

    @patch("agent_workflow.agent_context.tmux.pane_info", return_value=object())
    @patch("agent_workflow.agent_context.tmux.session_exists", return_value=True)
    def test_completion_is_required_before_candidate_and_cross_worktree_is_rejected(
        self, _exists, _pane
    ):
        with tempfile.TemporaryDirectory() as tmp:
            settings, worktree, _ = self._run(Path(tmp))
            self.assertFalse(candidates(settings, workdir=worktree)[0]["eligible"])
            context = complete_task(
                settings, "run-1", actor="curly", summary="Implemented parser",
                tags=["parser"], files=["src/parser.py"],
            )
            self.assertEqual(context["state"], "idle_reusable")
            same = candidates(settings, workdir=worktree, ticket_id="T-1", tags=["parser"])[0]
            self.assertTrue(same["eligible"])
            self.assertTrue(same["auto_reuse_eligible"])
            other = Path(tmp) / "other"
            other.mkdir()
            cross = candidates(settings, workdir=other, ticket_id="T-1")[0]
            self.assertFalse(cross["eligible"])
            self.assertIn("different_worktree", cross["reasons"])

    @patch("agent_workflow.agent_context.tmux.pane_info", return_value=object())
    @patch("agent_workflow.agent_context.tmux.session_exists", return_value=True)
    def test_reuse_waits_for_correlated_ack(self, _exists, _pane):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings, worktree, _ = self._run(root)
            complete_task(settings, "run-1", actor="curly", summary="Done")
            prompt = root / "second.md"
            prompt.write_text("task two", encoding="utf-8")
            pending = request_reuse(
                settings, "run-1", prompt_path=prompt, actor="orchestrator",
                ticket_id="T-1", pack_id="pack-1", automatic=True,
            )
            self.assertEqual(read(settings, "run-1")["state"], "reuse_pending")
            acknowledge(
                settings, "run-1", actor="curly", content="accepted",
                correlation_id=pending["message"]["message_id"],
            )
            context = read(settings, "run-1")
            self.assertEqual(context["state"], "busy")
            self.assertEqual(context["reuse_count"], 1)

    @patch("agent_workflow.agent_context.tmux.pane_info", return_value=object())
    @patch("agent_workflow.agent_context.tmux.session_exists", return_value=True)
    def test_auto_reuse_refuses_similarity_without_exact_lineage(self, _exists, _pane):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings, worktree, _ = self._run(root)
            complete_task(
                settings, "run-1", actor="curly", summary="Parser work", tags=["parser"]
            )
            prompt = root / "next.md"
            prompt.write_text("similar task", encoding="utf-8")
            result = auto_reuse(
                settings, workdir=worktree, prompt_path=prompt,
                actor="orchestrator", ticket_id="T-2", pack_id="pack-1",
                retry_of=None, agent_class="implementation", tags=["parser"],
            )
            self.assertEqual(result["action"], "launch")
            self.assertFalse(result["candidates"][0]["auto_reuse_eligible"])

    @patch("agent_workflow.agent_context.tmux.pane_info", return_value=object())
    @patch("agent_workflow.agent_context.tmux.session_exists", return_value=True)
    def test_stale_idle_agent_is_not_eligible(self, _exists, _pane):
        with tempfile.TemporaryDirectory() as tmp:
            settings, worktree, state_dir = self._run(Path(tmp))
            complete_task(settings, "run-1", actor="curly", summary="Done")
            path = state_dir / "agent-context.json"
            context = json.loads(path.read_text(encoding="utf-8"))
            context["completed_assignments"][-1]["completed_at"] = "2000-01-01T00:00:00+00:00"
            path.write_text(json.dumps(context), encoding="utf-8")
            candidate = candidates(settings, workdir=worktree, ticket_id="T-1")[0]
            self.assertFalse(candidate["eligible"])
            self.assertIn("idle_stale", candidate["reasons"])


if __name__ == "__main__":
    unittest.main()
