from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from agent_workflow.provider_evidence import build_provider_evidence


class ProviderEvidenceTests(unittest.TestCase):
    def _build(self, events: list[dict], stream_format: str = "codex-jsonl"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "executor-events.jsonl"
            path.write_text("".join(json.dumps(item) + "\n" for item in events), encoding="utf-8")
            return build_provider_evidence(
                events_path=path,
                stream_format=stream_format,
                executor="codex" if stream_format == "codex-jsonl" else "claude",
                session_id="evidence-test",
            )

    def test_terminal_replaces_deltas_without_double_counting(self):
        evidence = self._build([
            {"usage_mode": "delta", "usage": {"input_tokens": 3, "output_tokens": 2}},
            {"usage_mode": "delta", "usage": {"input_tokens": 4, "output_tokens": 5}},
            {"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 7}},
        ])
        self.assertEqual(7, evidence["aggregate"]["input_tokens"])
        self.assertEqual(7, evidence["aggregate"]["output_tokens"])
        self.assertIn("MIXED_MODES_TERMINAL_AUTHORITATIVE", evidence["incomplete_reasons"])

    def test_unidentified_duplicate_delta_is_ambiguous_not_silently_counted(self):
        event = {"usage_mode": "delta", "usage": {"input_tokens": 2}}
        evidence = self._build([event, event])
        self.assertEqual(2, evidence["aggregate"]["input_tokens"])
        self.assertEqual(1, evidence["classified_usage_count"])
        self.assertFalse(evidence["usage_complete"])
        self.assertIn("AMBIGUOUS_DUPLICATE_DELTA_EVENTS", evidence["incomplete_reasons"])

    def test_distinct_identified_equal_deltas_are_both_counted(self):
        evidence = self._build([
            {"event_id": "one", "usage_mode": "delta", "usage": {"input_tokens": 2}},
            {"event_id": "two", "usage_mode": "delta", "usage": {"input_tokens": 2}},
        ])
        self.assertTrue(evidence["usage_complete"])
        self.assertEqual(4, evidence["aggregate"]["input_tokens"])
        self.assertEqual(2, evidence["classified_usage_count"])

    def test_conflicting_payload_reuse_of_provider_event_id_is_incomplete(self):
        evidence = self._build([
            {
                "event_id": "usage-1",
                "type": "usage",
                "usage_mode": "delta",
                "usage": {"input_tokens": 2},
            },
            {
                "event_id": "usage-1",
                "type": "usage",
                "usage_mode": "delta",
                "usage": {"input_tokens": 9},
            },
        ])
        self.assertFalse(evidence["usage_complete"])
        self.assertIn(
            "CONFLICTING_PROVIDER_EVENT_ID", evidence["incomplete_reasons"]
        )
        self.assertEqual(2, evidence["aggregate"]["input_tokens"])

    def test_mixed_nonterminal_modes_are_incomplete_and_null(self):
        evidence = self._build([
            {"usage_mode": "delta", "usage": {"input_tokens": 2}},
            {"usage_mode": "cumulative", "usage": {"input_tokens": 2}},
        ])
        self.assertFalse(evidence["usage_complete"])
        self.assertIsNone(evidence["aggregate"]["input_tokens"])

    def test_cached_reasoning_and_claude_cost_variants(self):
        evidence = self._build([
            {"type": "result", "total_cost_usd": 0.25, "usage": {
                "input_tokens": 10,
                "cache_read_input_tokens": 4,
                "cache_creation_input_tokens": 2,
                "output_tokens": 3,
                "reasoning_tokens": 1,
            }}
        ], stream_format="claude-stream-json")
        aggregate = evidence["aggregate"]
        self.assertEqual(4, aggregate["cached_input_tokens"])
        self.assertEqual(2, aggregate["cache_write_input_tokens"])
        self.assertEqual(1, aggregate["reasoning_output_tokens"])
        self.assertEqual(0.25, aggregate["provider_billed_cost"])
        self.assertEqual("USD", aggregate["currency"])

    def test_empty_terminal_usage_is_incomplete(self):
        evidence = self._build([{"type": "turn.completed"}])
        self.assertFalse(evidence["usage_complete"])
        self.assertIn("TERMINAL_USAGE_EMPTY", evidence["incomplete_reasons"])

    def test_conflicting_terminal_updates_fail_closed(self):
        evidence = self._build([
            {"type": "turn.completed", "usage": {"input_tokens": 3}},
            {"type": "turn.completed", "usage": {"input_tokens": 4}},
        ])
        self.assertFalse(evidence["usage_complete"])
        self.assertIsNone(evidence["aggregate"]["input_tokens"])
        self.assertIn("CONFLICTING_TERMINAL_UPDATES", evidence["incomplete_reasons"])

    def test_non_finite_usage_is_rejected(self):
        evidence = self._build([
            {"type": "turn.completed", "usage": {"input_tokens": float("inf")}},
        ])
        self.assertFalse(evidence["usage_complete"])
        self.assertIsNone(evidence["aggregate"]["input_tokens"])

    def test_provider_cost_without_currency_is_incomplete(self):
        evidence = self._build([
            {"type": "turn.completed", "usage": {
                "input_tokens": 1, "provider_billed_cost": 0.1
            }},
        ])
        self.assertFalse(evidence["usage_complete"])
        self.assertIn("PROVIDER_COST_MISSING_CURRENCY", evidence["incomplete_reasons"])

    def test_nonmonotonic_cumulative_usage_fails_closed(self):
        evidence = self._build([
            {"usage_mode": "cumulative", "usage": {"input_tokens": 10}},
            {"usage_mode": "cumulative", "usage": {"input_tokens": 9}},
        ])
        self.assertFalse(evidence["usage_complete"])
        self.assertIsNone(evidence["aggregate"]["input_tokens"])
        self.assertIn("NONMONOTONIC_CUMULATIVE_USAGE", evidence["incomplete_reasons"])

    def test_raw_event_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.jsonl"
            target.write_text('{"type":"turn.completed","usage":{"input_tokens":1}}\n', encoding="utf-8")
            link = root / "executor-events.jsonl"
            os.symlink(target, link)
            with self.assertRaisesRegex(Exception, "non-symlink"):
                build_provider_evidence(
                    events_path=link,
                    stream_format="codex-jsonl",
                    executor="codex",
                    session_id="evidence-test",
                )

    def test_unknown_cost_remains_null(self):
        evidence = self._build([
            {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}
        ])
        self.assertIsNone(evidence["aggregate"]["provider_billed_cost"])
        self.assertIsNone(evidence["aggregate"]["local_estimated_cost"])
        self.assertIsNone(evidence["aggregate"]["currency"])
