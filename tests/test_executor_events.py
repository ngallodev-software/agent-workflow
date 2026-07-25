import unittest

from agent_workflow.config import defaults
from agent_workflow.executors import accumulate_usage, event_text, event_usage, prepare_executor


class ExecutorEventTests(unittest.TestCase):
    def test_known_executors_enable_structured_streams(self):
        settings = defaults()
        codex = prepare_executor(settings, "codex", None, structured=True)
        claude = prepare_executor(settings, "claude", None, structured=True)

        self.assertEqual(codex.stream_format, "codex-jsonl")
        self.assertIn("--json", codex.argv)
        self.assertIn("gpt-5.4-mini", codex.argv)
        self.assertNotIn("--ask-for-approval", codex.argv)
        self.assertEqual(claude.stream_format, "claude-stream-json")
        self.assertIn("--verbose", claude.argv)
        self.assertIn("manual", claude.argv)
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

    def test_unknown_explicit_commands_remain_unmodified(self):
        plan = prepare_executor(defaults(), None, ["cat"], structured=True)
        self.assertEqual(plan.name, None)
        self.assertEqual(plan.argv, ("cat",))
        self.assertEqual(plan.stream_format, "text")

    def test_interactive_known_executors_use_the_tui_entrypoint(self):
        codex = prepare_executor(defaults(), "codex", None, interactive=True)
        claude = prepare_executor(defaults(), "claude", None, interactive=True)
        self.assertEqual(codex.argv, ("codex", "--ask-for-approval", "on-request", "--model", "gpt-5.4-mini"))
        self.assertEqual(claude.argv, ("claude", "--permission-mode", "manual", "--model", "sonnet"))
        with self.assertRaisesRegex(Exception, "mutually exclusive"):
            prepare_executor(defaults(), "claude", None, structured=True, interactive=True)

    def test_non_interactive_permissions_use_subcommand_specific_flags(self):
        codex = prepare_executor(defaults(), "codex", None)
        claude = prepare_executor(defaults(), "claude", None)
        self.assertNotIn("--ask-for-approval", codex.argv)
        self.assertIn("--permission-mode", claude.argv)

    def test_no_go_models_require_explicit_recorded_authorization(self):
        with self.assertRaisesRegex(Exception, "no-go"):
            prepare_executor(defaults(), "codex", None, model="gpt-5.6-sol")
        plan = prepare_executor(
            defaults(), "codex", None, model="gpt-5.6-sol", allow_no_go_model=True
        )
        self.assertEqual(plan.model, "gpt-5.6-sol")
        self.assertTrue(plan.no_go_authorized)
        with self.assertRaisesRegex(Exception, "no-go"):
            prepare_executor(defaults(), "claude", None, model="fable")

    def test_executor_rejects_models_not_in_its_allowlist(self):
        with self.assertRaisesRegex(Exception, "not allowed"):
            prepare_executor(defaults(), "claude", None, model="gpt-5.4-mini")

    def test_explicit_usage_modes_do_not_double_count_terminal_total(self):
        usage = accumulate_usage(None, {"input_tokens": 3, "output_tokens": 2}, mode="delta")
        usage = accumulate_usage(usage, {"input_tokens": 4, "output_tokens": 5}, mode="delta")
        usage = accumulate_usage(usage, {"input_tokens": 7, "output_tokens": 7}, mode="terminal")
        self.assertEqual(usage["input_tokens"], 7)
        self.assertEqual(usage["output_tokens"], 7)

    def test_explicit_known_executors_preserve_structured_format(self):
        codex = prepare_executor(
            defaults(), None, ["/usr/local/bin/codex", "exec", "-"], structured=True
        )
        claude = prepare_executor(
            defaults(), None, ["claude", "--print"], structured=True
        )

        self.assertEqual(codex.name, "codex")
        self.assertEqual(codex.argv, ("/usr/local/bin/codex", "exec", "--model", "gpt-5.4-mini", "--json", "-"))
        self.assertEqual(codex.stream_format, "codex-jsonl")
        self.assertEqual(claude.name, "claude")
        self.assertEqual(
            claude.argv,
            ("claude", "--print", "--model", "sonnet", "--verbose", "--output-format", "stream-json"),
        )
        self.assertEqual(claude.stream_format, "claude-stream-json")
