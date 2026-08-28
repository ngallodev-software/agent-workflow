from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

from tests.conftest import REPO_ROOT


CURRENT_VERSION = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
CURRENT_TAG = f"v{CURRENT_VERSION}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fake_release(root: Path, *, bad_checksum: bool = False) -> tuple[Path, Path]:
    release = root / "release"
    release.mkdir()
    bundle_name = f"agent-workflow-{CURRENT_VERSION}-linux.tar.gz"
    wheel_name = f"agent_workflow-{CURRENT_VERSION}-py3-none-any.whl"
    staging = root / f"agent-workflow-{CURRENT_VERSION}-linux"
    staging.mkdir()
    (staging / "install.sh").write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$AGENT_WORKFLOW_BOOTSTRAP_TEST_MARKER\"\n",
        encoding="utf-8",
    )
    wheel = staging / wheel_name
    wheel.write_bytes(b"fake wheel")
    with tarfile.open(release / bundle_name, "w:gz") as archive:
        archive.add(staging, arcname=staging.name)
    manifest = release / "SHA256SUMS"
    bundle_digest = "0" * 64 if bad_checksum else _sha256(release / bundle_name)
    manifest.write_text(
        f"{bundle_digest}  {bundle_name}\n{_sha256(wheel)}  {wheel_name}\n",
        encoding="utf-8",
    )
    return release, wheel


def _run_bootstrap(release: Path, *args: str, marker: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "AGENT_WORKFLOW_RELEASE_BASE_URL": release.as_uri(),
            "AGENT_WORKFLOW_BOOTSTRAP_TEST_MARKER": str(marker),
        }
    )
    return subprocess.run(
        ["/bin/sh", "-s", "--", *args],
        cwd=REPO_ROOT,
        env=env,
        input=(REPO_ROOT / "install.sh").read_text(encoding="utf-8"),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_bootstrap_selects_tagged_bundle_and_verifies_checksum_offline(tmp_path: Path) -> None:
    release, _ = _write_fake_release(tmp_path)
    marker = tmp_path / "marker"
    result = _run_bootstrap(release, "--version", CURRENT_TAG, "--python", sys.executable, marker=marker)
    assert result.returncode == 0, result.stdout + result.stderr
    marker_args = marker.read_text(encoding="utf-8").splitlines()
    assert marker_args[-2] == "--wheel"
    assert Path(marker_args[-1]).name == f"agent_workflow-{CURRENT_VERSION}-py3-none-any.whl"


def test_bootstrap_stops_before_install_on_checksum_failure(tmp_path: Path) -> None:
    release, _ = _write_fake_release(tmp_path, bad_checksum=True)
    marker = tmp_path / "marker"
    result = _run_bootstrap(release, "--version", CURRENT_TAG, "--python", sys.executable, marker=marker)
    assert result.returncode != 0
    assert "checksum" in result.stderr.lower()
    assert not marker.exists()


def test_bootstrap_rejects_unsupported_host_before_download(tmp_path: Path) -> None:
    release, _ = _write_fake_release(tmp_path)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "uname").write_text(
        "#!/bin/sh\nif [ \"${1:-}\" = -m ]; then printf 'x86_64\\n'; else printf 'Plan9\\n'; fi\n",
        encoding="utf-8",
    )
    (fake_bin / "uname").chmod(0o755)
    env = os.environ.copy()
    env.update({"PATH": f"{fake_bin}:/usr/bin:/bin", "AGENT_WORKFLOW_RELEASE_BASE_URL": release.as_uri()})
    result = subprocess.run(
        ["/bin/sh", "-s", "--", "--version", CURRENT_TAG],
        cwd=REPO_ROOT,
        env=env,
        input=(REPO_ROOT / "install.sh").read_text(encoding="utf-8"),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "unsupported operating system" in result.stderr


def test_source_installer_migrates_codex_mcp_duplicates(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    config = codex / "config.toml"
    config.write_text(
        '[mcp_servers.other]\ncommand = "other"\n\n'
        '[mcp_servers.agent-workflow]\ncommand = "old"\n\n'
        '[mcp_servers.agent-workflow.env]\nOLD = "1"\n\n'
        '[mcp_servers."agent-workflow"]\ncommand = "older"\n',
        encoding="utf-8",
    )
    dist_info = tmp_path / "mcp-1.28.1.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text("Metadata-Version: 2.1\nName: mcp\nVersion: 1.28.1\n", encoding="utf-8")
    (tmp_path / "jsonschema.py").write_text("", encoding="utf-8")
    (tmp_path / "yaml.py").write_text("", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "CODEX_HOME": str(codex),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local/share"),
            "PYTHONPATH": str(tmp_path),
        }
    )
    command = [
        "bash",
        "scripts/install-source.sh",
        "--no-deps",
        "--no-skills",
        "--no-hooks",
        "--extras",
        "mcp",
        "--python",
        sys.executable,
    ]
    for _ in range(2):
        result = subprocess.run(command, cwd=REPO_ROOT, env=env, text=True, capture_output=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
    text = config.read_text(encoding="utf-8")
    assert "[mcp_servers.other]" in text
    assert text.count("[mcp_servers.agent-workflow]") == 1
    assert '[mcp_servers."agent-workflow"]' not in text
    assert text.count("BEGIN AGENT-WORKFLOW MANAGED MCP") == 1
    assert set(tomllib.loads(text)["mcp_servers"]) == {"other", "agent-workflow"}


def test_deployment_jenkins_install_skips_harness_mutations() -> None:
    jenkinsfile = (REPO_ROOT / "Jenkinsfile").read_text(encoding="utf-8")
    deployment = jenkinsfile.split('stage(\'Install built wheel\')', 1)[1]
    assert "--no-mcp-register --no-hooks --no-skills" in deployment
    assert 'install_python="$VENV/bin/python"' in deployment
    assert "sudo" not in deployment
    assert '"$WORKSPACE/install.sh"' in deployment


def test_release_workflow_is_tag_only_and_bundle_builder_is_reproducible(tmp_path: Path) -> None:
    workflow = (REPO_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "pull_request" not in workflow
    assert 'tags:' in workflow
    assert "gh release create \"$RELEASE_TAG\"" in workflow

    wheel = tmp_path / f"agent_workflow-{CURRENT_VERSION}-py3-none-any.whl"
    sdist = tmp_path / f"agent_workflow-{CURRENT_VERSION}.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    output = tmp_path / "dist"
    command = [
        sys.executable,
        "scripts/build-release-bundles.py",
        "--root",
        str(REPO_ROOT),
        "--version",
        CURRENT_TAG,
        "--wheel",
        str(wheel),
        "--sdist",
        str(sdist),
        "--output-dir",
        str(output),
    ]
    subprocess.run(command, cwd=REPO_ROOT, check=True, capture_output=True, text=True)
    first = {path.name: path.read_bytes() for path in output.glob("agent-workflow-*.tar.gz")}
    subprocess.run(command, cwd=REPO_ROOT, check=True, capture_output=True, text=True)
    second = {path.name: path.read_bytes() for path in output.glob("agent-workflow-*.tar.gz")}
    assert first == second
    assert set(first) == {
        f"agent-workflow-{CURRENT_VERSION}-linux.tar.gz",
        f"agent-workflow-{CURRENT_VERSION}-wsl2.tar.gz",
        f"agent-workflow-{CURRENT_VERSION}-macos.tar.gz",
    }
    with tarfile.open(output / f"agent-workflow-{CURRENT_VERSION}-macos.tar.gz", "r:gz") as archive:
        names = set(archive.getnames())
    assert f"agent-workflow-{CURRENT_VERSION}-macos/install.sh" in names
    assert f"agent-workflow-{CURRENT_VERSION}-macos/uninstall.sh" in names
    assert f"agent-workflow-{CURRENT_VERSION}-macos/agent_workflow-{CURRENT_VERSION}-py3-none-any.whl" in names
    forbidden = ("Jenkinsfile", "jenkins-local-job", "/.github/", ".github/workflows")
    assert not any(any(token in name for token in forbidden) for name in names)

def test_source_installer_canonicalizes_owned_hooks_on_reinstall(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex = home / ".codex"
    claude = home / ".claude"
    codex.mkdir(parents=True)
    claude.mkdir(parents=True)
    hooks_dir = home / ".local" / "share" / "agent-workflow" / "hooks"
    hooks_dir.mkdir(parents=True)

    owned = str(hooks_dir / "agent-workflow-run-reminder")
    unrelated = "/usr/local/bin/user-session-hook"
    codex_config = codex / "config.toml"
    duplicate_block = (
        "# agent-workflow managed reminder hooks\n"
        "[[hooks.SessionStart]]\n"
        "[[hooks.SessionStart.hooks]]\n"
        'type = "command"\n'
        f'command = "{owned}"\n'
        "# end agent-workflow managed reminder hooks\n"
    )
    codex_config.write_text(
        'user_setting = "keep"\n\n'
        + duplicate_block
        + "\n"
        + duplicate_block,
        encoding="utf-8",
    )

    claude_settings = claude / "settings.json"
    claude_settings.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": owned}]},
                        {
                            "hooks": [
                                {"type": "command", "command": owned},
                                {"type": "command", "command": unrelated},
                            ]
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    stale = hooks_dir / "obsolete-agent-workflow-hook"
    stale.write_text("#!/bin/sh\n", encoding="utf-8")
    # This name represents a formerly managed hook name; the source fixture
    # deliberately removes it so sync must delete the installed copy.
    stale_owned = hooks_dir / "codex-code-discovery-gate"
    stale_owned.write_text("#!/bin/sh\n", encoding="utf-8")

    fake_modules = tmp_path / "fake-modules"
    fake_modules.mkdir()
    (fake_modules / "jsonschema.py").write_text("", encoding="utf-8")
    (fake_modules / "yaml.py").write_text("", encoding="utf-8")

    # Use a copied source whose managed hook set no longer contains the gate,
    # simulating migration after a hook asset is retired.
    source = tmp_path / "source"
    shutil.copytree(REPO_ROOT, source, symlinks=True)
    (source / "scripts" / "hooks" / "codex-code-discovery-gate").unlink()

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "CODEX_HOME": str(codex),
            "CLAUDE_CONFIG_DIR": str(claude),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local/share"),
            "PYTHONPATH": str(fake_modules),
        }
    )
    command = [
        "bash",
        "scripts/install-source.sh",
        "--no-deps",
        "--no-skills",
        "--no-mcp-register",
        "--python",
        sys.executable,
    ]
    for _ in range(2):
        result = subprocess.run(
            command,
            cwd=source,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    codex_text = codex_config.read_text(encoding="utf-8")
    assert codex_text.count("# agent-workflow managed reminder hooks") == 1
    assert codex_text.count("# end agent-workflow managed reminder hooks") == 1
    assert 'user_setting = "keep"' in codex_text

    claude_data = json.loads(claude_settings.read_text(encoding="utf-8"))
    commands = [
        entry["command"]
        for group in claude_data["hooks"]["SessionStart"]
        for entry in group.get("hooks", [])
        if isinstance(entry, dict) and "command" in entry
    ]
    assert commands.count(str(hooks_dir / "agent-workflow-run-reminder")) == 1
    assert commands.count(str(hooks_dir / "rtk-session-reminder")) == 1
    assert commands.count(str(hooks_dir / "codebase-memory-session-reminder")) == 1
    assert commands.count(unrelated) == 1
    assert not stale_owned.exists()
    assert stale.exists()
