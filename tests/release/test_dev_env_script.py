from __future__ import annotations

from pathlib import Path
import os
import subprocess

from tests.conftest import REPO_ROOT


SCRIPT = REPO_ROOT / "scripts" / "dev-env.sh"


def _make_fake_venv(path: Path) -> None:
    (path / "bin").mkdir(parents=True)
    python = path / "bin" / "python"
    python.write_text("#!/usr/bin/env bash\nexec python3 \"$@\"\n", encoding="utf-8")
    python.chmod(0o755)
    aw = path / "bin" / "agent-workflow"
    aw.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    aw.chmod(0o755)


def test_dev_env_script_has_valid_bash_syntax() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert '[[ -v ' not in text
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_dev_env_on_and_off_restore_shell_environment(tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    _make_fake_venv(venv)
    home = tmp_path / "home"
    source_config = home / ".config" / "agent-workflow" / "config.toml"
    source_config.parent.mkdir(parents=True)
    source_config.write_text(
        "schema_version = 1\n\n"
        "[paths]\n"
        'worktree_root = "~/.local/share/agent-workflow/worktrees"\n'
        'state_root = "~/.local/state/agent-workflow"\n\n'
        "[decision_policy]\n"
        'mode = "comparative"\n'
        'profile = "default"\n',
        encoding="utf-8",
    )

    command = (
        "set -euo pipefail\n"
        f"export HOME={home}\n"
        "export PATH=/usr/bin:/bin\n"
        "unset VIRTUAL_ENV AGENT_WORKFLOW_VENV AGENT_WORKFLOW_BIN XDG_CONFIG_HOME XDG_STATE_HOME XDG_DATA_HOME\n"
        f"source {SCRIPT} on {venv}\n"
        "printf 'ON:%s|%s|%s|%s\\n' \"$VIRTUAL_ENV\" \"$XDG_CONFIG_HOME\" \"$XDG_STATE_HOME\" \"$XDG_DATA_HOME\"\n"
        f"source {SCRIPT} off\n"
        "printf 'OFF:%s|%s|%s\\n' \"${VIRTUAL_ENV-unset}\" \"${XDG_CONFIG_HOME-unset}\" \"$PATH\"\n"
    )
    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "HOME": str(home), "PATH": "/usr/bin:/bin"},
    )

    assert result.returncode == 0, result.stderr
    assert f"ON:{venv}|" in result.stdout
    assert f"{venv}/.xdg/config" in result.stdout
    assert f"{venv}/.xdg/state" in result.stdout
    assert f"{venv}/.xdg/data" in result.stdout
    assert "OFF:unset|unset|/usr/bin:/bin" in result.stdout

    dev_config = venv / ".xdg" / "config" / "agent-workflow" / "config.toml"
    text = dev_config.read_text(encoding="utf-8")
    assert f'worktree_root = "{venv}/.xdg/data/agent-workflow/worktrees"' in text
    assert f'state_root = "{venv}/.xdg/state/agent-workflow"' in text
    assert 'mode = "comparative"' in text


def test_dev_env_script_must_be_sourced() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "on"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "must be sourced" in result.stderr
