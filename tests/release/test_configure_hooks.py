from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from tests.conftest import REPO_ROOT


def _configure_hooks_module():
    path = REPO_ROOT / "scripts" / "configure-hooks.py"
    spec = importlib.util.spec_from_file_location("configure_hooks", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_codex_configuration_collapses_historical_managed_blocks(tmp_path: Path) -> None:
    module = _configure_hooks_module()
    config = tmp_path / "config.toml"
    block = module.render_codex_hooks(Path("/hooks"), "")
    config.write_text(f"[projects]\n\n{block}\n\n{block}\n", encoding="utf-8")

    module.configure_codex(config, Path("/hooks"), "")
    module.configure_codex(config, Path("/hooks"), "")
    text = config.read_text(encoding="utf-8")
    assert text.count("# agent-workflow managed reminder hooks") == 1
    assert text.count("# end agent-workflow managed reminder hooks") == 1
    assert text.count("/hooks/rtk-session-reminder") == 1


def test_claude_configuration_collapses_duplicates_across_matching_groups(tmp_path: Path) -> None:
    module = _configure_hooks_module()
    settings = tmp_path / "settings.json"
    command = "/hooks/agent-workflow-run-reminder"
    settings.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": command}]},
                        {"hooks": [{"type": "command", "command": command}]},
                    ],
                    "PreToolUse": [
                        {"matcher": "Read|Grep|Glob", "hooks": []},
                        {"matcher": "Read|Grep|Glob", "hooks": []},
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    module.configure_claude(settings, Path("/hooks"), "/hooks/codex-code-discovery-gate")
    module.configure_claude(settings, Path("/hooks"), "/hooks/codex-code-discovery-gate")
    data = json.loads(settings.read_text(encoding="utf-8"))
    session = data["hooks"]["SessionStart"]
    assert sum(h.get("command") == command for group in session for h in group["hooks"]) == 1
    pretool = data["hooks"]["PreToolUse"]
    assert sum(
        h.get("command") == "/hooks/codex-code-discovery-gate"
        for group in pretool
        for h in group["hooks"]
    ) == 1


def test_source_installer_removes_stale_hook_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(
        REPO_ROOT,
        source,
        ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    (source / "scripts" / "hooks" / "rtk-session-reminder").unlink()
    home = tmp_path / "home"
    hook_data = home / ".local" / "share" / "agent-workflow" / "hooks"
    hook_data.mkdir(parents=True)
    stale = hook_data / "rtk-session-reminder"
    stale.write_text("stale\n", encoding="utf-8")
    unrelated = hook_data / "obsolete-hook"
    unrelated.write_text("user-owned\n", encoding="utf-8")
    fake_modules = tmp_path / "fake-modules"
    fake_modules.mkdir()
    (fake_modules / "jsonschema.py").write_text("", encoding="utf-8")
    (fake_modules / "yaml.py").write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "HOME": str(home),
        "CODEX_HOME": str(home / ".codex"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "PYTHONPATH": str(fake_modules),
        "AGENT_WORKFLOW_SOURCE_ROOT": str(source),
    }
    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "install-source.sh"),
            "--no-deps",
            "--no-skills",
            "--python",
            sys.executable,
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not stale.exists()
    assert unrelated.exists()
    assert (hook_data / "agent-workflow-run-reminder").is_file()


def test_source_installer_uses_one_shared_skill_root(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(
        REPO_ROOT,
        source,
        ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    home = tmp_path / "home"
    codex = home / ".codex"
    legacy_agents = home / ".agents" / "skills"
    legacy_claude = home / ".claude" / "skills"
    for root in (codex / "skills", legacy_agents, legacy_claude):
        root.mkdir(parents=True)
    target = str(source / "skills" / "agent-workflow-orchestrator")
    for root in (legacy_agents, legacy_claude):
        (root / "agent-workflow-orchestrator").symlink_to(target)
    unrelated = legacy_agents / "user-skill"
    unrelated.symlink_to(source / "skills" / "agent-workflow")

    fake_modules = tmp_path / "fake-modules"
    fake_modules.mkdir()
    (fake_modules / "jsonschema.py").write_text("", encoding="utf-8")
    (fake_modules / "yaml.py").write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "HOME": str(home),
        "CODEX_HOME": str(codex),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "PYTHONPATH": str(fake_modules),
        "AGENT_WORKFLOW_SOURCE_ROOT": str(source),
    }
    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "install-source.sh"),
            "--no-deps",
            "--no-hooks",
            "--no-mcp-register",
            "--python",
            sys.executable,
        ],
        cwd=source,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (codex / "skills" / "agent-workflow-orchestrator").is_symlink()
    assert not (legacy_agents / "agent-workflow-orchestrator").exists()
    assert not (legacy_claude / "agent-workflow-orchestrator").exists()
    assert unrelated.is_symlink()
    manifest = json.loads((home / ".local" / "share" / "agent-workflow" / "installed-harnesses.json").read_text())
    assert manifest == {
        "schema": "agent-workflow/installed-harnesses/v1",
        "harnesses": ["codex"],
    }
