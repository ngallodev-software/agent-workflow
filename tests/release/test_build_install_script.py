from __future__ import annotations

from pathlib import Path
import os
import subprocess

from tests.conftest import REPO_ROOT


SCRIPT = REPO_ROOT / "scripts" / "build-install.sh"


def test_build_install_script_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_build_install_script_documents_active_venv_and_verify_mode() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    normalized = " ".join(result.stdout.split())
    assert "active" in normalized.lower()
    assert "VIRTUAL_ENV" in normalized
    assert "--venv PATH" in normalized
    assert "--verify-only" in normalized
    assert "never installs to the user Python environment" in normalized


def test_build_install_script_is_wheel_only_and_does_not_call_source_installer() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"$PYTHON" -m build --wheel' in text
    assert '"$PYTHON" -m pip install --no-deps --force-reinstall "$WHEEL"' in text
    assert "scripts/install-source.sh" not in text
    assert "./install.sh" not in text
    assert "--user" not in text
    assert "$HOME/.local/bin" not in text


def test_build_install_script_verifies_schema_and_editable_cleanup() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'venv / "share" / "agent-workflow" / "schemas"' in text
    assert "core install unexpectedly owns benchmark schemas" in text
    assert "__editable__.agent_workflow-*.pth" in text
    assert "__editable___agent_workflow_*_finder.py" in text
    assert "Agent-Workflow is still installed editable" in text
    assert "\\${" not in text


def test_build_install_script_handles_unset_venv_environment(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("AGENT_WORKFLOW_VENV", None)
    env.pop("VIRTUAL_ENV", None)
    env["PATH"] = "/usr/bin:/bin"

    result = subprocess.run(
        ["bash", str(SCRIPT), "--verify-only"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert "unbound variable" not in result.stderr.lower()
    assert "AGENT_WORKFLOW_VENV" not in result.stderr


def test_build_install_script_uses_dev_environment_helper() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'source "$ROOT/scripts/dev-env.sh"' in text
    assert 'aw_dev_env_on "$VENV"' in text
    assert "TYPESAFE_API_KEY" in text
    assert "agent-workflow-comparative-eval" in text
