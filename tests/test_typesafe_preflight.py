from dataclasses import replace

import pytest

from agent_workflow import agent_runs
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError


def test_typesafe_enabled_requires_runtime_key(monkeypatch, tmp_path):
    settings = replace(defaults(tmp_path / "config.toml"), plugins_enabled=("agent-workflow-typesafe",), typesafe_env_file=tmp_path / "typesafe.env")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(agent_runs, "distribution_version", lambda _: "0.1.1")
    with pytest.raises(WorkflowError, match=r"source .*typesafe\.env"):
        agent_runs._require_typesafe_environment(settings)


def test_typesafe_runtime_key_allows_prepare_gate(monkeypatch, tmp_path):
    settings = replace(defaults(tmp_path / "config.toml"), plugins_enabled=("agent-workflow-typesafe",), typesafe_env_file=tmp_path / "typesafe.env")
    monkeypatch.setenv("TYPESAFE_API_KEY", "redacted-test-value")
    monkeypatch.setattr(agent_runs, "distribution_version", lambda _: "0.1.1")
    agent_runs._require_typesafe_environment(settings)
