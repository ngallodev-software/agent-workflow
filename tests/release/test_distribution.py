from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import jsonschema

from tests.conftest import InstalledProduct, REPO_ROOT


def test_release_asset_audit_is_the_single_static_repository_gate() -> None:
    result = subprocess.run(
        ["python3", "scripts/audit-release-assets.py"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr




def test_test_authority_audit_blocks_silent_suite_growth(tmp_path: Path) -> None:
    policy = json.loads((REPO_ROOT / "tests" / "test-authority.json").read_text(encoding="utf-8"))
    blocked_policy = tmp_path / "blocked-test-authority.json"
    policy["layers"]["invariants"]["max_files"] = 0
    blocked_policy.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

    cases = [
        ([sys.executable, "scripts/audit-test-suite.py", "--skip-collection"], 0, "test authority audit: passed"),
        (
            [
                sys.executable,
                "scripts/audit-test-suite.py",
                "--skip-collection",
                "--policy",
                str(blocked_policy),
            ],
            1,
            "invariants files grew",
        ),
    ]
    for command, expected_code, expected_text in cases:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
        assert result.returncode == expected_code, result.stdout + result.stderr
        assert expected_text in result.stdout + result.stderr

    testing = (REPO_ROOT / "docs" / "TESTING.md").read_text(encoding="utf-8")
    protocol = (REPO_ROOT / "docs" / "references" / "EXECUTION_PROTOCOL.md").read_text(encoding="utf-8")
    preflight = (REPO_ROOT / "docs" / "references" / "WORKTREE_PREFLIGHT.md").read_text(encoding="utf-8")
    assert "tests/test-authority.json" in testing
    assert "scripts/audit-test-suite.py" in testing
    assert "test-authority" in protocol
    assert "persistence=false" in preflight
    assert "$XDG_CACHE_HOME/agent-workflow/codebase-memory/<worktree-id>/" in preflight
    assert "git status --porcelain=v2 -z" in preflight
    assert "256 MiB" in preflight


def test_all_published_json_schemas_are_valid_draft_2020_12() -> None:
    schemas = sorted((REPO_ROOT / "schemas").glob("*.json"))
    assert schemas
    for path in schemas:
        jsonschema.Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_shell_entrypoints_and_installer_are_syntax_valid() -> None:
    paths = [REPO_ROOT / "install.sh", REPO_ROOT / "uninstall.sh", REPO_ROOT / "bin" / "agent-workflow"]
    paths.extend(sorted((REPO_ROOT / "scripts").glob("*.sh")))
    for path in paths:
        subprocess.run(["bash", "-n", str(path)], check=True)


def test_documented_commands_match_the_installed_public_surface(
    installed_product: InstalledProduct, product_env: dict[str, str]
) -> None:
    help_text = installed_product.run("--help", env=product_env, check=True).stdout
    command_group = re.search(r"\{([a-z][a-z0-9,-]+)\}", help_text)
    assert command_group is not None, help_text
    public_commands = set(command_group.group(1).split(","))
    assert {"launch", "status", "workflow", "pack", "eval"} <= public_commands

    canonical_docs = [REPO_ROOT / "README.md", *sorted((REPO_ROOT / "docs").glob("*.md"))]
    documented: set[str] = set()
    for path in canonical_docs:
        text = path.read_text(encoding="utf-8")
        fence_languages = "bash|sh|shell|text" if path.name == "COMMAND_REFERENCE.md" else "bash|sh|shell"
        blocks = re.findall(rf"```(?:{fence_languages})\n(.*?)```", text, flags=re.DOTALL)
        for block in blocks:
            for match in re.finditer(
                r"^\s*agent-workflow\s+([a-z][a-z0-9-]+)(?:\s|$)",
                block,
                flags=re.MULTILINE,
            ):
                documented.add(match.group(1))
    assert documented <= public_commands, f"unknown documented commands: {sorted(documented - public_commands)}"

    command_reference = (REPO_ROOT / "docs" / "COMMAND_REFERENCE.md").read_text(encoding="utf-8")
    assert "agent-workflow eval compare BASELINE.json CANDIDATE.json --output PATH" in command_reference


def test_built_wheel_excludes_repository_only_ci_assets(tmp_path: Path) -> None:
    output = tmp_path / "dist"
    output.mkdir()
    result = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--no-build-isolation", "--wheel-dir", str(output)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheels = sorted(output.glob("agent_workflow-*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
    forbidden = ("Jenkinsfile", "jenkins-local-job", ".github/workflows")
    assert not any(any(token in name for token in forbidden) for name in names)
    assert not any("__pycache__/" in name or name.endswith(".pyc") for name in names)


def test_optional_mcp_profile_rejects_missing_pinned_sdk_before_client_registration(
    tmp_path: Path,
) -> None:
    fake_python = tmp_path / "python-without-mcp"
    fake_python.write_text(
        f"#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then exit 1; fi\n"
        f"exec {sys.executable!r} \"$@\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    home = tmp_path / "home"
    env = {
        **os.environ,
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
    }
    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "install-source.sh"),
            "--no-deps",
            "--no-skills",
            "--no-hooks",
            "--extras",
            "mcp",
            "--python",
            str(fake_python),
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode != 0
    assert "MCP support requires mcp==1.28.1" in result.stderr
    assert not (home / ".codex" / "config.toml").exists()
    assert not (home / ".claude.json").exists()
