import json
import tempfile
import unittest
from pathlib import Path

from agent_workflow.errors import WorkflowError
from agent_workflow.config import defaults
from agent_workflow.messages import (
    MAX_CONTENT_CHARS,
    MESSAGE_SCHEMA,
    append_message,
    replay_messages,
    wait_for_messages,
)
from agent_workflow.sessions import acknowledge, progress, steer, wait_for_message
from agent_workflow.state import write_status


class MessageLogTests(unittest.TestCase):
    def test_append_and_replay_after_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            first = append_message(
                run_dir,
                session_id="run-1",
                direction="parent_to_child",
                kind="steer",
                actor="parent",
                content="Please inspect the tests.",
            )
            second = append_message(
                run_dir,
                session_id="run-1",
                direction="child_to_parent",
                kind="progress",
                actor="child",
                content="I am inspecting them.",
                correlation_id=first["message_id"],
            )
            self.assertEqual([first, second], replay_messages(run_dir))
            self.assertEqual([second], replay_messages(run_dir, after_sequence=1))
            self.assertEqual(MESSAGE_SCHEMA, second["schema"])

    def test_sequence_is_contiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            sequences = [
                append_message(
                    run_dir,
                    session_id="run",
                    direction="parent_to_child",
                    kind="ack",
                    actor="parent",
                    content=str(index),
                )["sequence"]
                for index in range(3)
            ]
            self.assertEqual([1, 2, 3], sequences)

    def test_rejects_invalid_message_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            base = dict(
                session_id="run",
                direction="parent_to_child",
                kind="steer",
                actor="parent",
                content="ok",
            )
            for update in (
                {"session_id": "../unsafe"},
                {"actor": ""},
                {"direction": "sideways"},
                {"kind": "notice"},
                {"content": ""},
                {"content": "x" * (MAX_CONTENT_CHARS + 1)},
                {"correlation_id": "not-a-uuid"},
            ):
                with self.subTest(update=update), self.assertRaises(WorkflowError):
                    append_message(run_dir, **(base | update))

    def test_rejects_malformed_or_noncontiguous_existing_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            path = run_dir / "messages.jsonl"
            path.write_text("not json\n", encoding="utf-8")
            with self.assertRaises(WorkflowError):
                replay_messages(run_dir)
            path.write_text(
                json.dumps({"schema": "agent-workflow/session-message/v0"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(WorkflowError):
                replay_messages(run_dir)
            path.write_text(
                json.dumps(
                    {
                        "schema": MESSAGE_SCHEMA,
                        "sequence": 2,
                        "message_id": "2a9d57d7-9a95-4acd-a3e8-8f27a84b985e",
                        "session_id": "run",
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "direction": "parent_to_child",
                        "kind": "steer",
                        "actor": "parent",
                        "content": "bad sequence",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(WorkflowError):
                append_message(
                    run_dir,
                    session_id="run",
                    direction="parent_to_child",
                    kind="steer",
                    actor="parent",
                    content="will not append",
                )

    def test_session_controls_are_durable_and_terminal_runs_reject_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = defaults(root / "missing.toml")
            settings = settings.__class__(
                **{**settings.__dict__, "state_root": root / "state"}
            )
            write_status(settings, "run-1", {"session_id": "run-1", "status": "launched"})
            request = steer(settings, "run-1", actor="parent", content="check tests")
            update = progress(settings, "run-1", actor="child", content="checking")
            receipt = acknowledge(
                settings,
                "run-1",
                actor="child",
                content="applied",
                correlation_id=request["message_id"],
            )
            self.assertEqual([request, update, receipt], wait_for_message(settings, "run-1"))
            self.assertEqual(
                [],
                wait_for_messages(
                    root / "state" / "runs" / "run-1",
                    after_sequence=receipt["sequence"],
                    timeout_seconds=0,
                ),
            )
            write_status(settings, "run-done", {"session_id": "run-done", "status": "completed"})
            with self.assertRaisesRegex(WorkflowError, "terminal session"):
                steer(settings, "run-done", actor="parent", content="too late")
