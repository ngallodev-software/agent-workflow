from __future__ import annotations

import json
import os
import re
import subprocess
import sys
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
    assert 'version=f"%(prog)s {__version__}"' in _read("src/agent_workflow/cli_parser.py")
    result = subprocess.run(
        [sys.executable, "-m", "agent_workflow", "--version"],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == f"agent-workflow {version}"
    assert '"version": __version__' in _read("src/agent_workflow/doctor.py")
    doctor = subprocess.run(
        [sys.executable, "-m", "agent_workflow", "--json", "doctor"],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(doctor.stdout)["version"] == version

    for relative in ("release/release-policy.json", "release/dependency-lock.json"):
        assert json.loads(_read(relative))["version"] == version

    active_text = "\n".join(
        _read(relative)
        for relative in (
            "README.md", "docs/ARCHITECTURE.md", "docs/INSTALLATION.md",
            "docs/OPERATIONS.md", "docs/BACKLOG.md",
        )
    )
    assert version in active_text
    assert f"v{version}/install.sh" in _read("docs/INSTALLATION.md")
    assert f"--version v{version}" in _read("docs/INSTALLATION.md")


def test_optional_mcp_and_repository_only_jenkins_claims_do_not_drift() -> None:
    install = _read("docs/INSTALLATION.md")
    install_flat = " ".join(install.split())
    readme = _read("README.md")
    readme_flat = " ".join(readme.split())
    pyproject = tomllib.loads(_read("pyproject.toml"))

    forbidden = (
        "The core package includes the pinned MCP SDK",
        "on every normal install",
        "pipeline uses the core MCP dependency",
    )
    assert not any(claim in install for claim in forbidden)
    assert "mcp" in pyproject["project"]["optional-dependencies"]
    assert all("mcp" not in dep.lower() for dep in pyproject["project"]["dependencies"])
    assert "Jenkins CI and local server-job files remain in the source repository" in readme_flat
    assert "excluded from installed wheels and platform runtime bundles" in install_flat


def test_runtime_authority_claims_match_headless_agent_run_architecture() -> None:
    readme = _read("README.md")
    architecture = _read("docs/ARCHITECTURE.md")
    operations = _read("docs/OPERATIONS.md")
    assert "Agent Run" in readme
    assert "headless" in readme
    assert "worker" in architecture.lower()
    assert "agent-workflow commands --format markdown" in operations
    assert "External host and plugin boundary" in architecture
    assert "plugin absent" in architecture


def test_restore_guide_is_portable_and_current() -> None:
    operations = _read("docs/OPERATIONS.md")
    assert "/lump/apps" not in operations
    assert "gpt-5.6-terra" not in operations
    assert "0.2.5" not in operations
    assert "host-specific absolute paths" in operations
    assert "Agent Run" in operations
