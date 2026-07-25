import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agent_workflow.errors import WorkflowError
from agent_workflow.tmux import (
    configure_server,
    current_window_target,
    signal_waiters,
    split_window,
    ensure_interactive_capacity,
    wait_for_wakeup,
    wakeup_channel,
)


class TmuxWakeupTests(unittest.TestCase):
    def test_configure_server_enables_mouse(self):
        with patch("agent_workflow.tmux.ensure_tmux"), patch("agent_workflow.tmux.run") as run:
            configure_server(mouse=True)
        self.assertEqual(run.call_args_list[0].args[0], ["tmux", "set-option", "-g", "mouse", "on"])
        self.assertEqual(run.call_args_list[1].args[0][-2:], ["pane-border-status", "top"])

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

    def test_split_window_requests_right_side_pane(self):
        listing = Mock(returncode=0, stdout="%1\t\t0\t0\t0\t\n")
        created = Mock(returncode=0, stdout="parent:2.4\n")
        ok = Mock(returncode=0, stdout="")
        with patch.dict("agent_workflow.tmux.os.environ", {"TMUX_PANE": "%1"}, clear=True), patch(
            "agent_workflow.tmux.run", side_effect=[listing, ok, created, ok, ok, ok, ok, ok]
        ) as run:
            self.assertEqual("parent:2.4", split_window("parent:2", "/tmp/work", "/tmp/runner"))
        self.assertEqual(
            run.call_args_list[2].args[0],
            [
                "tmux",
                "split-window",
                "-h",
                "-d",
                "-P",
                "-F",
                "#{session_name}:#{window_index}.#{pane_index}",
                "-t",
                "%1",
                "-c",
                "/tmp/work",
                "/tmp/runner",
            ],
        )
        self.assertEqual(
            run.call_args_list[3].args[0],
            ["tmux", "set-option", "-p", "-t", "parent:2.4", "remain-on-exit", "on"],
        )
        self.assertEqual(
            run.call_args_list[5].args[0],
            ["tmux", "set-option", "-p", "-t", "parent:2.4", "@agent-workflow-column", "1"],
        )

    def test_agent_columns_are_created_horizontally_before_vertical_splits(self):
        listing = Mock(returncode=0, stdout="%1\torchestrator\t0\t0\t0\t\n%2\tagent\t80\t0\t0\t1\n")
        created = Mock(returncode=0, stdout="parent:2.5\n")
        ok = Mock(returncode=0, stdout="")
        with patch("agent_workflow.tmux.run", side_effect=[listing, created, ok, ok, ok, ok, ok]) as run:
            split_window("parent:2", "/tmp/work", "/tmp/runner")
        command = run.call_args_list[1].args[0]
        self.assertEqual(command[2], "-h")
        self.assertEqual(command[command.index("-t") + 1], "%2")

    def test_vertical_splits_balance_across_full_width(self):
        listing = Mock(
            returncode=0,
            stdout=(
                "%1\torchestrator\t0\t0\t0\t\n"
                "%2\tagent\t60\t0\t0\t1\n"
                "%4\tagent\t60\t20\t0\t1\n"
                "%3\tagent\t100\t0\t0\t2\n"
            ),
        )
        created = Mock(returncode=0, stdout="parent:2.6\n")
        ok = Mock(returncode=0, stdout="")
        with patch("agent_workflow.tmux.run", side_effect=[listing, created, ok, ok, ok, ok, ok]) as run:
            split_window("parent:2", "/tmp/work", "/tmp/runner")
        command = run.call_args_list[1].args[0]
        self.assertEqual(command[2], "-v")
        self.assertEqual(command[command.index("-t") + 1], "%3")

    def test_unlimited_shared_noninteractive_launch_stacks_vertically(self):
        listing = Mock(
            returncode=0,
            stdout=(
                "%1\torchestrator\t0\t0\t0\t\n"
                "%2\tagent\t80\t0\t0\t1\n"
            ),
        )
        created = Mock(returncode=0, stdout="parent:2.5\n")
        ok = Mock(returncode=0, stdout="")
        with patch("agent_workflow.tmux.run", side_effect=[listing, created, ok, ok, ok, ok, ok]) as run:
            split_window(
                "parent:2", "/tmp/work", "/tmp/runner",
                max_interactive_agent_panes=None,
                max_interactive_agent_width=None,
                max_interactive_agent_vertical=None,
            )
        command = run.call_args_list[1].args[0]
        self.assertEqual(command[2], "-v")
        self.assertEqual(command[command.index("-t") + 1], "%2")

    def test_unmarked_live_right_pane_is_adopted_and_dead_panes_are_ignored(self):
        listing = Mock(
            returncode=0,
            stdout=(
                "%1\t\t0\t0\t0\t\n"
                "%2\tagent\t60\t0\t1\t1\n"
                "%4\t\t105\t0\t0\t\n"
            ),
        )
        created = Mock(returncode=0, stdout="parent:2.5\n")
        ok = Mock(returncode=0, stdout="")
        with patch.dict("agent_workflow.tmux.os.environ", {"TMUX_PANE": "%1"}, clear=True), patch(
            "agent_workflow.tmux.run", side_effect=[listing, created, ok, ok, ok, ok, ok]
        ) as run:
            split_window("parent:2", "/tmp/work", "/tmp/runner")
        command = run.call_args_list[1].args[0]
        self.assertEqual(command[2], "-h")
        self.assertEqual(command[command.index("-t") + 1], "%4")

    def test_interactive_agent_pane_limit_is_enforced_before_split(self):
        listing = Mock(
            returncode=0,
            stdout=(
                "%1\torchestrator\t0\t0\t0\t\n"
                "%2\tagent\t60\t0\t0\t1\n"
                "%3\tagent\t60\t10\t0\t1\n"
                "%4\tagent\t60\t20\t0\t1\n"
                "%5\tagent\t100\t0\t0\t2\n"
                "%6\tagent\t100\t10\t0\t2\n"
                "%7\tagent\t100\t20\t0\t2\n"
            ),
        )
        with patch.dict("agent_workflow.tmux.os.environ", {"TMUX_PANE": "%1"}, clear=True), patch(
            "agent_workflow.tmux.run", return_value=listing
        ) as run, self.assertRaisesRegex(WorkflowError, "pane limit reached: 6/6"):
            split_window("parent:2", "/tmp/work", "/tmp/runner")
        self.assertEqual(run.call_count, 1)

    def test_capacity_preflight_counts_live_non_orchestrator_panes(self):
        listing = Mock(
            returncode=0,
            stdout=(
                "%1\torchestrator\t0\n"
                "%2\tagent\t0\n"
                "%3\tagent\t0\n"
                "%4\tagent\t0\n"
                "%5\tagent\t1\n"
            ),
        )
        with patch("agent_workflow.tmux.run", return_value=listing), self.assertRaisesRegex(
            WorkflowError, "pane limit reached: 3/3"
        ):
            ensure_interactive_capacity("parent:2", 3)
