from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.eval.compare import compare_trials
from agent_workflow.provider_evidence import build_provider_evidence
from tests.support import trial


def _evidence(tmp_path: Path, events: list[dict], stream_format: str = "codex-jsonl") -> dict:
    path = tmp_path / "executor-events.jsonl"
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
    return build_provider_evidence(
        events_path=path,
        stream_format=stream_format,
        executor="codex" if stream_format == "codex-jsonl" else "claude",
        session_id="provider-matrix",
    )


@pytest.mark.parametrize(
    ("events", "complete", "input_tokens", "reason"),
    [
        ([{"event_id": "1", "usage_mode": "delta", "usage": {"input_tokens": 2}}, {"event_id": "2", "usage_mode": "delta", "usage": {"input_tokens": 3}}], True, 5, None),
        ([{"event_id": "same", "usage_mode": "delta", "usage": {"input_tokens": 2}}, {"event_id": "same", "usage_mode": "delta", "usage": {"input_tokens": 9}}], False, 2, "CONFLICTING_PROVIDER_EVENT_ID"),
        ([{"usage_mode": "delta", "usage": {"input_tokens": 2}}, {"usage_mode": "cumulative", "usage": {"input_tokens": 2}}], False, None, "MIXED_NONTERMINAL_USAGE_MODES"),
        ([{"type": "turn.completed"}], False, None, "TERMINAL_USAGE_EMPTY"),
    ],
)
def test_provider_usage_accounting_matrix(
    tmp_path: Path, events: list[dict], complete: bool, input_tokens: int | None, reason: str | None
) -> None:
    evidence = _evidence(tmp_path, events)
    assert evidence["usage_complete"] is complete
    assert evidence["aggregate"]["input_tokens"] == input_tokens
    if reason:
        assert reason in evidence["incomplete_reasons"]


def test_terminal_totals_are_authoritative_without_double_counting(tmp_path: Path) -> None:
    evidence = _evidence(
        tmp_path,
        [
            {"event_id": "d1", "usage_mode": "delta", "usage": {"input_tokens": 3, "output_tokens": 2}},
            {"event_id": "d2", "usage_mode": "delta", "usage": {"input_tokens": 4, "output_tokens": 5}},
            {"event_id": "t", "type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 7}},
        ],
    )
    assert evidence["aggregate"]["input_tokens"] == 7
    assert evidence["aggregate"]["output_tokens"] == 7


def test_comparison_rejects_mismatched_cohorts_and_never_overclaims_small_samples() -> None:
    result = compare_trials([trial("b", "fail")], [trial("c", "pass")])
    assert result["winner"] is None
    assert result["paired_n"] == 1
    with pytest.raises(WorkflowError, match="cohorts do not match"):
        compare_trials([trial("b", "fail", task_id="a")], [trial("c", "pass", task_id="b")])
