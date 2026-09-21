from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT


PY_SCRIPT = REPO_ROOT / "scripts" / "build-install-all.py"
SH_SCRIPT = REPO_ROOT / "scripts" / "build-install-all.sh"


def test_build_install_all_help_documents_shared_stack() -> None:
    result = subprocess.run(
        [sys.executable, str(PY_SCRIPT), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    for option in (
        "--venv",
        "--contracts-source",
        "--comparative-eval-source",
        "--specgen-source",
        "--benchmark-source",
        "--verify-only",
    ):
        assert option in result.stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is unavailable")
def test_build_install_all_shell_wrapper_has_valid_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SH_SCRIPT)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_build_install_all_is_existing_venv_only_and_comparative() -> None:
    text = PY_SCRIPT.read_text(encoding="utf-8")
    assert "no existing shared virtualenv found" in text
    assert "TYPESAFE_API_KEY is required before build/install" in text
    assert 'provider = "typesafe"' in text
    assert 'mode = "comparative"' in text
    assert 'enabled = ["agent-workflow-benchmark", "agent-workflow-spec"]' in text
    assert "typesafe-sdk==0.6.0" in text
    assert "agent-workflow-comparative-eval" in text
    assert "agent-workflow-spec-contracts" in text
    assert "specgen-aw" in text
    assert "agent-workflow-benchmark" in text
    assert 'Path(str(codex_argv[0])).name != "codex"' in text
    assert "agent-workflow-codex" not in text
    assert '"-m", "venv"' not in text


def test_build_install_all_uses_project_installers_and_local_wheels() -> None:
    text = PY_SCRIPT.read_text(encoding="utf-8")
    contracts = text.index('source=sources["contracts"]')
    comparative = text.index('source=sources["comparative_eval"]')
    core = text.index('ROOT / "scripts" / "build-install.sh"')
    specgen = text.index('source=sources["specgen"]')
    benchmark = text.index('sources["benchmark"] / "scripts" / "build-install.sh"')
    assert contracts < comparative < core < specgen < benchmark
    assert '"--no-deps"' in text
    assert '"--force-reinstall"' in text
    assert '"--json", "spec", "compatibility"' in text


def test_build_install_all_wrapper_targets_python_orchestrator() -> None:
    text = SH_SCRIPT.read_text(encoding="utf-8")
    assert "build-install-all.py" in text
