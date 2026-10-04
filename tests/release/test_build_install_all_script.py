from __future__ import annotations

from pathlib import Path
import os
import subprocess

from tests.conftest import REPO_ROOT


SCRIPT = REPO_ROOT / "scripts" / "build-install-all.sh"


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_build_install_all_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], cwd=REPO_ROOT, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_build_install_all_help_documents_stack_and_sources() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"], cwd=REPO_ROOT, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    for option in (
        "--venv PATH",
        "--contracts-source PATH",
        "--comparative-eval-source PATH",
        "--specgen-source PATH",
        "--benchmark-source PATH",
        "--verify-only",
        "--no-pull",
        "--pull-only",
        "--allow-dirty-pull",
    ):
        assert option in result.stdout
    assert "resolved dynamically from each source checkout" in result.stdout
    assert "repo == wheel == installed" in result.stdout


def test_build_install_all_is_existing_venv_wheel_only() -> None:
    text = _text()
    assert "python -m venv" not in text
    assert "pip install --user" not in text
    assert "pip install -e" not in text
    assert "--no-deps --force-reinstall" in text
    assert '"$PYTHON" -m build --wheel --no-isolation' in text


def test_local_component_versions_are_not_hard_coded() -> None:
    text = _text()
    # Local versions must come from the source checkout after pull/re-exec.
    for name in (
        "EXPECTED_CONTRACTS_VERSION",
        "EXPECTED_AGENT_WORKFLOW_VERSION",
        "EXPECTED_COMPARATIVE_EVAL_VERSION",
        "EXPECTED_SPECGEN_VERSION",
        "EXPECTED_BENCHMARK_VERSION",
    ):
        assert f'{name}="$(resolve_source_version ' in text
    assert 'EXPECTED_COMPARATIVE_EVAL_VERSION="0.3.1"' not in text
    assert 'EXPECTED_COMPARATIVE_EVAL_VERSION="0.3.4"' not in text
    assert "resolve_source_version()" in text
    assert 'source / "VERSION"' in text
    assert 'source / "pyproject.toml"' in text


def test_third_party_runtime_versions_remain_explicitly_frozen() -> None:
    text = _text()
    assert 'EXPECTED_TYPESAFE_VERSION="0.6.0"' in text
    assert 'EXPECTED_INSPECT_AI_VERSION="0.3.268"' in text
    assert 'EXPECTED_INSPECT_SWE_VERSION="0.2.71"' in text


def test_repo_venv_alignment_is_reported_before_build_and_strictly_verified() -> None:
    text = _text()
    report = text.index("report_repo_venv_versions")
    build = text.index("build_wheel()")
    assert report < build
    assert "metadata.version(name)" in text
    assert 'state="match" if installed==repo_version else "mismatch; will reinstall"' in text
    assert "installed {observed}; repo/runtime expects {version}" in text
    verify_only = text.index('if [[ "$VERIFY_ONLY" -eq 1 ]]')
    assert "verify_stack" in text[verify_only : verify_only + 250]


def test_build_install_all_validates_wheel_metadata_against_source_version() -> None:
    text = _text()
    assert ".dist-info/METADATA" in text
    assert "if observed != expected" in text
    for wheel in (
        "CONTRACTS_WHEEL",
        "AGENT_WORKFLOW_WHEEL",
        "COMPARATIVE_EVAL_WHEEL",
        "SPECGEN_WHEEL",
        "BENCHMARK_WHEEL",
    ):
        assert f'{wheel}="$(build_wheel ' in text


def test_build_install_all_uses_required_dependency_order() -> None:
    text = _text()
    installs = [
        'install_wheel specgen-agent-workflow-contracts',
        'install_wheel agent-workflow "$AGENT_WORKFLOW_WHEEL"',
        'install_wheel agent-workflow-comparative-eval',
        'install_wheel specgen "$SPECGEN_WHEEL"',
        'install_wheel agent-workflow-benchmark',
    ]
    positions = [text.index(item) for item in installs]
    assert positions == sorted(positions)


def test_build_install_all_records_source_provenance() -> None:
    text = _text()
    assert "write_source_provenance" in text
    assert "source-provenance.json" in text
    assert "agent-workflow/source-provenance/v1" in text
    assert '"git","-C",str(source),"rev-parse"' in text
    assert '"git","-C",str(source),"status"' in text
    assert '"version":version' in text
    assert '"revision":revision' in text


def test_build_install_all_writes_comparative_plugin_config() -> None:
    text = _text()
    assert 'enabled = ["agent-workflow-spec", "agent-workflow-benchmark"]' in text
    assert 'provider = "typesafe"' in text
    assert "typesafe-api-calls.jsonl" in text
    assert 'mode = "comparative"' in text
    assert "TYPESAFE_API_KEY" in text
    assert 'settings.executors.get("codex",[None])[0] != "codex"' in text
    assert '"agent-workflow-comparative-eval"' in text


def test_build_install_all_pulls_stack_before_build_and_reexecs() -> None:
    text = _text()
    assert 'bash "$ROOT/scripts/git-pull-all.sh"' in text
    assert 'exec bash "$ROOT/scripts/build-install-all.sh" --no-pull' in text
    assert "--pull-only" in text
    assert "--allow-dirty-pull" in text
    assert text.index('bash "$ROOT/scripts/git-pull-all.sh"') < text.index("resolve_source_version()")


def test_build_install_all_verify_only_disables_pull() -> None:
    assert '--verify-only) VERIFY_ONLY=1; NO_PULL=1' in _text()


def test_build_install_all_handles_unset_venv_without_unbound_variable(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("AGENT_WORKFLOW_VENV", None)
    env.pop("VIRTUAL_ENV", None)
    env.pop("TYPESAFE_API_KEY", None)
    env["PATH"] = "/usr/bin:/bin"
    result = subprocess.run(
        ["bash", str(SCRIPT), "--verify-only"], cwd=tmp_path, text=True, capture_output=True, check=False, env=env
    )
    assert "unbound variable" not in result.stderr.lower()


def test_build_install_all_does_not_override_git_authentication() -> None:
    text = _text()
    for forbidden in (
        "ALLOW_CREDENTIAL_HELPER",
        "--allow-credential-helper",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "GIT_ASKPASS",
        "credential.helper",
    ):
        assert forbidden not in text
