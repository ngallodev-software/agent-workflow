from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_workflow.benchmarking import auth
from agent_workflow.benchmarking.auth import (
    FORBIDDEN_API_MODE,
    SUBSCRIPTION_MODE,
    preflight_authentication,
    validate_authentication_config,
)
from agent_workflow.benchmarking.metrics import aggregate_usage, normalize_usage
from agent_workflow.benchmarking.policy import apply_operating_policy, load_operating_policy
from agent_workflow.benchmarking.planning import create_run_plan
from agent_workflow.config import defaults
from agent_workflow.benchmarking.runner import execute_pair
from agent_workflow.benchmarking.runtime import validate_runtime_lock
from agent_workflow.benchmarking.service import export_builtin_suite
from agent_workflow.benchmarking.statistics import paired_bootstrap_interval
from agent_workflow.errors import WorkflowError
from agent_workflow.process import run


def _builtin_suite(tmp_path: Path) -> Path:
    destination = tmp_path / "priority-picker-v1"
    export_builtin_suite(destination, benchmark_id="priority-picker-v1")
    return destination


def _executor(*, provider: str = "openai", mode: str = SUBSCRIPTION_MODE) -> dict[str, object]:
    credential = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
    return {
        "provider": provider,
        "executor": "codex-cli" if provider == "openai" else "claude-code-cli",
        "environment_allowlist": ["HOME"],
        "authentication": {
            "mode": mode,
            "status_argv": ["provider", "auth", "status"],
            "status_timeout_seconds": 5,
            "credential_environment": [credential],
        },
    }


def test_process_stdin_delivery_is_bounded_and_repeatable() -> None:
    for value in ("first", "second", "third"):
        result = run(["cat"], input_text=value, timeout_seconds=5)
        assert result.stdout == value
        assert result.stderr == ""
        assert result.returncode == 0


def test_subscription_session_is_default_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    class Result:
        returncode = 0
        stdout = "Logged in using ChatGPT"
        stderr = ""
        argv = ("provider", "auth", "status")

        @staticmethod
        def as_dict(*, include_output: bool = True) -> dict[str, object]:
            return {"returncode": 0, "include_output": include_output}

    monkeypatch.setattr(auth, "run", lambda *args, **kwargs: Result())
    evidence = preflight_authentication(_executor())
    assert evidence["authenticated"] is True
    assert evidence["requested_mode"] == SUBSCRIPTION_MODE
    assert evidence["observed_mode"] == SUBSCRIPTION_MODE
    assert evidence["credential_environment_present"] == []


def test_subscription_session_refuses_ambient_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    evidence = preflight_authentication(_executor())
    assert evidence["authenticated"] is False
    assert evidence["observed_mode"] == FORBIDDEN_API_MODE
    assert "refused" in evidence["detail"]
    assert "must-not-be-used" not in json.dumps(evidence)



def test_anthropic_status_does_not_treat_provider_as_pro_subscription() -> None:
    assert auth._classify_status("anthropic", '{"provider":"anthropic","authenticated":true}') is None
    assert auth._classify_status("anthropic", '{"subscriptionType":"pro"}') == SUBSCRIPTION_MODE

def test_subscription_cost_is_not_mislabeled_as_provider_billed() -> None:
    billing = {
        "mode": "subscription",
        "provider_billed_cost_semantics": "not-attributable",
        "subscription_allocation": {"method": "fixed-per-arm-run", "amount": 12.5},
    }
    usage = normalize_usage(
        {
            "input_tokens": 1000,
            "output_tokens": 200,
            "total_tokens": 1200,
            "cost": 0.012,
        },
        currency="USD",
        price_catalog_id="catalog-v1",
        source="test",
        billing=billing,
        pricing={
            "input_tokens_include_cached": True,
            "usd_per_million_tokens": {
                "input": 10,
                "cached_input": 1,
                "cache_write_input": 10,
                "output": 20,
                "reasoning_output": 20,
            },
        },
    )
    assert usage["provider_billed_cost"] is None
    assert usage["local_estimated_cost"] == 0.014
    assert usage["provider_billed_cost_semantics"] == "not-attributable"
    aggregate = aggregate_usage([usage], billing=billing)
    assert aggregate["provider_billed_cost"] is None
    assert aggregate["subscription_allocated_cost"] == 12.5


def test_paired_bootstrap_is_deterministic() -> None:
    first = paired_bootstrap_interval([1, 2, 3, 4], label="same-run", samples=500)
    second = paired_bootstrap_interval([1, 2, 3, 4], label="same-run", samples=500)
    assert first == second
    assert first["n"] == 4
    assert first["lower"] <= first["mean"] <= first["upper"]  # type: ignore[operator]


def test_publication_runtime_requires_content_addressed_browser_and_fonts() -> None:
    lock = {
        "schema": "agent-workflow/visual-runtime-lock/v1",
        "reproducibility_state": "development-host-detected",
        "playwright_version": "1.57.0",
        "browser_product": "chromium",
        "browser_version": "unknown",
        "browser_executable_candidates": ["/usr/bin/chromium"],
        "font_manifest": [{"family": "DejaVu Sans", "resolved_file": "DejaVuSans.ttf", "sha256": None}],
        "container_image": None,
    }
    validate_runtime_lock(lock, claim_level="development")
    with pytest.raises(WorkflowError, match="content-addressed"):
        validate_runtime_lock(lock, claim_level="publication")


def test_pair_level_infrastructure_retry_selects_fresh_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_workflow.benchmarking import runner

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    plan = {
        "run_id": "retry-run",
        "benchmark_id": "priority-picker-v1",
        "coordinator": {"run_dir": str(run_dir)},
    }
    pair = {
        "pair_id": "case-r01",
        "case_id": "case",
        "repetition": 1,
        "base_revision": "a" * 40,
        "fixture_sha256": "b" * 64,
        "task_prompt_sha256": "c" * 64,
        "input_bundle_sha256": "d" * 64,
        "environment_sha256": "e" * 64,
        "tool_policy_sha256": "f" * 64,
        "resource_policy_sha256": "1" * 64,
        "attempts": [
            {"attempt": 1, "attempt_id": "case-r01-a01", "arms": {}},
            {"attempt": 2, "attempt_id": "case-r01-a02", "arms": {}},
        ],
    }
    observed: list[int] = []

    def fake_attempt(_plan, _pair, attempt):
        observed.append(attempt["attempt"])
        number = attempt["attempt"]
        evidence = run_dir / f"attempt-{number}.json"
        evidence.write_text("{}\n", encoding="utf-8")
        return {
            "attempt": number,
            "attempt_id": attempt["attempt_id"],
            "state": "infrastructure_failed" if number == 1 else "terminal",
            "pair_nonce_sha256": str(number) * 64,
            "pair_wall_seconds": 1.0,
            "pair_start_skew_seconds": 0.01,
            "pair_sum_arm_wall_seconds": 2.0,
            "pair_critical_path_seconds": 1.0,
            "arms": {"control_raw": "left.json", "workflow_full": "right.json"},
            "completed_at": "2026-08-01T00:00:00+00:00",
            "evidence": str(evidence),
        }

    monkeypatch.setattr(runner, "_execute_attempt", fake_attempt)
    monkeypatch.setattr(runner, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "validate_value", lambda *args, **kwargs: None)
    result = execute_pair(plan, pair)
    assert observed == [1, 2]
    assert result["selected_attempt"] == 2
    assert result["infrastructure_retry_count"] == 1
    assert [item["state"] for item in result["attempts"]] == ["infrastructure_failed", "terminal"]


def test_internal_policy_rejects_synthetic_authentication(tmp_path: Path) -> None:
    suite = _builtin_suite(tmp_path)
    policy = load_operating_policy(suite / "policies" / "internal.json")
    spec = json.loads((suite / "benchmark-spec.json").read_text(encoding="utf-8"))
    with pytest.raises(WorkflowError, match="not allowed by operating policy"):
        apply_operating_policy(spec, policy, authentication_mode="synthetic-none")


def test_publication_policy_requires_twenty_eligible_pairs(tmp_path: Path) -> None:
    suite = _builtin_suite(tmp_path)
    policy = load_operating_policy(suite / "policies" / "publication.json")
    assert policy["repetitions"] == 20
    assert policy["winner_policy"]["minimum_eligible_pairs"] == 20
    assert policy["winner_policy"]["confidence_level"] == 0.95
    assert policy["authentication_default"] == "subscription-session"
    assert policy["allowed_authentication_modes"] == ["subscription-session"]


def test_internal_policy_rejects_command_line_overrides(tmp_path: Path) -> None:
    suite = _builtin_suite(tmp_path)
    settings = replace(
        defaults(tmp_path / "config.toml"),
        worktree_root=tmp_path / "worktrees",
        state_root=tmp_path / "state",
    )
    with pytest.raises(WorkflowError, match="may not be overridden"):
        create_run_plan(
            settings,
            spec_path=suite / "benchmark-spec.json",
            executor_path=suite / "executors" / "synthetic.json",
            repo=tmp_path / "unused",
            base_ref="HEAD",
            repetitions=2,
            policy_path=suite / "policies" / "internal.json",
        )
