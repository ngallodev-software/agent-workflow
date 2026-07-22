import unittest

from agent_workflow.config import defaults
from agent_workflow.executors import event_text, event_usage, prepare_executor


class ExecutorEventTests(unittest.TestCase):
    def test_known_executors_enable_structured_streams(self):
        settings = defaults()
        codex = prepare_executor(settings, "codex", None, structured=True)
        claude = prepare_executor(settings, "claude", None, structured=True)

        self.assertEqual(codex.stream_format, "codex-jsonl")
        self.assertIn("--json", codex.argv)
        self.assertEqual(claude.stream_format, "claude-stream-json")
        self.assertIn("--verbose", claude.argv)
        self.assertEqual(claude.argv[-2:], ("--output-format", "stream-json"))

    def test_event_adapters_extract_text_and_usage(self):
        codex = {
            "item": {"type": "agent_message", "text": "done"},
            "usage": {"input_tokens": 3, "output_tokens": 2},
        }
        claude = {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "ok"}]},
        }

        self.assertEqual(event_text(codex, "codex-jsonl"), ["done"])
        self.assertEqual(event_usage(codex), codex["usage"])
        self.assertEqual(event_text(claude, "claude-stream-json"), ["ok"])

    def test_explicit_commands_remain_unmodified(self):
        plan = prepare_executor(defaults(), None, ["cat"], structured=True)
        self.assertEqual(plan.argv, ("cat",))
        self.assertEqual(plan.stream_format, "text")
