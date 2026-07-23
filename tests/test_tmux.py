import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agent_workflow.tmux import current_window_target, signal_waiters, wait_for_wakeup, wakeup_channel


class TmuxWakeupTests(unittest.TestCase):
    def test_channels_are_stable_and_do_not_disclose_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "one"
            second = Path(tmp) / "two"
            self.assertEqual(wakeup_channel(first), wakeup_channel(first / ".." / "one"))
            self.assertNotEqual(wakeup_channel(first), wakeup_channel(second))
            self.assertNotIn(str(first), wakeup_channel(first))

    def test_signal_is_best_effort(self):
        with patch("agent_workflow.tmux.run", side_effect=Exception("missing")):
            # Only WorkflowError is expected from the production wrapper.
            # A generic exception must still surface programming defects.
            with self.assertRaises(Exception):
                signal_waiters("channel")
        with patch("agent_workflow.tmux.run", side_effect=__import__("agent_workflow.errors", fromlist=["WorkflowError"]).WorkflowError("missing")):
            signal_waiters("channel")

    def test_wait_is_bounded_for_timeout_and_unavailable_tmux(self):
        process = Mock()
        process.wait.side_effect = [subprocess.TimeoutExpired(["tmux"], 0.1), 0]
        with patch("agent_workflow.tmux.subprocess.Popen", return_value=process):
            self.assertFalse(wait_for_wakeup("channel", 0.1))
        process.kill.assert_called_once()
        with patch("agent_workflow.tmux.subprocess.Popen", side_effect=OSError("missing")):
            self.assertFalse(wait_for_wakeup("channel", 0.1))

    def test_current_window_requires_tmux_environment_and_valid_response(self):
        with patch.dict("agent_workflow.tmux.os.environ", {}, clear=True):
            self.assertIsNone(current_window_target())
        result = Mock(returncode=0, stdout="parent:2\n")
        with patch.dict("agent_workflow.tmux.os.environ", {"TMUX": "socket"}, clear=True), patch("agent_workflow.tmux.run", return_value=result):
            self.assertEqual("parent:2", current_window_target())
