from __future__ import annotations

import hashlib
import json
import shlex
import shutil
import subprocess
import tomllib
from pathlib import Path

from tests.conftest import InstalledProduct, REPO_ROOT, fake_agent_path, git_repo, wait_for_status


def test_installed_cli_exposes_operable_public_surface(
    installed_product: InstalledProduct, product_env: dict[str, str]
) -> None:
    expected_version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    version = installed_product.run("--version", env=product_env, check=True)
    assert version.stdout.strip() == f"agent-workflow {expected_version}"

    help_result = installed_product.run("--help", env=product_env, check=True)
    for command in ("doctor", "launch", "workflow", "eval", "pack", "worktree"):
        assert command in help_result.stdout
    launch_help = installed_product.run("launch", "--help", env=product_env, check=True)
    launch_help_text = " ".join(launch_help.stdout.split())
    assert "explicitly opt into a non-interactive structured evidence run" in launch_help_text
    assert "pane-limit-action" in launch_help.stdout

    doctor = installed_product.json("doctor", env=product_env)
    assert doctor["version"] == expected_version
    assert doctor["checks"]["required_commands_present"] is True
    assert doctor["commands"]["tmux"].endswith("/tmux")

    config = installed_product.json("config", "show", env=product_env)
    assert config["terminal"]["backend"] == "tmux"
    assert Path(config["paths"]["state_root"]).is_absolute()


def test_pane_capacity_fallback_is_structured_and_non_interactive(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Inspect the repository.\n", encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text(
        "\n".join(
            [
                "[executors.codex]",
                f'command = ["{fake_agent_path}"]',
                'models = ["gpt-5.4-mini"]',
                'default_model = "gpt-5.4-mini"',
                'model_arg = ["--model"]',
                "",
                "[git]",
                "require_clean_source = false",
                "",
                "[agents]",
                'default_executor = "codex"',
                'default_class = "implementation"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    env = dict(product_env)
    env.update(
        {
            "TMUX": "fake-server",
            "TMUX_PANE": "%0",
            "FAKE_TMUX_AGENT_COUNT": "6",
            "FAKE_AGENT_MODE": "structured",
        }
    )
    installed_product.json(
        "launch",
        "capacity-fallback",
        repo,
        prompt,
        "--config",
        config,
        "--executor",
        "codex",
        "--agent-class",
        "implementation",
        "--pane-limit-action",
        "non-interactive",
        env=env,
    )
    status = wait_for_status(env, "capacity-fallback")
    assert status["status"] == "completed"
    run = Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / "capacity-fallback"
    contract = json.loads((run / "launch-contract.json").read_text(encoding="utf-8"))
    assert contract["command_plan"]["interactive"] is False
    assert contract["command_plan"]["executor_interactive"] is False
    assert contract["command_plan"]["stream_format"] == "codex-jsonl"


def test_prompt_pack_scaffold_validate_and_archive_round_trip_is_deterministic(
    installed_product: InstalledProduct, product_env: dict[str, str], tmp_path: Path
) -> None:
    pack = tmp_path / "release-pack"
    scaffold = installed_product.json(
        "pack", "scaffold", pack, "--phases", "2", "--name", "Release Pack", env=product_env
    )
    assert scaffold["phases"] == 2
    assert (pack / "phase-0" / "task-manifest.yaml").is_file()
    assert not (pack / "MANIFEST.sha256").exists()

    validation = installed_product.json("pack", "validate", pack, env=product_env)
    assert validation["ok"] is True

    first = tmp_path / "first.tar.zst"
    second = tmp_path / "second.tar.zst"
    installed_product.json("pack", "archive", pack, first, env=product_env)
    installed_product.json("pack", "archive", pack, second, env=product_env)
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
    subprocess.run(["zstd", "-t", "-q", str(first)], check=True)


def test_worktree_create_list_and_remove_uses_real_git(
    installed_product: InstalledProduct, product_env: dict[str, str], tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    head = git_repo(repo)
    destination = tmp_path / "ticket-worktree"

    created = installed_product.json(
        "worktree", "create", repo, "TICKET-1", "HEAD", "--dest", destination, env=product_env
    )
    assert created["base_revision"] == head
    assert destination.is_dir()

    listed = installed_product.json("worktree", "list", repo, env=product_env)
    assert any(Path(item["worktree"]) == destination for item in listed)

    removed = installed_product.json(
        "worktree", "remove", repo, destination, "--delete-branch", env=product_env
    )
    assert removed["branch_deleted"] is True
    assert not destination.exists()


def test_source_installer_round_trip_preserves_user_owned_paths(
    product_env: dict[str, str], tmp_path: Path
) -> None:
    home = tmp_path / "install-home"
    env = dict(product_env)
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": "",
        }
    )
    (home / ".codex").mkdir(parents=True)
    (home / ".codex" / "config.toml").write_text('model = "keep-me"\n', encoding="utf-8")
    cbm_gate = home / ".codex" / "hooks" / "cbm-code-discovery-gate"
    cbm_gate.parent.mkdir()
    cbm_gate.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
    cbm_gate.chmod(0o700)
    (home / ".claude.json").write_text('{"userSetting": "keep-me"}\n', encoding="utf-8")
    (home / ".claude").mkdir()
    (home / ".claude" / "settings.json").write_text(
        '{"permissions": {"mode": "acceptEdits"}}\n', encoding="utf-8"
    )

    def run(script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(REPO_ROOT / script), "--no-deps", "--extras", "mcp"]
            if script == "install.sh"
            else [str(REPO_ROOT / script)],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )

    first = run("install.sh")
    assert first.returncode == 0, first.stdout + first.stderr
    launcher = home / ".local" / "bin" / "agent-workflow"
    assert launcher.resolve() == (REPO_ROOT / "bin" / "agent-workflow").resolve()
    assert (home / ".config" / "agent-workflow" / "config.toml").is_file()
    codex_config = tomllib.loads((home / ".codex" / "config.toml").read_text(encoding="utf-8"))
    assert codex_config["model"] == "keep-me"
    codex_server = codex_config["mcp_servers"]["agent-workflow"]
    assert Path(codex_server["command"]).name == "python3"
    assert codex_server["args"][-1] == str(REPO_ROOT)
    codex_hook_commands = [
        entry["hooks"][0]["command"] for entry in codex_config["hooks"]["SessionStart"]
    ]
    assert len(codex_hook_commands) == 3
    assert all(Path(command).is_file() for command in codex_hook_commands)
    codex_pre_tool_use = codex_config["hooks"]["PreToolUse"]
    assert [group["matcher"] for group in codex_pre_tool_use] == ["^Bash$"]
    adapter_command = codex_pre_tool_use[0]["hooks"][0]["command"]
    assert "codex-code-discovery-gate" in adapter_command
    assert "Read|Grep|Glob" not in (home / ".codex" / "config.toml").read_text(encoding="utf-8")
    adapter, configured_gate = shlex.split(adapter_command)
    code_payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "session_id": str(tmp_path),
        "tool_input": {"command": "sed -n '1,20p' src/example.py"},
    }
    first_gate = subprocess.run(
        [adapter, configured_gate], input=json.dumps(code_payload), text=True, capture_output=True, check=False
    )
    assert first_gate.returncode == 2
    second_gate = subprocess.run(
        [adapter, configured_gate], input=json.dumps(code_payload), text=True, capture_output=True, check=False
    )
    assert second_gate.returncode == 0
    no_path_gate = subprocess.run(
        [adapter, configured_gate],
        input=json.dumps({**code_payload, "tool_input": {"command": "git status --short"}}),
        text=True,
        capture_output=True,
        check=False,
    )
    assert no_path_gate.returncode == 0
    codex_cli = shutil.which("codex")
    if codex_cli:
        codex_help = subprocess.run(
            [codex_cli, "--strict-config", "--help"],
            env={**env, "CODEX_HOME": str(home / ".codex")},
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert codex_help.returncode == 0, codex_help.stdout + codex_help.stderr
    claude_config = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    assert claude_config["userSetting"] == "keep-me"
    claude_server = claude_config["mcpServers"]["agent-workflow"]
    assert claude_server["type"] == "stdio"
    assert claude_server["args"][-1] == str(REPO_ROOT)
    claude_settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    claude_hook_commands = [
        entry["command"]
        for group in claude_settings["hooks"]["SessionStart"]
        for entry in group["hooks"]
    ]
    assert len(claude_hook_commands) == 3
    assert all(Path(command).is_file() for command in claude_hook_commands)
    assert claude_settings["permissions"] == {"mode": "acceptEdits"}
    assert len(claude_settings["hooks"]["SessionStart"][0]["hooks"]) == 3
    assert (home / ".codex" / "config.toml").read_text(encoding="utf-8").count("[mcp_servers.agent-workflow]") == 1
    assert (home / ".claude.json").read_text(encoding="utf-8").count('"agent-workflow"') == 1
    assert (home / ".claude.json").read_text(encoding="utf-8").count('"hooks"') == 0
    version = subprocess.run(
        [str(launcher), "--version"], env=env, text=True, capture_output=True, timeout=30, check=False
    )
    assert version.returncode == 0, version.stderr

    second = run("install.sh")
    assert second.returncode == 0, second.stdout + second.stderr

    user_owned = home / ".codex" / "skills" / "agent-workflow-orchestrator"
    user_owned.unlink()
    user_owned.write_text("user-owned\n", encoding="utf-8")
    removed = run("uninstall.sh")
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert not launcher.exists()
    assert user_owned.read_text(encoding="utf-8") == "user-owned\n"
    assert (home / ".config" / "agent-workflow" / "config.toml").is_file()
    assert "preserved unrelated path" in removed.stderr


def test_source_installer_without_cbm_gate_keeps_pretooluse_disabled(
    product_env: dict[str, str], tmp_path: Path
) -> None:
    home = tmp_path / "install-home"
    env = dict(product_env)
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": "",
        }
    )
    codex_home = home / ".codex"
    codex_home.mkdir(parents=True)
    (codex_home / "config.toml").write_text('model = "keep-me"\n', encoding="utf-8")
    result = subprocess.run(
        [str(REPO_ROOT / "install.sh"), "--no-deps", "--no-skills"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    config = tomllib.loads((codex_home / "config.toml").read_text(encoding="utf-8"))
    assert len(config["hooks"]["SessionStart"]) == 3
    assert "PreToolUse" not in config["hooks"]


def test_public_errors_are_actionable_and_nonzero(
    installed_product: InstalledProduct, product_env: dict[str, str], tmp_path: Path
) -> None:
    missing_snapshot = installed_product.run(
        "workflow", "validate", tmp_path / "missing.json", env=product_env
    )
    assert missing_snapshot.returncode == 2
    assert "cannot read" in missing_snapshot.stderr.lower()

    mcp = subprocess.run(
        [str(installed_product.mcp), "--repo-root", str(tmp_path)],
        env=product_env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert mcp.returncode == 2
    assert "agent-workflow[mcp]" in mcp.stderr
