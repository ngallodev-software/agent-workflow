from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from tests.conftest import REPO_ROOT


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_active_version_authorities_and_release_examples_are_synchronized() -> None:
    version = _read("VERSION").strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)

    pyproject = tomllib.loads(_read("pyproject.toml"))
    assert pyproject["project"]["version"] == version
    assert f'version: {version}' in _read("agent-workflow.yaml")
    assert f'__version__ = "{version}"' in _read("src/agent_workflow/__init__.py")
    assert f'%(prog)s {version}' in _read("src/agent_workflow/cli_parser.py")
    assert f'"version": "{version}"' in _read("src/agent_workflow/doctor.py")

    for relative in ("release/release-policy.json", "release/dependency-lock.json"):
        assert json.loads(_read(relative))["version"] == version

    active_text = "\n".join(
        _read(relative)
        for relative in (
            "docs/ARCHITECTURE.md",
            "docs/PLUGIN_API.md",
            "docs/FEATURE_MODULE_ARCHITECTURE.md",
            "docs/INSTALLATION.md",
            "docs/CHANGELOG.md",
            "SESSION_RESTORE.md",
            "prompt-packs/feature-modularization/README.md",
            "prompt-packs/feature-modularization/pack.yaml",
            "docs/man/agent-workflow.1",
            "docs/man/agent-workflow-index.1",
            "docs/man/agent-workflow-workflow.1",
            "docs/man/agent-workflow-mcp.1",
        )
    )
    assert version in active_text
    assert f"v{version}/install.sh" in _read("docs/INSTALLATION.md")
    assert f"--version v{version}" in _read("docs/INSTALLATION.md")
    assert f'minimum_version: "{version}"' in _read("prompt-packs/feature-modularization/pack.yaml")


def test_optional_mcp_and_repository_only_jenkins_claims_do_not_drift() -> None:
    install = _read("docs/INSTALLATION.md")
    install_flat = " ".join(install.split())
    readme = _read("README.md")
    readme_flat = " ".join(readme.split())
    mcp_man = _read("docs/man/agent-workflow-mcp.1")

    forbidden = (
        "The core package includes the pinned MCP SDK",
        "on every normal install",
        "pipeline uses the core MCP dependency",
    )
    assert not any(claim in install for claim in forbidden)
    assert "Base installations neither require the MCP SDK nor edit MCP client configuration." in install_flat
    assert "only with the mcp extra" in install
    assert "The base package does not install the MCP SDK." in mcp_man
    assert "Jenkins CI and local server-job files remain in the source repository" in readme_flat
    assert "excluded from installed wheels and platform runtime bundles" in install_flat


def test_hierarchy_authority_claims_stop_before_runtime_claims() -> None:
    readme = _read("README.md")
    architecture = _read("docs/ARCHITECTURE.md")
    command_reference = _read("docs/COMMAND_REFERENCE.md")
    main_man = _read("docs/man/agent-workflow.1")

    for text in (readme, architecture, main_man):
        assert "digest-sealed team/root receipts" in text
    assert "tmux topology" in readme and "remain separately gated" in readme
    assert "no runtime/tmux authority yet" in architecture
    assert "does not yet expose team-runtime or tmux-topology commands" in command_reference
    assert "Team runtime, tmux topology" in main_man


def test_restore_guide_is_portable_and_current() -> None:
    restore = _read("SESSION_RESTORE.md")
    assert "/lump/apps" not in restore
    assert "gpt-5.6-terra" not in restore
    assert "0.2.5" not in restore
    assert "host-specific absolute paths" in restore
    assert "Base installation does not require the MCP SDK" in restore
