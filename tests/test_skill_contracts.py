from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


class SkillContractTests(unittest.TestCase):
    def test_all_workflow_skills_have_metadata_and_orchestrator_link(self) -> None:
        expected = {
            "agent-workflow-orchestrator",
            "delegated-implementation",
            "phase-gate-review",
            "prompt-pack-builder",
        }
        self.assertEqual({p.parent.name for p in SKILLS.glob("*/SKILL.md")}, expected)
        for name in expected:
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertRegex(text, rf"(?m)^name: {re.escape(name)}$")
            self.assertRegex(text, r"(?m)^description: .+$")
            if name != "agent-workflow-orchestrator":
                self.assertIn("agent-workflow-orchestrator", text)

    def test_orchestrator_preserves_canonical_lifecycle_claims(self) -> None:
        text = (SKILLS / "agent-workflow-orchestrator" / "SKILL.md").read_text(encoding="utf-8")
        for command in (
            "agent-workflow doctor",
            "agent-workflow pack validate",
            "agent-workflow worktree create",
            "agent-workflow launch",
            "agent-workflow status",
            "agent-workflow watch",
            "agent-workflow steer",
            "agent-workflow progress",
            "agent-workflow ack",
            "agent-workflow interrupt",
            "agent-workflow terminate",
            "agent-workflow review",
            "agent-workflow accept",
        ):
            self.assertIn(command, text)
        self.assertIn("visible pane", text)
        self.assertIn("detached named session", text)
        self.assertIn("host-native subagent is not", text)
        self.assertNotIn("tmux new-session", text)
        self.assertNotIn("tmux split-window", text)
