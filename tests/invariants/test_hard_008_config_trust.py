from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from agent_workflow.compatibility import probe_executor
from agent_workflow.config import as_dict, load_settings, trust_report
from agent_workflow.errors import WorkflowError
from agent_workflow.process import EnvironmentPolicy, build_environment


def test_config_schema_rejects_unknown_policy_keys(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("schema_version = 1\nunknown_policy = true\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match=r"unknown config key\(s\) in \[root\]"):
        load_settings(path)


def test_governed_config_fails_on_group_world_write_and_local_reports_warning(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.toml"
    path.write_text("schema_version = 1\n[security]\nmode = \"local\"\n", encoding="utf-8")
    path.chmod(0o664)
    local = load_settings(path)
    assert trust_report(local)["warnings"]
    path.write_text("schema_version = 1\n[security]\nmode = \"governed\"\n", encoding="utf-8")
    path.chmod(0o666)
    with pytest.raises(WorkflowError, match="untrusted configuration file"):
        load_settings(path)


def test_config_symlink_is_rejected_without_following(tmp_path: Path) -> None:
    target = tmp_path / "target.toml"
    target.write_text("schema_version = 1\n", encoding="utf-8")
    link = tmp_path / "config.toml"
    link.symlink_to(target)
    with pytest.raises(WorkflowError, match="symlink config"):
        load_settings(link)


def test_missing_policy_file_warns_locally_and_fails_governed(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'schema_version = 1\n[security]\nmode = "local"\npolicy_files = ["missing-policy.toml"]\n',
        encoding="utf-8",
    )
    local = load_settings(path)
    report = trust_report(local)
    assert report["ok"] is True
    assert any(item["label"] == "policy file" for item in report["warnings"])

    path.write_text(
        'schema_version = 1\n[security]\nmode = "governed"\npolicy_files = ["missing-policy.toml"]\n',
        encoding="utf-8",
    )
    with pytest.raises(WorkflowError, match="untrusted policy file"):
        load_settings(path)


def test_custom_executor_is_explicitly_unclassified_and_git_env_is_fixed() -> None:
    decision = probe_executor("custom", [sys.executable], digest=True)
    assert decision["decision"] == "unclassified"
    assert decision["explanation_code"] == "COMPAT-CUSTOM-EXECUTOR"
    assert decision["executable"]["resolved_path"] == os.path.realpath(sys.executable)
    environment, policy, _ = build_environment(["git"], EnvironmentPolicy())
    assert policy == "controlled"
    assert environment["GIT_PAGER"] == "cat"
    assert environment["GIT_EXTERNAL_DIFF"] == ""
    assert "SSH_AUTH_SOCK" not in environment


def test_config_show_redacts_secret_like_executor_arguments(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'schema_version = 1\n[executors.secret]\ncommand = ["tool", "--api-key", "SYNTHETIC-CONFIG-SECRET"]\n',
        encoding="utf-8",
    )
    shown = as_dict(load_settings(path))
    assert "SYNTHETIC-CONFIG-SECRET" not in str(shown)
