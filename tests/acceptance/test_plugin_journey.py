from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import InstalledProduct


def _build_and_install_fixture(installed_product: InstalledProduct, tmp_path: Path) -> None:
    package = tmp_path / "fixture-plugin"
    package.mkdir()
    (package / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "agent-workflow-fixture-plugin"
version = "1.0.0"
requires-python = ">=3.11"

[project.entry-points."agent_workflow.plugins"]
fixture = "aw_fixture_plugin:plugin"

[tool.setuptools]
py-modules = ["aw_fixture_plugin"]
""",
        encoding="utf-8",
    )
    (package / "aw_fixture_plugin.py").write_text(
        """import os
from pathlib import Path
from agent_workflow.plugin_api import PluginCommand, PluginDescriptor

marker = os.environ.get("FIXTURE_PLUGIN_IMPORT_MARKER")
if marker:
    Path(marker).write_text("imported\\n", encoding="utf-8")

def configure(parser):
    parser.add_argument("--value", required=True)

def execute(args, context):
    return {
        "plugin": "fixture",
        "value": args.value,
        "host_version": context.host_version,
        "state_root": str(context.settings.state_root),
    }

def plugin():
    return PluginDescriptor(
        name="fixture",
        version="1.0.0",
        commands=(PluginCommand("fixture-echo", "fixture plugin echo", configure, execute),),
        resources=("fixture://echo",),
    )
""",
        encoding="utf-8",
    )
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    built = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheelhouse),
            str(package),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    wheel = next(wheelhouse.glob("agent_workflow_fixture_plugin-*.whl"))
    installed = subprocess.run(
        [str(installed_product.python), "-m", "pip", "install", "--no-deps", str(wheel)],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr


def _config(path: Path, *, enabled: bool) -> Path:
    path.write_text(
        "schema_version = 1\n\n[plugins]\nenabled = "
        + ('["fixture"]\n' if enabled else "[]\n"),
        encoding="utf-8",
    )
    return path


def test_installed_trusted_plugin_is_explicit_atomic_and_recoverable(
    installed_product: InstalledProduct,
    tmp_path: Path,
) -> None:
    _build_and_install_fixture(installed_product, tmp_path)
    marker = tmp_path / "plugin-imported"
    env = {**os.environ, "FIXTURE_PLUGIN_IMPORT_MARKER": str(marker)}
    disabled = _config(tmp_path / "disabled.toml", enabled=False)
    enabled = _config(tmp_path / "enabled.toml", enabled=True)

    inventory = installed_product.run(
        "--config", disabled, "--json", "plugins", "list", env=env, check=True
    )
    inventory_data = json.loads(inventory.stdout)
    assert inventory_data["plugins"][0]["name"] == "fixture"
    assert inventory_data["plugins"][0]["loaded"] is False
    assert not marker.exists(), "disabled entry-point candidate was imported"

    executed = installed_product.run(
        "--config",
        enabled,
        "--json",
        "fixture-echo",
        "--value",
        "hello",
        env=env,
        check=True,
    )
    assert json.loads(executed.stdout)["value"] == "hello"
    assert marker.read_text(encoding="utf-8") == "imported\n"

    catalog = installed_product.run(
        "--config", enabled, "--json", "commands", "--format", "json", env=env, check=True
    )
    catalog_data = json.loads(catalog.stdout)
    assert [item["name"] for item in catalog_data["plugins"]] == ["fixture"]
    assert "fixture-echo" in {item["command"] for item in catalog_data["commands"]}

    marker.unlink()
    suppressed = installed_product.run(
        "--config", enabled, "--no-plugins", "--json", "plugins", "list", env=env, check=True
    )
    suppressed_data = json.loads(suppressed.stdout)
    assert suppressed_data["suppressed"] is True
    assert suppressed_data["plugins"][0]["suppressed"] is True
    assert not marker.exists(), "--no-plugins imported an enabled candidate"

    unavailable = installed_product.run(
        "--config", enabled, "--no-plugins", "fixture-echo", "--value", "hello", env=env
    )
    assert unavailable.returncode == 2
    assert not marker.exists()
