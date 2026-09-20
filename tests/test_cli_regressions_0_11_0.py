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
from agent_workflow.cli_runtime import parse_args
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


@pytest.mark.parametrize("flag", ["--json"])
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
    monkeypatch.setattr(
        delegation_module,
        "_delegation_result",
        lambda **kwargs: {"state": kwargs["state"], "agent_run_id": kwargs["agent_run_id"]},
    )

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


def test_explicit_agent_name_is_logical_identity_not_preferred_name_allowlist(
    tmp_path: Path,
) -> None:
    settings = replace(
        defaults(tmp_path / "config.toml"),
        state_root=tmp_path / "state",
        preferred_agent_names=("luna-01", "luna-02"),
    )
    identity = resolve_agent_identity(
        settings,
        requested_name="terra",
        requested_role=None,
        requested_class="review",
        executor="codex",
        model=LUNA_MODEL,
        reasoning_effort="medium",
        allow_no_go_model=False,
        explicit_command=None,
        interactive=False,
    )
    assert identity.agent_name == "terra"
    assert identity.agent_class == "review"
    assert identity.model == LUNA_MODEL


def test_role_runtime_override_error_points_to_operator_compatibility_path(
    tmp_path: Path,
) -> None:
    settings = replace(
        defaults(tmp_path / "config.toml"),
        state_root=tmp_path / "state",
    )
    with pytest.raises(
        Exception,
        match="omit --role and use the matching --agent-class",
    ):
        resolve_agent_identity(
            settings,
            requested_name=None,
            requested_role="review",
            requested_class=None,
            executor="codex",
            model=LUNA_MODEL,
            reasoning_effort="medium",
            allow_no_go_model=False,
            explicit_command=None,
            interactive=False,
        )


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


def test_agent_verify_accepts_cwd_after_run_id_before_separator() -> None:
    parser = build_parser(command_scope="agent")
    args = parse_args(
        parser,
        [
            "agent",
            "verify",
            "run-1",
            "--cwd",
            "/tmp/worktree",
            "--timeout",
            "30",
            "--",
            "python",
            "-c",
            "raise SystemExit(0)",
        ],
    )
    assert args.agent_run_id == "run-1"
    assert args.cwd == Path("/tmp/worktree")
    assert args.timeout == 30
    assert args.argv == ["python", "-c", "raise SystemExit(0)"]


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
        criteria=(
            {"id": "P0-AC-01", "description": "The deterministic protocol is used."},
            {"id": "P0-AC-02", "description": None},
        ),
        command_artifacts={"role": "implementation"},
        dirty_at_launch=True,
        dirty_authorized=True,
        retry_context="Use pass/fail/not_verified and preserve the approved baseline drift.",
    )
    text = launch.read_text(encoding="utf-8")
    assert "Operator-approved source drift" in text
    assert "do not mark the task blocked merely because the baseline is dirty" in text
    assert "## Operator retry context" in text
    assert "pass|fail|not_verified" in text
    assert "agent complete AGENT_RUN_ID" in text
    assert "## Machine-readable acceptance criteria" in text
    assert "`P0-AC-01`" in text
    assert "rejects unknown IDs" in text


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


def test_legacy_worker_completion_commands_are_removed() -> None:
    parser = build_parser(command_scope="agent")
    subcommands = next(
        action.choices for action in parser._actions if hasattr(action, "choices") and action.choices
        if "agent" in action.choices
    )["agent"]
    command_action = next(action for action in subcommands._actions if hasattr(action, "choices") and action.choices)
    assert "task-complete" not in command_action.choices
    assert "completion-validate" not in command_action.choices


def test_terminal_assignment_close_is_host_owned_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_workflow import agent_context as context_module

    context = {
        "agent_run_id": "run-1",
        "state": "busy",
        "current_assignment": {
            "assignment_id": "assignment-1",
            "ticket_id": "P1-00",
            "pack_id": "pack",
        },
        "completed_assignment": None,
    }
    stored = dict(context)
    monkeypatch.setattr(context_module, "_read_json", lambda _path: dict(stored))
    monkeypatch.setattr(
        context_module,
        "_append_event",
        lambda *_args, **_kwargs: {"timestamp": "2026-09-19T00:00:00+00:00"},
    )
    monkeypatch.setattr(
        context_module,
        "atomic_write_json",
        lambda _path, value, **_kwargs: stored.update(value),
    )
    monkeypatch.setattr(context_module, "append_lifecycle_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(context_module, "append_message", lambda *_args, **_kwargs: None)

    first = context_module.close_terminal_assignment(tmp_path, "run-1")
    assert first["state"] == "closed"
    assert first["completed_assignment"]["summary"] == "terminal completion evidence collected"
    second = context_module.close_terminal_assignment(tmp_path, "run-1")
    assert second["state"] == "closed"


def test_unexpected_failure_diagnostic_is_schema_shaped_and_redacted(tmp_path: Path) -> None:
    import json
    import subprocess

    from agent_workflow.contracts import validate_instance
    from agent_workflow.unexpected_failures import record_unexpected_failure

    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    try:
        raise subprocess.CalledProcessError(
            7,
            ["tool", "--token", "secret-token"],
            output="authorization=secret-token output",
            stderr="token=secret-token failure at /tmp/example",
        )
    except subprocess.CalledProcessError as exc:
        result = record_unexpected_failure(
            exc,
            settings=settings,
            argv=["agent-run", "start", "run-1", "--token", "secret-token"],
            top_level="agent-run",
        )
    value = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    validate_instance(value, "agent-workflow/unexpected-failure/v1", artifact=result["path"])
    serialized = json.dumps(value)
    assert "secret-token" not in serialized
    assert value["exception"]["type"] == "CalledProcessError"
    assert value["exception"]["details"]["returncode"] == 7
    assert value["traceback"]
    assert value["traceback"][-1]["path"].endswith("test_cli_regressions_0_11_0.py")


def test_cli_unexpected_failure_prints_locator_and_persists_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import json
    from agent_workflow import cli as cli_module

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state-home"))
    monkeypatch.setattr(
        cli_module,
        "bootstrap_plugins",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("diagnostic boom")),
    )
    assert cli_module.main(["doctor"]) == 1
    error = capsys.readouterr().err
    assert "correlation ID" in error
    assert "diagnostic:" in error
    diagnostics = list((tmp_path / "state-home" / "agent-workflow" / "diagnostics" / "unexpected").glob("*.json"))
    assert len(diagnostics) == 1
    value = json.loads(diagnostics[0].read_text(encoding="utf-8"))
    assert value["exception"]["type"] == "RuntimeError"
    assert value["exception"]["message"] == "diagnostic boom"


def test_version_boundary_is_0_11_0() -> None:
    from agent_workflow import __version__

    assert __version__ == "0.11.0"


def test_worker_criterion_parser_rejects_free_form_enum() -> None:
    parser = build_parser(command_scope="agent")
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["agent", "criterion", "run-1", "criterion-1", "verified", "--evidence", "ok"]
        )
    args = parser.parse_args(
        ["agent", "criterion", "run-1", "criterion-1", "pass", "--evidence", "ok"]
    )
    assert args.result == "pass"


def test_worker_command_catalog_prefers_deterministic_completion_api() -> None:
    from agent_workflow.command_catalog import _PROFILE_COMMANDS

    allowed = _PROFILE_COMMANDS["implementation"]
    assert {"agent criterion", "agent verify", "agent complete", "agent completion-status"} <= allowed
    assert "agent completion-validate" not in allowed
    assert "agent task-complete" not in allowed


def test_worker_complete_derives_protocol_fields_and_schema_validates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    import subprocess

    from agent_workflow import worker_completion as worker_module

    repo = tmp_path / "repo"
    handoff = repo / ".agent-workflow-handoff" / "run-1"
    handoff.mkdir(parents=True)
    subprocess.run(["git", "init", str(repo)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True, stdout=subprocess.DEVNULL)
    base = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "commit", "-am", "change"], check=True, stdout=subprocess.DEVNULL)
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()

    contract = {
        "agent_run": {"id": "run-1"},
        "ticket": "P0-00",
        "ticket_identity": {"mode": "explicit", "value": "P0-00"},
        "pack": {"id": "pack-1"},
        "worktree": {"path": str(repo), "source_revision": base},
        "paths": {"handoff_dir": str(handoff)},
    }
    draft = {
        "schema": worker_module.DRAFT_SCHEMA,
        "agent_run_id": "run-1",
        "state": "open",
        "criteria": [{"id": "criterion-1", "result": "pass", "evidence": ["verified by test"]}],
        "commands": [{"argv": ["true"], "cwd": str(repo), "exit_code": 0, "receipt": "exit=0"}],
        "created_at": "2026-09-19T00:00:00+00:00",
        "updated_at": "2026-09-19T00:00:00+00:00",
    }
    (handoff / worker_module.DRAFT_NAME).write_text(json.dumps(draft), encoding="utf-8")
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    monkeypatch.setattr(
        worker_module,
        "_context",
        lambda *_args, **_kwargs: (tmp_path / "state" / "runs" / "run-1", contract, repo, handoff),
    )

    result = worker_module.complete(settings, "run-1", result="completed")
    value = json.loads((handoff / "completion.json").read_text(encoding="utf-8"))
    assert result["state"] == "finalized"
    assert value["agent_run_id"] == "run-1"
    assert value["ticket_id"] == "P0-00"
    assert value["pack_id"] == "pack-1"
    assert value["base_revision"] == base
    assert value["head_revision"] == head
    assert value["changed_files"] == ["a.txt"]
    assert value["criteria"][0]["result"] == "pass"


def test_worker_complete_refuses_completed_with_failed_observed_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    import subprocess

    from agent_workflow import worker_completion as worker_module

    repo = tmp_path / "repo"
    handoff = repo / ".agent-workflow-handoff" / "run-1"
    handoff.mkdir(parents=True)
    subprocess.run(["git", "init", str(repo)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True, stdout=subprocess.DEVNULL)
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    contract = {
        "agent_run": {"id": "run-1"}, "ticket": None,
        "ticket_identity": {"mode": "omitted", "value": None}, "pack": {"id": None},
        "worktree": {"path": str(repo), "source_revision": head},
        "paths": {"handoff_dir": str(handoff)},
    }
    draft = {
        "schema": worker_module.DRAFT_SCHEMA, "agent_run_id": "run-1", "state": "open",
        "criteria": [{"id": "criterion-1", "result": "pass", "evidence": ["inspection"]}],
        "commands": [{"argv": ["npm", "run", "build"], "cwd": str(repo), "exit_code": 127, "receipt": "exit=127"}],
        "created_at": "2026-09-19T00:00:00+00:00", "updated_at": "2026-09-19T00:00:00+00:00",
    }
    (handoff / worker_module.DRAFT_NAME).write_text(json.dumps(draft), encoding="utf-8")
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    monkeypatch.setattr(worker_module, "_context", lambda *_a, **_k: (tmp_path / "state", contract, repo, handoff))
    with pytest.raises(Exception, match="cannot hide commands\\[0\\] exit_code 127"):
        worker_module.complete(settings, "run-1", result="completed")
    assert not (handoff / "completion.json").exists()


def test_repo_local_execution_config_is_auto_discovered_and_merged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_workflow.cli_runtime import bootstrap_plugins

    xdg_config = tmp_path / "config"
    global_config = xdg_config / "agent-workflow" / "config.toml"
    global_config.parent.mkdir(parents=True)
    state_root = tmp_path / "state"
    global_config.write_text(
        "schema_version = 1\n[paths]\nstate_root = " + repr(str(state_root)) + "\n",
        encoding="utf-8",
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    prompt = repo / "ticket.md"
    prompt.write_text("review\n", encoding="utf-8")
    local = repo / ".agent-workflow-execution.toml"
    local.write_text(
        "schema_version = 1\n[agents]\npreferred_names = ['terra-p4']\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))

    settings, _ = bootstrap_plugins(
        ["agent-run", "prepare", "p4-review", str(repo), str(prompt)],
        load_plugins=False,
    )
    assert settings.state_root == state_root.resolve()
    assert settings.preferred_agent_names == ("terra-p4",)
    assert settings.config_path == local.resolve()
    assert settings.config_sources == (global_config.resolve(), local.resolve())


def test_repo_local_execution_config_cannot_override_security_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_workflow.cli_runtime import bootstrap_plugins
    from agent_workflow.errors import WorkflowError

    xdg_config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
    repo = tmp_path / "repo"
    repo.mkdir()
    prompt = repo / "ticket.md"
    prompt.write_text("review\n", encoding="utf-8")
    (repo / ".agent-workflow-execution.toml").write_text(
        "schema_version = 1\n[security]\nmode = 'local'\n",
        encoding="utf-8",
    )
    with pytest.raises(WorkflowError, match="non-execution section"):
        bootstrap_plugins(
            ["agent-run", "prepare", "p4-review", str(repo), str(prompt)],
            load_plugins=False,
        )


def test_worker_criterion_can_bind_host_receipt_by_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    from agent_workflow import worker_completion as worker_module

    repo = tmp_path / "repo"
    repo.mkdir()
    handoff = tmp_path / "state" / "runs" / "run-1" / "handoff"
    handoff.mkdir(parents=True)
    receipt = repo / "GITHUB_PROMOTION_RECEIPT.md"
    receipt.write_text("before -> after\n", encoding="utf-8")
    contract = {
        "agent_run": {"id": "run-1"},
        "worktree": {"path": str(repo)},
        "paths": {"handoff_dir": str(handoff)},
    }
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    monkeypatch.setattr(
        worker_module,
        "_context",
        lambda *_a, **_k: (tmp_path / "state" / "runs" / "run-1", contract, repo, handoff),
    )
    result = worker_module.record_criterion(
        settings,
        "run-1",
        criterion_id="github-metadata-receipt",
        result="pass",
        evidence=[],
        evidence_files=[Path("GITHUB_PROMOTION_RECEIPT.md")],
    )
    digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
    assert result["criterion"]["evidence"] == [
        f"file:GITHUB_PROMOTION_RECEIPT.md#sha256={digest};bytes={receipt.stat().st_size}"
    ]


def test_review_limitation_is_non_gating_for_receipt_based_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    import subprocess

    from agent_workflow import worker_completion as worker_module

    repo = tmp_path / "repo"
    handoff = tmp_path / "state" / "runs" / "review-1" / "handoff"
    handoff.mkdir(parents=True)
    subprocess.run(["git", "init", str(repo)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True, stdout=subprocess.DEVNULL)
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    contract = {
        "agent_run": {"id": "review-1"},
        "ticket": "P4-01",
        "ticket_identity": {"mode": "explicit", "value": "P4-01"},
        "pack": {"id": "portfolio"},
        "worktree": {"path": str(repo), "source_revision": head},
        "paths": {"handoff_dir": str(handoff)},
    }
    draft = {
        "schema": worker_module.DRAFT_SCHEMA,
        "agent_run_id": "review-1",
        "state": "open",
        "criteria": [{"id": "host-receipt", "result": "pass", "evidence": ["receipt digest verified"]}],
        "limitations": [{"id": "live-github-fetch", "result": "not_verified", "evidence": ["controlled DNS unavailable"]}],
        "commands": [{"argv": ["true"], "cwd": str(repo), "exit_code": 0, "receipt": "exit=0"}],
        "created_at": "2026-09-19T00:00:00+00:00",
        "updated_at": "2026-09-19T00:00:00+00:00",
    }
    (handoff / worker_module.DRAFT_NAME).write_text(json.dumps(draft), encoding="utf-8")
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    monkeypatch.setattr(
        worker_module,
        "_context",
        lambda *_a, **_k: (tmp_path / "state" / "runs" / "review-1", contract, repo, handoff),
    )
    result = worker_module.complete(
        settings,
        "review-1",
        result="completed",
        review_disposition="approved",
    )
    completion = json.loads((handoff / "completion.json").read_text(encoding="utf-8"))
    assert result["review_disposition"] == "approved"
    assert completion["limitations"][0]["result"] == "not_verified"


def test_limitation_command_has_no_free_form_result_enum() -> None:
    parser = build_parser(command_scope="agent")
    args = parser.parse_args(
        ["agent", "limitation", "run-1", "browser-launch", "--evidence", "EPERM"]
    )
    assert args.agent_command == "limitation"
    assert not hasattr(args, "result")


def test_accept_revision_is_derived_from_sealed_completion() -> None:
    from agent_workflow.lifecycle import _acceptance_revision

    parser = build_parser(command_scope="agent-run")
    args = parser.parse_args(
        ["agent-run", "accept", "run-1", "--actor", "host", "--reason", "reviewed"]
    )
    assert not hasattr(args, "revision")
    assert _acceptance_revision({"head_revision": "abc123"}) == "abc123"

def test_prerequisite_policy_names_are_closed() -> None:
    from agent_workflow.errors import WorkflowError
    from agent_workflow.preflight import prerequisite_policy

    assert prerequisite_policy("accepted").name == "accepted"
    assert prerequisite_policy("sealed_completed").name == "sealed_completed"
    with pytest.raises(WorkflowError, match="prerequisite requirement must be one of"):
        prerequisite_policy("reviewed-ish")


def test_new_handoff_boundary_is_outside_source_checkout(tmp_path: Path) -> None:
    from agent_workflow.agent_run_artifacts import _create_handoff_dir

    repo = tmp_path / "repo"
    repo.mkdir()
    state_dir = tmp_path / "state" / "runs" / "run-1"
    state_dir.mkdir(parents=True)
    handoff = _create_handoff_dir(state_dir, "run-1")
    assert handoff == (state_dir / "handoff").resolve()
    assert not (repo / ".agent-workflow-handoff").exists()


def test_assignment_transition_table_rejects_out_of_order_completion() -> None:
    from agent_workflow import agent_context as context_module
    from agent_workflow.errors import WorkflowError

    assert context_module._assignment_next_state("busy", "task_completed") == "closed"
    with pytest.raises(WorkflowError, match="not allowed"):
        context_module._assignment_next_state("closed", "task_completed")


def test_agent_verify_separator_reaches_verification_argv() -> None:
    from agent_workflow.cli_runtime import parse_args

    parser = build_parser(command_scope="agent")
    args = parse_args(
        parser,
        ["agent", "verify", "run-1", "--", "npm", "ci", "--ignore-scripts"],
    )
    assert args.argv == ["npm", "ci", "--ignore-scripts"]
    assert args.explicit_command is None



def test_prompt_pack_task_criteria_are_machine_readable_and_duplicate_safe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from agent_workflow import manifests as manifests_module

    monkeypatch.setattr(
        manifests_module,
        "load_pack_manifest",
        lambda _root: {
            "phases": [
                {
                    "tasks": [
                        {
                            "id": "P0-00",
                            "criteria": [
                                {"id": "AC-01", "description": "First"},
                                {"id": "AC-02"},
                            ],
                        }
                    ]
                }
            ]
        },
    )
    assert manifests_module.task_criteria(tmp_path, "P0-00") == (
        {"id": "AC-01", "description": "First"},
        {"id": "AC-02", "description": None},
    )

    monkeypatch.setattr(
        manifests_module,
        "load_pack_manifest",
        lambda _root: {
            "phases": [
                {"tasks": [{"id": "P0-00", "criteria": [{"id": "AC-01"}, {"id": "AC-01"}]}]}
            ]
        },
    )
    with pytest.raises(Exception, match="duplicate criterion ID"):
        manifests_module.task_criteria(tmp_path, "P0-00")


def test_worker_criterion_rejects_id_outside_launch_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_workflow import worker_completion as worker_module
    from agent_workflow.errors import WorkflowError

    repo = tmp_path / "repo"
    repo.mkdir()
    handoff = tmp_path / "handoff"
    handoff.mkdir()
    state_dir = tmp_path / "state" / "runs" / "run-1"
    state_dir.mkdir(parents=True)
    contract = {
        "agent_run": {"id": "run-1"},
        "criteria": [{"id": "AC-01", "description": "Only criterion"}],
    }
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    monkeypatch.setattr(
        worker_module,
        "_context",
        lambda *_a, **_k: (state_dir, contract, repo, handoff),
    )

    with pytest.raises(WorkflowError, match="not declared by this ticket"):
        worker_module.record_criterion(
            settings,
            "run-1",
            criterion_id="made-up",
            result="pass",
            evidence=["looks good"],
        )

    recorded = worker_module.record_criterion(
        settings,
        "run-1",
        criterion_id="AC-01",
        result="pass",
        evidence=["verified"],
    )
    assert recorded["criterion"]["id"] == "AC-01"


def test_worker_complete_rejects_omitted_declared_criteria(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_workflow import worker_completion as worker_module
    from agent_workflow.errors import WorkflowError

    repo = tmp_path / "repo"
    repo.mkdir()
    handoff = tmp_path / "handoff"
    handoff.mkdir()
    state_dir = tmp_path / "state" / "runs" / "run-1"
    state_dir.mkdir(parents=True)
    contract = {
        "agent_run": {"id": "run-1"},
        "criteria": [
            {"id": "AC-01", "description": None},
            {"id": "AC-02", "description": None},
        ],
    }
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    monkeypatch.setattr(
        worker_module,
        "_context",
        lambda *_a, **_k: (state_dir, contract, repo, handoff),
    )
    worker_module.record_criterion(
        settings,
        "run-1",
        criterion_id="AC-01",
        result="pass",
        evidence=["done"],
    )
    with pytest.raises(WorkflowError, match="AC-02"):
        worker_module.complete(settings, "run-1", result="completed")

    state = worker_module.status(settings, "run-1")
    assert state["missing_criteria"] == ["AC-02"]
    assert [item["id"] for item in state["expected_criteria"]] == ["AC-01", "AC-02"]


def test_launch_contract_criterion_catalog_rejects_duplicates() -> None:
    from agent_workflow.contracts import validate_criteria_catalog
    from agent_workflow.errors import WorkflowError

    validate_criteria_catalog({"criteria": [{"id": "AC-01"}, {"id": "AC-02"}]})
    with pytest.raises(WorkflowError, match="duplicate criterion ID"):
        validate_criteria_catalog({"criteria": [{"id": "AC-01"}, {"id": "AC-01"}]})


def test_terminal_outcome_rules_are_shared_and_fail_invalid_completion() -> None:
    from agent_workflow.terminal_pipeline import TerminalObservation, derive_terminal_outcome

    exit_zero_invalid = derive_terminal_outcome(
        TerminalObservation(executor_result="completed", exit_code=0),
        completion_result="invalid",
        policy_result="passed",
    )
    assert exit_zero_invalid.status == "failed"
    assert exit_zero_invalid.exit_code == 1
    assert exit_zero_invalid.failure_category == "completion_invalid"
    assert exit_zero_invalid.acceptance_eligible is False

    valid_but_budget_failed = derive_terminal_outcome(
        TerminalObservation(executor_result="completed", exit_code=0),
        completion_result="valid",
        policy_result="failed",
    )
    assert valid_but_budget_failed.status == "completed"
    assert valid_but_budget_failed.acceptance_eligible is False

    interrupted = derive_terminal_outcome(
        TerminalObservation(executor_result="interrupted", exit_code=143),
        completion_result="valid",
        policy_result="passed",
    )
    assert interrupted.status == "interrupted"
    assert interrupted.exit_code == 143


def test_terminal_outcome_collection_failure_is_not_process_success() -> None:
    from agent_workflow.terminal_pipeline import TerminalObservation, derive_terminal_outcome

    outcome = derive_terminal_outcome(
        TerminalObservation(executor_result="completed", exit_code=0),
        completion_result="valid",
        policy_result="passed",
        evidence_errors=["collectors: scope read failed"],
    )
    assert outcome.status == "failed"
    assert outcome.exit_code == 1
    assert outcome.failure_category == "terminal_collection_failed"
