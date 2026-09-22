from __future__ import annotations

from pathlib import Path
import os
import subprocess

from tests.conftest import REPO_ROOT


SCRIPT = REPO_ROOT / "scripts" / "build-install-all.sh"


def test_build_install_all_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_build_install_all_help_documents_stack_and_sources() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    text = result.stdout
    for option in (
        "--venv PATH",
        "--contracts-source PATH",
        "--comparative-eval-source PATH",
        "--specgen-source PATH",
        "--benchmark-source PATH",
        "--verify-only",
    ):
        assert option in text
    for version in ("0.2.1", "0.11.5", "0.1.0", "0.2.4", "0.2.9", "0.6.0"):
        assert version in text


def test_build_install_all_is_existing_venv_wheel_only() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "python -m venv" not in text
    assert "virtualenv" not in text.lower() or "existing virtualenv" in text.lower()
    assert "pip install --user" not in text
    assert "-m pip install --user" not in text
    assert "pip install -e" not in text
    assert "--no-deps --force-reinstall" in text
    assert "python -m build" not in text
    assert '"$PYTHON" -m build --wheel --no-isolation' in text


def test_build_install_all_uses_required_dependency_order() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    installs = [
        'install_wheel "specgen-agent-workflow-contracts"',
        'install_wheel "agent-workflow" "$AGENT_WORKFLOW_WHEEL"',
        'install_wheel "agent-workflow-comparative-eval"',
        'install_wheel "specgen" "$SPECGEN_WHEEL"',
        'install_wheel "agent-workflow-benchmark"',
    ]
    positions = [text.index(item) for item in installs]
    assert positions == sorted(positions)


def test_build_install_all_writes_comparative_plugin_config() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'enabled = ["agent-workflow-spec", "agent-workflow-benchmark"]' in text
    assert 'provider = "typesafe"' in text
    assert "api_call_log" in text
    assert "typesafe-api-calls.jsonl" in text
    assert 'mode = "comparative"' in text
    assert "TYPESAFE_API_KEY" in text
    assert 'settings.executors.get("codex", [None])[0] != "codex"' in text
    assert "agent-workflow-codex wrapper may not be used" in text
    assert '"agent-workflow-comparative-eval"' in text


def test_build_install_all_requires_exact_stack_versions() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    expected = {
        "EXPECTED_CONTRACTS_VERSION": "0.2.1",
        "EXPECTED_AGENT_WORKFLOW_VERSION": "0.11.5",
        "EXPECTED_COMPARATIVE_EVAL_VERSION": "0.1.0",
        "EXPECTED_SPECGEN_VERSION": "0.2.4",
        "EXPECTED_BENCHMARK_VERSION": "0.2.9",
        "EXPECTED_TYPESAFE_VERSION": "0.6.0",
    }
    for name, version in expected.items():
        assert f'{name}="{version}"' in text


def test_build_install_all_handles_unset_venv_without_unbound_variable(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("AGENT_WORKFLOW_VENV", None)
    env.pop("VIRTUAL_ENV", None)
    env.pop("TYPESAFE_API_KEY", None)
    env["PATH"] = "/usr/bin:/bin"

    result = subprocess.run(
        ["bash", str(SCRIPT), "--verify-only"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert "unbound variable" not in result.stderr.lower()


def test_build_install_all_verify_only_does_not_rewrite_config() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    verify_body = text.split("verify_stack() {", 1)[1].split(
        '\n}\n\nif [[ "$VERIFY_ONLY" -eq 1 ]]', 1
    )[0]
    assert "write_stack_config" not in verify_body

    verify_only_block = text.split('if [[ "$VERIFY_ONLY" -eq 1 ]]; then', 1)[1].split(
        "fi", 1
    )[0]
    assert "verify_stack" in verify_only_block
    assert "write_stack_config" not in verify_only_block

    last_install = text.index(
        'install_wheel "agent-workflow-benchmark" "$BENCHMARK_WHEEL"'
    )
    config_write = text.index("write_stack_config", last_install)
    final_verify = text.index("verify_stack", config_write)
    assert last_install < config_write < final_verify
