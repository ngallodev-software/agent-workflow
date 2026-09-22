from __future__ import annotations

from pathlib import Path
import subprocess

from tests.conftest import REPO_ROOT


SCRIPT = REPO_ROOT / "scripts" / "git-pull-all.sh"


def test_git_pull_all_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_git_pull_all_documents_safe_update_contract() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    text = result.stdout
    for value in (
        "--contracts-source PATH",
        "--comparative-eval-source PATH",
        "--specgen-source PATH",
        "--benchmark-source PATH",
        "--allow-dirty",
        "--allow-credential-helper",
        "git pull --ff-only",
        "GH_TOKEN/GITHUB_TOKEN",
        "credential helpers disabled",
        "never switches branches",
    ):
        assert value in text


def test_git_pull_all_fails_closed_without_destructive_git_operations() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'git -C "$source" pull --ff-only' in text
    assert "status --porcelain=v1" in text
    assert "symbolic-ref --quiet --short HEAD" in text
    assert "rev-parse --abbrev-ref --symbolic-full-name '@{u}'" in text
    assert "before=" in text
    assert "after=" in text
    for forbidden in (
        "git checkout",
        "git switch",
        "git reset",
        "git stash",
        "git clean",
        "pull --rebase",
    ):
        assert forbidden not in text


def test_agent_workflow_is_pulled_last_for_safe_reexec() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    positions = [
        text.rindex('pull_repo "contracts"'),
        text.rindex('pull_repo "comparative-eval"'),
        text.rindex('pull_repo "specgen"'),
        text.rindex('pull_repo "benchmark"'),
        text.rindex('pull_repo "agent-workflow"'),
    ]
    assert positions == sorted(positions)


def test_git_pull_all_uses_nonpersistent_github_https_auth_by_default() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "GIT_TERMINAL_PROMPT=0" in text
    assert "GCM_INTERACTIVE=Never" in text
    assert "GIT_ASKPASS" in text
    assert "GIT_CONFIG_KEY_0=credential.helper" in text
    assert "GIT_CONFIG_VALUE_0=" in text
    assert "GH_TOKEN" in text
    assert "GITHUB_TOKEN" in text
    assert "gh auth token --hostname github.com" in text
    assert "remote set-url" not in text
    assert "git credential approve" not in text
    assert "git credential reject" not in text
    assert "credential.helper store" not in text
    assert "credential.helper cache" not in text
