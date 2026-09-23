from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from agent_workflow.worker_completion import finish


def _setup(tmp_path: Path, monkeypatch, *, criteria, acceptance, verification_results):
    import agent_workflow.worker_completion as module

    state_dir = tmp_path / "state" / "runs" / "run-1"
    handoff = state_dir / "handoff"
    worktree = tmp_path / "repo"
    handoff.mkdir(parents=True)
    worktree.mkdir()

    contract = {
        "agent_run": {"id": "run-1"},
        "criteria": criteria,
        "worktree": {"path": str(worktree), "source_revision": "a" * 40},
        "paths": {"handoff_dir": str(handoff)},
        "ticket": "P0-00",
        "ticket_identity": {"mode": "explicit", "value": "P0-00"},
        "pack": {"id": "pack-1"},
    }
    binding = {
        "schema": "agent-workflow/job-binding/v1",
        "acceptance_commands": acceptance,
    }
    settings = SimpleNamespace(state_root=tmp_path / "state")

    monkeypatch.setattr(
        module,
        "_context",
        lambda *_a, **_k: (state_dir, contract, worktree, handoff),
    )
    monkeypatch.setattr(module, "_job_binding", lambda _state: binding)

    results = iter(verification_results)

    def fake_verify(_settings, _run_id, *, argv, cwd=None, timeout_seconds=None):
        value = next(results)
        return {
            "agent_run_id": "run-1",
            "ok": value["ok"],
            "reused": value.get("reused", False),
            "command": {
                "argv": list(argv),
                "cwd": str(cwd or worktree),
                "exit_code": 0 if value["ok"] else 1,
                "receipt": value.get("receipt", "exit=0" if value["ok"] else "exit=1"),
            },
            "stdout": value.get("stdout", ""),
            "stderr": value.get("stderr", ""),
            "workspace_sha256": "f" * 64,
        }

    monkeypatch.setattr(module, "verify_command", fake_verify)
    return settings, handoff


def test_finish_runs_acceptance_once_and_derives_mapped_criterion(tmp_path: Path, monkeypatch) -> None:
    import agent_workflow.worker_completion as module

    settings, handoff = _setup(
        tmp_path,
        monkeypatch,
        criteria=[
            {
                "id": "tests-pass",
                "description": "Acceptance suite passes",
                "acceptance_command_ids": ["pytest"],
            }
        ],
        acceptance=[
            {
                "id": "pytest",
                "argv": ["pytest", "-q"],
                "cwd": ".",
                "timeout_seconds": 300,
                "result_format": "exit-code",
                "junit_path": None,
            }
        ],
        verification_results=[{"ok": True, "reused": True, "receipt": "exit=0"}],
    )
    completed = {}

    def fake_complete(_settings, _run_id, **kwargs):
        completed.update(kwargs)
        return {
            "agent_run_id": "run-1",
            "state": "finalized",
            "result": kwargs["result"],
        }

    monkeypatch.setattr(module, "complete", fake_complete)

    result = finish(settings, "run-1", result="completed")
    assert result["state"] == "finalized"
    assert result["fast_path"] is True
    assert result["verification"][0]["id"] == "pytest"
    draft = json.loads((handoff / module.DRAFT_NAME).read_text(encoding="utf-8"))
    assert draft["criteria"] == [
        {
            "id": "tests-pass",
            "result": "pass",
            "evidence": [
                "acceptance-command:pytest; ok=True; reused=True; receipt=exit=0"
            ],
        }
    ]
    telemetry = json.loads((handoff / module.PROTOCOL_TELEMETRY_NAME).read_text(encoding="utf-8"))
    assert telemetry["acceptance"]["executed"] == 1
    assert telemetry["acceptance"]["cache_hits"] == 1
    assert telemetry["finish"]["outcomes"]["completed"] == 1


def test_finish_stops_on_failed_acceptance_and_requests_repair(tmp_path: Path, monkeypatch) -> None:
    import agent_workflow.worker_completion as module

    settings, handoff = _setup(
        tmp_path,
        monkeypatch,
        criteria=[
            {
                "id": "tests-pass",
                "description": None,
                "acceptance_command_ids": ["pytest"],
            }
        ],
        acceptance=[
            {
                "id": "pytest",
                "argv": ["pytest", "-q"],
                "cwd": ".",
                "timeout_seconds": 300,
                "result_format": "exit-code",
                "junit_path": None,
            }
        ],
        verification_results=[{"ok": False, "stderr": "1 failed", "receipt": "exit=1"}],
    )
    monkeypatch.setattr(
        module,
        "complete",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("completion must not run")),
    )

    result = finish(settings, "run-1", result="completed")
    assert result["state"] == "verification_failed"
    assert result["repair_required"] is True
    assert result["failed_acceptance_commands"] == ["pytest"]
    assert result["verification"][0]["stderr"] == "1 failed"

    draft = json.loads((handoff / module.DRAFT_NAME).read_text(encoding="utf-8"))
    assert draft["criteria"][0]["result"] == "fail"


def test_finish_only_requests_unmapped_semantic_criteria(tmp_path: Path, monkeypatch) -> None:
    import agent_workflow.worker_completion as module

    settings, _handoff = _setup(
        tmp_path,
        monkeypatch,
        criteria=[
            {
                "id": "tests-pass",
                "description": None,
                "acceptance_command_ids": ["pytest"],
            },
            {
                "id": "architecture-review",
                "description": "Semantic architecture requirement",
                "acceptance_command_ids": [],
            },
        ],
        acceptance=[
            {
                "id": "pytest",
                "argv": ["pytest", "-q"],
                "cwd": ".",
                "timeout_seconds": 300,
                "result_format": "exit-code",
                "junit_path": None,
            }
        ],
        verification_results=[{"ok": True}],
    )
    monkeypatch.setattr(
        module,
        "complete",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("completion must wait")),
    )

    result = finish(settings, "run-1", result="completed")
    assert result["state"] == "semantic_evidence_required"
    assert result["criteria"] == ["architecture-review"]


def test_finish_compatibility_run_without_bound_commands_requests_legacy_verification(
    tmp_path: Path, monkeypatch
) -> None:
    import agent_workflow.worker_completion as module

    state_dir = tmp_path / "state" / "runs" / "run-1"
    handoff = state_dir / "handoff"
    worktree = tmp_path / "repo"
    handoff.mkdir(parents=True)
    worktree.mkdir()
    contract = {
        "agent_run": {"id": "run-1"},
        "criteria": [],
        "worktree": {"path": str(worktree), "source_revision": None},
        "paths": {"handoff_dir": str(handoff)},
        "ticket": None,
        "ticket_identity": {"mode": "omitted", "value": None},
        "pack": {"id": None},
    }
    settings = SimpleNamespace(state_root=tmp_path / "state")
    monkeypatch.setattr(
        module,
        "_context",
        lambda *_a, **_k: (state_dir, contract, worktree, handoff),
    )
    monkeypatch.setattr(module, "_job_binding", lambda _state: None)

    result = finish(settings, "run-1", result="completed")
    assert result["state"] == "verification_required"
    assert "legacy agent verify" in result["next_action"]
