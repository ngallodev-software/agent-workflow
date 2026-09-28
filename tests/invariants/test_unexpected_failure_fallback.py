from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from agent_workflow.unexpected_failures import record_unexpected_failure


def test_unexpected_failure_uses_temp_fallback_when_state_root_is_unwritable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    blocked_parent = tmp_path / "blocked"
    blocked_parent.write_text("not a directory\n", encoding="utf-8")
    state_root = blocked_parent / "state"

    fallback = tmp_path / "fallback"

    def fake_mkdtemp(*, prefix: str) -> str:
        assert prefix == "agent-workflow-unexpected-"
        fallback.mkdir()
        return str(fallback)

    monkeypatch.setattr(
        "agent_workflow.unexpected_failures.tempfile.mkdtemp",
        fake_mkdtemp,
    )

    try:
        raise RuntimeError("original failure")
    except RuntimeError as exc:
        result = record_unexpected_failure(
            exc,
            settings=SimpleNamespace(state_root=state_root),
            argv=["agent", "finish", "run-1"],
            top_level="agent",
        )

    path = Path(result["path"])
    assert path.parent == fallback
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["correlation_id"] == result["correlation_id"]
    assert record["exception"]["type"] == "RuntimeError"
    assert record["exception"]["message"] == "original failure"
    assert path.stat().st_mode & 0o777 == 0o600
