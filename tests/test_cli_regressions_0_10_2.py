from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from agent_workflow.agent_identity import (
    AgentNameInUseError,
    claim_agent_name,
    release_agent_name,
    resolve_agent_identity,
)
from agent_workflow.agent_runs import _resolve_job_reference, _resolve_pack_reference
from agent_workflow import delegation as delegation_module
from agent_workflow.cli_parser import build_parser
from agent_workflow.config import LUNA_MODEL, defaults
from agent_workflow.pack import scaffold


def test_delegate_model_override_does_not_inject_default_role() -> None:
    parser = build_parser(command_scope="delegate")
    args = parser.parse_args(
        [
            "delegate",
            "run-1",
            "prompt.md",
            "--workdir",
            ".",
            "--model",
            "gpt-5",
        ]
    )
    assert args.role is None
    assert args.model == "gpt-5"



def test_model_pinned_identity_without_role_uses_compatibility_path(tmp_path: Path) -> None:
    settings = replace(
        defaults(tmp_path / "config.toml"),
        state_root=tmp_path / "state",
    )
    identity = resolve_agent_identity(
        settings,
        requested_name=None,
        requested_role=None,
        requested_class=None,
        executor="codex",
        model=LUNA_MODEL,
        allow_no_go_model=False,
        explicit_command=None,
        interactive=False,
    )
    assert identity.model == LUNA_MODEL
    assert identity.runtime_alias is None


@pytest.mark.parametrize("flag", ["--json", "--structured"])
def test_agent_run_status_accepts_machine_readable_flag_after_subcommand(flag: str) -> None:
    parser = build_parser(command_scope="agent-run")
    args = parser.parse_args(["agent-run", "status", "run-1", flag])
    assert args.json is True



def test_delegate_defers_ticket_default_when_job_selector_is_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = replace(
        defaults(tmp_path / "config.toml"),
        state_root=tmp_path / "state",
    )
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Implement the selected task.\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_prepare(_settings, **kwargs):
        captured.update(kwargs)
        return {"status": "prepared", "role": "implementation"}

    monkeypatch.setattr(delegation_module, "prepare_agent_run", fake_prepare)
    monkeypatch.setattr(delegation_module, "public_agent_run_view", lambda value: value)

    result = delegation_module.delegate(
        settings,
        agent_run_id="portfolio-run",
        prompt_path=prompt,
        workdir=tmp_path,
        job_path=Path("P0-00"),
        worker_mode="external",
    )

    assert captured["ticket_id"] is None
    assert captured["job_path"] == Path("P0-00")
    assert result["state"] == "prepared"

def test_pack_path_and_v1_task_id_resolve_to_manifest_identity(tmp_path: Path) -> None:
    pack_root = tmp_path / "portfolio-pack"
    scaffold(pack_root, 1, name="portfolio-site")
    prompt = next((pack_root / "phase-0" / "tickets").glob("P0-00-*.md"))

    selected_root, selected_id = _resolve_pack_reference(
        pack_reference=str(pack_root),
        prompt_source=prompt,
        prompt_pack_root_override=None,
    )
    assert selected_root == pack_root.resolve()
    assert selected_id == "portfolio-site"

    native_job, ticket_id, pack_id = _resolve_job_reference(
        job_reference=Path("P0-00"),
        pack_root=selected_root,
        prompt_path=prompt,
        workdir=tmp_path,
        ticket_id=None,
        pack_id=selected_id,
    )
    assert native_job is None
    assert ticket_id == "P0-00"
    assert pack_id == "portfolio-site"


def test_live_unpublished_name_lease_can_be_skipped_for_implicit_allocation(
    tmp_path: Path,
) -> None:
    settings = replace(
        defaults(tmp_path / "config.toml"),
        state_root=tmp_path / "state",
    )
    claim_agent_name(
        settings,
        agent_name="agent-01",
        agent_run_id="owner-run",
        interactive=False,
    )
    try:
        first = resolve_agent_identity(
            settings,
            requested_name=None,
            requested_role=None,
            requested_class=None,
            executor=None,
            model=None,
            allow_no_go_model=False,
            explicit_command=None,
            interactive=False,
        )
        assert first.agent_name == "agent-01"
        with pytest.raises(AgentNameInUseError):
            claim_agent_name(
                settings,
                agent_name=first.agent_name,
                agent_run_id="second-run",
                interactive=False,
            )

        retry = resolve_agent_identity(
            settings,
            requested_name=None,
            requested_role=None,
            requested_class=None,
            executor=None,
            model=None,
            allow_no_go_model=False,
            explicit_command=None,
            interactive=False,
            unavailable_names={first.agent_name},
        )
        assert retry.agent_name == "agent-02"
    finally:
        release_agent_name(
            settings,
            agent_name="agent-01",
            agent_run_id="owner-run",
        )


def test_restart_parser_is_prepare_first_and_accepts_context_file() -> None:
    parser = build_parser(command_scope="agent-run")
    args = parser.parse_args(
        ["agent-run", "restart", "run-1", "--context-file", "retry.md"]
    )
    assert args.context_file == Path("retry.md")
    assert args.start is False


def test_launch_prompt_records_dirty_authorization_retry_context_and_completion_contract(
    tmp_path: Path,
) -> None:
    from agent_workflow.agent_runs import _write_launch_prompt

    state_dir = tmp_path / "run"
    state_dir.mkdir()
    (state_dir / "prompt.md").write_text("Do the ticket.\n", encoding="utf-8")
    handoff = tmp_path / "handoff"
    handoff.mkdir()

    launch = _write_launch_prompt(
        state_dir,
        agent_run_id="retry-run",
        agent_name="agent-01",
        agent_class="implementation",
        role_id="implementation",
        role_digest="a" * 64,
        role_instructions=None,
        tier="low",
        retry_of="prior-run",
        created_at="2026-09-19T00:00:00+00:00",
        prompt_source=tmp_path / "ticket.md",
        prompt_pack_root=None,
        handoff_dir=handoff,
        command_artifacts={"role": "implementation"},
        dirty_at_launch=True,
        dirty_authorized=True,
        retry_context="Use pass/fail/not_verified and preserve the approved baseline drift.",
    )
    text = launch.read_text(encoding="utf-8")
    assert "Operator-approved source drift" in text
    assert "do not mark the task blocked merely because the baseline is dirty" in text
    assert "## Operator retry context" in text
    assert "pass`, `fail`, or `not_verified`" in text
    assert "agent completion-validate" in text


def test_review_prerequisite_accepts_verified_sealed_completion_without_lifecycle_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_workflow import preflight as preflight_module

    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    run = settings.state_root / "runs" / "impl-run"
    run.mkdir(parents=True)
    (run / "final-receipt.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        preflight_module,
        "verify_seal_details",
        lambda _run: ({"agent_run_id": "impl-run"}, "f" * 64),
    )
    monkeypatch.setattr(preflight_module, "lifecycle_receipts", lambda *args, **kwargs: [])

    def fake_read_sealed(_run, _receipt, relative, _schema):
        if relative == "final-status.json":
            return {"status": "completed"}, "1" * 64
        if relative == "completion.json":
            return {"result": "completed"}, "2" * 64
        if relative == "collections/completion.json":
            return {"validation_status": "valid"}, "3" * 64
        raise AssertionError(relative)

    monkeypatch.setattr(preflight_module, "read_sealed_contract", fake_read_sealed)

    review = preflight_module.resolve_prerequisites(
        settings, ["impl-run"], requirement="sealed_completed"
    )
    assert review["status"] == "accepted"
    assert "reviewable" in review["prerequisites"][0]["reason"]

    implementation = preflight_module.resolve_prerequisites(
        settings, ["impl-run"], requirement="accepted"
    )
    assert implementation["status"] == "missing"


def test_linked_worktree_exposes_both_git_admin_roots(tmp_path: Path) -> None:
    import subprocess

    from agent_workflow.git import administrative_dirs

    repo = tmp_path / "repo"
    worktree = tmp_path / "linked"
    subprocess.run(["git", "init", str(repo)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "baseline"], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-b", "ticket", str(worktree)],
        check=True,
        stdout=subprocess.DEVNULL,
    )

    roots = administrative_dirs(worktree)
    assert len(roots) == 2
    assert any("worktrees" in str(path) for path in roots)
    assert repo.joinpath(".git").resolve() in roots


def test_headless_host_task_complete_is_validation_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_workflow import agent_context as context_module
    from agent_workflow import completion as completion_module

    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    monkeypatch.setattr(context_module, "bridge_available", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(context_module, "bridge_required", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        context_module,
        "read",
        lambda *_args, **_kwargs: {"worker_mode": "headless", "state": "busy"},
    )
    monkeypatch.setattr(
        context_module,
        "read_status",
        lambda *_args, **_kwargs: {"workdir": str(tmp_path)},
    )
    monkeypatch.setattr(context_module, "authoritative_execution_status", lambda *_args: "running")
    monkeypatch.setattr(
        completion_module,
        "validate_completion_handoff",
        lambda *_args, **_kwargs: {"validation_status": "valid"},
    )

    result = context_module.complete_task(
        settings,
        "run-1",
        actor="worker",
        summary="done",
    )
    assert result["outcome"] == "not_required"
    assert result["completion_validation_status"] == "valid"


def test_finalize_treats_process_result_plus_live_runner_as_convergence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_workflow import finalization as finalization_module

    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    run = settings.state_root / "runs" / "run-1"
    run.mkdir(parents=True)
    monkeypatch.setattr(finalization_module, "RUNNER_CONVERGENCE_SECONDS", 0.0)
    monkeypatch.setattr(
        finalization_module,
        "synchronize_projection",
        lambda *_args, **_kwargs: {"agent_run_id": "run-1", "status": "running"},
    )
    monkeypatch.setattr(finalization_module, "_already_finalized", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(finalization_module, "read_agent_run_contract", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(finalization_module, "_heartbeat_pids", lambda *_args, **_kwargs: (101, 202))
    monkeypatch.setattr(finalization_module, "process_sample", lambda _pid: {"alive": True})
    monkeypatch.setattr(
        finalization_module,
        "_json_object",
        lambda path: {"returncode": 0, "exit_code": 0} if path.name == "process-result.json" else {},
    )
    monkeypatch.setattr(finalization_module, "authoritative_execution_status", lambda *_args: "running")

    result = finalization_module.finalize_run(settings, "run-1")
    assert result["outcome"] == "runner_converging"
    assert result["process_result_present"] is True


def test_restart_prepares_headless_retry_without_start_and_binds_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib
    import json

    from agent_workflow import agent_runs as runs_module

    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    prior = settings.state_root / "runs" / "prior-run"
    prior.mkdir(parents=True)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("original ticket\n", encoding="utf-8")
    context_file = tmp_path / "retry.md"
    context_file.write_text("correct the prior completion evidence\n", encoding="utf-8")
    argv = ["codex", "exec", "-"]
    digest = hashlib.sha256(
        json.dumps(argv, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    contract = {
        "agent_run": {
            "agent_name": "agent-01",
            "agent_class": "implementation",
            "tier": "low",
        },
        "pack": {"id": None, "root": None},
        "worktree": {"path": str(tmp_path)},
        "prompt": {"source": str(prompt), "sha256": hashlib.sha256(prompt.read_bytes()).hexdigest()},
        "worker_plan": {"argv": argv, "command_sha256": digest, "mode": "headless"},
        "runtime_policy": {"no_go_authorized": False, "codex_reasoning_effort": "medium"},
        "evaluation_policy": {"path": None},
        "ticket": "P0-00",
    }
    command = {
        "argv": argv,
        "model": None,
        "stream_format": "text",
        "executor": "codex",
    }
    captured: dict[str, object] = {}
    starts: list[str] = []

    monkeypatch.setattr(runs_module, "_child_lifecycle_control", lambda _id: None)
    monkeypatch.setattr(runs_module, "read_agent_run_contract", lambda _path: contract)
    monkeypatch.setattr(runs_module, "authoritative_execution_status", lambda _path: "failed")
    monkeypatch.setattr(runs_module, "read_contract", lambda *_args, **_kwargs: command)

    def fake_prepare(_settings, **kwargs):
        captured.update(kwargs)
        return {
            "agent_run_id": kwargs["agent_run_id"],
            "worker_mode": "headless",
            "status": "prepared",
        }

    monkeypatch.setattr(runs_module, "prepare", fake_prepare)
    monkeypatch.setattr(
        runs_module,
        "start",
        lambda _settings, run_id: starts.append(run_id) or {"agent_run_id": run_id, "status": "running"},
    )

    result = runs_module.restart(
        settings,
        "prior-run",
        "retry-run",
        retry_context_path=context_file,
    )
    assert result["status"] == "prepared"
    assert starts == []
    assert captured["retry_of"] == "prior-run"
    assert captured["retry_context"] == "correct the prior completion evidence\n"


def test_bridged_headless_task_complete_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_workflow import agent_context as context_module

    context = {
        "agent_run_id": "run-1",
        "worker_mode": "headless",
        "interactive": False,
        "state": "busy",
        "current_assignment": {
            "assignment_id": "assignment-1",
            "ticket_id": "P1-00",
            "pack_id": "pack",
        },
    }
    monkeypatch.setattr(context_module, "_read_json", lambda _path: dict(context))
    monkeypatch.setattr(
        context_module,
        "_append_event",
        lambda *_args, **_kwargs: {"timestamp": "2026-09-19T00:00:00+00:00"},
    )
    monkeypatch.setattr(context_module, "atomic_write_json", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(context_module, "append_lifecycle_event", lambda *_args, **_kwargs: None)

    result = context_module.apply_bridged_completion(
        tmp_path,
        "run-1",
        actor="worker",
        summary="completed",
    )
    assert result["state"] == "closed"
    assert result["completed_assignment"]["summary"] == "completed"
