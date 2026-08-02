from __future__ import annotations

import json
from argparse import Namespace
from dataclasses import replace
from pathlib import Path

from agent_workflow.cli_handlers.workflow import handle_workflow_command
from agent_workflow.config import Settings, defaults
from agent_workflow.util import read_json
from agent_workflow.workflow import snapshot_sha256


def _settings(tmp_path: Path) -> Settings:
    config = tmp_path / "config.toml"
    state_root = tmp_path / "state"
    worktree_root = tmp_path / "worktrees"
    config.write_text(
        "schema_version = 1\n\n"
        "[paths]\n"
        f"state_root = {json.dumps(str(state_root))}\n"
        f"worktree_root = {json.dumps(str(worktree_root))}\n",
        encoding="utf-8",
    )
    return replace(
        defaults(config),
        state_root=state_root,
        worktree_root=worktree_root,
    )


def test_workflow_template_handler_owns_template_output_and_rendering(
    tmp_path: Path,
    capsys,
) -> None:
    spec = tmp_path / "template-spec.json"
    spec.write_text(
        json.dumps(
            {
                "workflow_id": "handler-template",
                "pack_id": "handler-pack",
                "pack_manifest_sha256": "a" * 64,
                "parameters": {
                    "steps": [
                        {
                            "node_id": "first",
                            "session_id": "handler-first",
                            "prompt_path": "/tmp/first.md",
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "workflow.json"

    data, output_complete = handle_workflow_command(
        _settings(tmp_path),
        Namespace(
            workflow_command="template",
            template="pipeline",
            spec=spec,
            output=output,
            json=False,
        ),
    )

    assert data is None
    assert output_complete is True
    assert capsys.readouterr().out.strip() == str(output)
    snapshot = read_json(output)
    assert snapshot["workflow_id"] == "handler-template"
    assert snapshot_sha256(snapshot)

class _FakeWorkflowService:
    calls: list[tuple[str, str]] = []

    def __init__(self, *, scheduler) -> None:
        self.scheduler = scheduler

    def _record(self, operation: str, snapshot: str):
        self.calls.append((operation, snapshot))
        return {"operation": operation, "snapshot": snapshot}

    def validate(self, snapshot: str):
        return self._record("validate", snapshot)

    def start(self, snapshot: str):
        return self._record("start", snapshot)

    def status(self, snapshot: str):
        return self._record("status", snapshot)

    def resume(self, snapshot: str):
        return self._record("resume", snapshot)

    def seal(self, snapshot: str):
        return self._record("seal", snapshot)

    def verify(self, snapshot: str):
        return self._record("verify", snapshot)


class _FakeSchedulerService:
    def __init__(self, *, settings, run_dir, workdir) -> None:
        self.settings = settings
        self.run_dir = run_dir
        self.workdir = workdir


def test_workflow_handler_routes_service_operations_without_rendering(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import agent_workflow.cli_handlers.workflow as workflow_handler

    _FakeWorkflowService.calls = []
    monkeypatch.setattr(workflow_handler, "WorkflowService", _FakeWorkflowService)
    monkeypatch.setattr(workflow_handler, "SchedulerService", _FakeSchedulerService)
    settings = _settings(tmp_path)

    for command in ("validate", "start", "status", "resume", "seal", "verify"):
        data, output_complete = handle_workflow_command(
            settings,
            Namespace(
                workflow_command=command,
                snapshot=f"{command}.json",
                run_dir=tmp_path,
            ),
        )
        assert output_complete is False
        assert data == {"operation": command, "snapshot": f"{command}.json"}

    assert _FakeWorkflowService.calls == [
        (command, f"{command}.json")
        for command in ("validate", "start", "status", "resume", "seal", "verify")
    ]

