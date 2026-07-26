from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from agent_workflow.config import defaults
from agent_workflow.mcp.server import _service_result
from agent_workflow.mcp.services import (
    PackValidationRequest,
    PageRequest,
    ServiceError,
    WorkflowReadService,
    _page,
)
from agent_workflow.messages import append_message
from agent_workflow.util import atomic_write_json


def _service(tmp_path: Path) -> tuple[WorkflowReadService, Path]:
    state = tmp_path / "state"
    repo = tmp_path / "repo"
    state.mkdir()
    repo.mkdir()
    settings = replace(defaults(tmp_path / "config.toml"), state_root=state)
    return WorkflowReadService(settings, repository_root=repo), state


def _status(state: Path, session_id: str = "run-1") -> Path:
    run = state / "runs" / session_id
    run.mkdir(parents=True)
    atomic_write_json(
        run / "status.json",
        {
            "schema": "agent-workflow/session-status/v2",
            "session_id": session_id,
            "status": "running",
            "disposition": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "workdir": "/private/workdir",
            "prompt_path": "/private/prompt",
            "log_path": "/private/log",
        },
    )
    return run


def test_message_listing_is_metadata_only_and_bounded(tmp_path: Path) -> None:
    service, state = _service(tmp_path)
    run = _status(state)
    secret = "synthetic-secret@example.test"
    append_message(
        run,
        session_id="run-1",
        direction="child_to_parent",
        kind="progress",
        actor="child",
        content=secret,
    )

    result = service.list_messages("run-1")
    encoded = json.dumps(result.as_dict())
    assert secret not in encoded
    item = result.items[0]
    assert item["redaction_state"] == "body_omitted"
    assert item["content_length"] == len(secret.encode())
    assert "content" not in item
    assert result.as_dict()["schema"] == "agent-workflow/mcp-page/v1"


@pytest.mark.parametrize("selected", ["pack-link", "alias/pack"])
def test_pack_path_symlink_components_fail_closed(tmp_path: Path, selected: str) -> None:
    service, _ = _service(tmp_path)
    repo = service.repository_root
    real = repo / "real"
    real.mkdir()
    (real / "pack").mkdir()
    if selected == "pack-link":
        os.symlink("real/pack", repo / selected)
    else:
        os.symlink("real", repo / "alias")

    with pytest.raises(ServiceError) as caught:
        service.validate_pack(PackValidationRequest(selected))
    assert caught.value.category == "forbidden_root"


def test_receipt_summary_rejects_writable_or_irregular_entries_without_partial_output(tmp_path: Path) -> None:
    service, state = _service(tmp_path)
    run = _status(state)
    receipts = run / "receipts"
    receipts.mkdir()
    (receipts / "000001-reviewed.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ServiceError) as caught:
        service.list_receipts("run-1")
    assert caught.value.category == "invalid_evidence"


def test_pagination_and_unexpected_errors_are_stable() -> None:
    with pytest.raises(ServiceError) as caught:
        _page(PageRequest(limit=101), [])
    assert caught.value.category == "invalid_limit"

    response = _service_result(lambda: (_ for _ in ()).throw(RuntimeError("/secret/path")))
    assert response["error"] == "internal_error"
    assert response["correlation_id"]
    assert "/secret/path" not in json.dumps(response)
