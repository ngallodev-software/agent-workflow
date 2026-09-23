from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

from agent_workflow.context_efficiency import (
    update_executor_context_runtime,
    write_executor_context,
)
from agent_workflow.worker_completion import verify_command


def test_executor_context_projects_durable_refs_and_runtime_amplification(tmp_path) -> None:
    state = tmp_path / "run"
    handoff = state / "handoff"
    handoff.mkdir(parents=True)
    prompt = state / "prompt.md"
    launch = state / "launch-prompt.md"
    card = state / "command-card.md"
    catalog = state / "command-catalog.json"
    baseline = state / "source-baseline.json"
    prompt.write_text("ticket\n", encoding="utf-8")
    launch.write_text("runtime\n---\nticket\n", encoding="utf-8")
    card.write_text("card\n", encoding="utf-8")
    catalog.write_text("{}\n", encoding="utf-8")
    baseline.write_text("{}\n", encoding="utf-8")
    command_artifacts = {
        "card_path": "command-card.md",
        "card_sha256": hashlib.sha256(card.read_bytes()).hexdigest(),
        "catalog_path": "command-catalog.json",
        "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
    }
    value = write_executor_context(
        state,
        agent_run_id="run-1",
        role_id="implementation",
        role_digest="d" * 64,
        prompt_path=prompt,
        launch_prompt_path=launch,
        handoff_dir=handoff,
        command_artifacts=command_artifacts,
        criteria=({"id": "AC-01", "description": "not replayed"},),
        source_baseline_path=baseline,
    )
    assert value["projection"]["criteria_ids"] == ["AC-01"]
    assert "schema_validation" in value["projection"]["host_deterministic_gates"]
    assert value["measurements"]["injected_context"]["bytes"] == len(launch.read_bytes()) - len(prompt.read_bytes())
    assert (handoff / "executor-context.json").is_file()

    events = state / "executor-events.jsonl"
    events.write_text(
        "\n".join(
            json.dumps(item)
            for item in (
                {"type": "turn.completed", "id": "turn-1"},
                {"type": "item.completed", "item": {"id": "cmd-1", "type": "command_execution", "command": "agent-workflow agent finish run-1 --result completed"}},
                {"type": "turn.completed", "id": "turn-2"},
            )
        ) + "\n",
        encoding="utf-8",
    )
    (handoff / "protocol-telemetry.json").write_text(
        json.dumps({
            "schema": "agent-workflow/protocol-telemetry/v2",
            "cli_command_counts": {"finish": 1},
            "acceptance": {"executed": 2, "reused": 1, "failed": 0, "cache_hits": 1, "cache_misses": 1},
            "finish": {"invocations": 2, "outcomes": {"completed": 1}},
        }) + "\n",
        encoding="utf-8",
    )
    (state / "messages.jsonl").write_text(
        json.dumps({"kind": "steer"}) + "\n" + json.dumps({"kind": "ack"}) + "\n",
        encoding="utf-8",
    )
    updated = update_executor_context_runtime(
        state,
        events_path=events,
        provider_evidence={"aggregate": {"input_tokens": 200, "cached_input_tokens": 120}},
    )
    assert updated is not None
    assert updated["runtime"]["model_turn_count"] == 2
    assert updated["runtime"]["tool_call_count"] == 1
    assert updated["runtime"]["command_execution_count"] == 1
    assert updated["runtime"]["input_tokens_per_turn"] == 100.0
    assert updated["runtime"]["cached_input_ratio"] == 0.6
    assert updated["runtime"]["command_families"]["agent-workflow agent finish"] == 1
    assert updated["runtime"]["protocol_command_counts"] == {"finish": 1}
    assert updated["runtime"]["acceptance_command_executions"] == 2
    assert updated["runtime"]["verification_cache_hits"] == 1
    assert updated["runtime"]["verification_cache_misses"] == 1
    assert updated["runtime"]["finish_invocations"] == 2
    assert updated["runtime"]["finish_incomplete_invocations"] == 1
    assert updated["runtime"]["finish_outcomes"] == {"completed": 1}
    assert updated["runtime"]["message_kind_counts"] == {"ack": 1, "steer": 1}


def _completion_context(tmp_path, monkeypatch, *, fingerprints: list[str], returncodes: list[int]):
    import agent_workflow.worker_completion as module

    repo = tmp_path / "repo"
    handoff = tmp_path / "state" / "runs" / "run-1" / "handoff"
    handoff.mkdir(parents=True)
    repo.mkdir()
    contract = {
        "agent_run": {"id": "run-1"},
        "worktree": {"path": str(repo), "source_revision": None},
        "paths": {"handoff_dir": str(handoff)},
        "ticket": None,
        "ticket_identity": {"mode": "omitted", "value": None},
        "pack": {"id": None},
    }
    settings = SimpleNamespace(state_root=tmp_path / "state")
    monkeypatch.setattr(module, "_context", lambda *_a, **_k: (handoff.parent, contract, repo, handoff))
    fingerprints_iter = iter(fingerprints)
    monkeypatch.setattr(module, "_workspace_fingerprint", lambda _repo: next(fingerprints_iter))
    calls = []
    codes = iter(returncodes)

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        code = next(codes)
        return SimpleNamespace(argv=tuple(argv), stdout="ok", stderr="", returncode=code)

    monkeypatch.setattr(module, "run", fake_run)
    return settings, calls


def test_successful_verification_reuses_receipt_when_workspace_is_unchanged(tmp_path, monkeypatch) -> None:
    settings, calls = _completion_context(
        tmp_path, monkeypatch, fingerprints=["same", "same", "same"], returncodes=[0]
    )
    first = verify_command(settings, "run-1", argv=["pytest", "-q"])
    second = verify_command(settings, "run-1", argv=["pytest", "-q"])
    assert first["reused"] is False
    assert second["reused"] is True
    assert len(calls) == 1


def test_verification_cache_invalidates_on_workspace_change(tmp_path, monkeypatch) -> None:
    settings, calls = _completion_context(
        tmp_path,
        monkeypatch,
        fingerprints=["before", "after", "changed", "after2"],
        returncodes=[0, 0],
    )
    verify_command(settings, "run-1", argv=["pytest", "-q"])
    second = verify_command(settings, "run-1", argv=["pytest", "-q"])
    assert second["reused"] is False
    assert len(calls) == 2


def test_failed_verification_is_never_reused(tmp_path, monkeypatch) -> None:
    settings, calls = _completion_context(
        tmp_path, monkeypatch, fingerprints=["a", "b", "b", "c"], returncodes=[1, 0]
    )
    first = verify_command(settings, "run-1", argv=["pytest", "-q"])
    second = verify_command(settings, "run-1", argv=["pytest", "-q"])
    assert first["ok"] is False
    assert second["reused"] is False
    assert len(calls) == 2


def test_verification_cache_reuses_success_across_agent_runs_on_same_worktree(tmp_path, monkeypatch) -> None:
    import agent_workflow.worker_completion as module

    repo = tmp_path / "repo-shared"
    repo.mkdir()
    settings = SimpleNamespace(state_root=tmp_path / "state")
    contexts = {}
    for run_id in ("run-a", "run-b"):
        handoff = settings.state_root / "runs" / run_id / "handoff"
        handoff.mkdir(parents=True)
        contract = {
            "agent_run": {"id": run_id},
            "worktree": {"path": str(repo), "source_revision": None},
            "paths": {"handoff_dir": str(handoff)},
            "ticket": None,
            "ticket_identity": {"mode": "omitted", "value": None},
            "pack": {"id": None},
        }
        contexts[run_id] = (handoff.parent, contract, repo, handoff)

    monkeypatch.setattr(module, "_context", lambda _settings, run_id: contexts[run_id])
    monkeypatch.setattr(
        module,
        "_cache_entry_reusable",
        lambda _settings, *, current_agent_run_id, entry: True,
    )
    fingerprints = iter(["same-workspace", "same-workspace", "same-workspace"])
    monkeypatch.setattr(module, "_workspace_fingerprint", lambda _repo: next(fingerprints))
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        return SimpleNamespace(argv=tuple(argv), stdout="passed", stderr="", returncode=0)

    monkeypatch.setattr(module, "run", fake_run)

    first = verify_command(settings, "run-a", argv=["python", "-m", "unittest"])
    second = verify_command(settings, "run-b", argv=["python", "-m", "unittest"])

    assert first["reused"] is False
    assert second["reused"] is True
    assert second["reused_from_agent_run_id"] == "run-a"
    assert len(calls) == 1
    assert first["stdout"] == ""
    assert first["output_refs"]["stdout"]["bytes"] == len("passed")
    assert (settings.state_root / "runs" / "run-a" / first["output_refs"]["stdout"]["path"]).is_file()
