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
        "git pull --ff-only",
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

def test_git_pull_all_leaves_authentication_to_git() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'git -C "$source" pull --ff-only' in text
    for forbidden in (
        "GIT_ASKPASS",
        "GIT_TERMINAL_PROMPT",
        "GCM_INTERACTIVE",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "gh auth token",
        "credential.helper",
        "remote set-url",
    ):
        assert forbidden not in text


def test_specgen_pull_is_explicitly_opt_in() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "WITH_SPECGEN=0" in text
    assert "--with-specgen) WITH_SPECGEN=1" in text
    assert 'SPECGEN_SOURCE=""' in text
    assert 'if [[ "$WITH_SPECGEN" -eq 1 ]]; then' in text
    assert 'pull_repo "specgen" "$SPECGEN_SOURCE"' in text
    assert "optional and excluded unless --with-specgen is supplied." in text


def test_specgen_source_implies_specgen_pull() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    block = text[text.index("--specgen-source)") : text.index("--benchmark-source)")]
    assert 'SPECGEN_SOURCE="$1"' in block
    assert "WITH_SPECGEN=1" in block
