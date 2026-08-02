from __future__ import annotations

import hashlib
import importlib
import json
import sys
from dataclasses import dataclass, replace
from types import SimpleNamespace

import pytest

from agent_workflow.cli import build_parser
from agent_workflow.command_catalog import write_launch_command_artifacts
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.plugin_api import (
    PluginCommand,
    PluginDescriptor,
    PluginPackageResource,
)
from agent_workflow.plugins import load_plugin_registry


def _configure(parser) -> None:
    parser.add_argument("--value", default="ok")


def _execute(args, context):
    return {"value": args.value, "host": context.host_version}


@dataclass
class _EntryPoint:
    name: str
    value: str
    exported: object
    load_count: int = 0

    @property
    def dist(self):
        return SimpleNamespace(name=f"dist-{self.name}", version="1.0")

    def load(self):
        self.load_count += 1
        return self.exported


def _descriptor(name: str, *, api_version: int = 1, command: str | None = None):
    commands = ()
    if command:
        commands = (PluginCommand(command, f"{command} command", _configure, _execute),)
    return PluginDescriptor(name=name, version="1.0", api_version=api_version, commands=commands)


def _install_candidates(monkeypatch: pytest.MonkeyPatch, *entries: _EntryPoint) -> None:
    def entry_points(*, group: str):
        assert group == "agent_workflow.plugins"
        return entries

    monkeypatch.setattr("agent_workflow.plugins.metadata.entry_points", entry_points)


def test_disabled_candidates_are_discovered_without_import(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = _EntryPoint("fixture", "fixture:plugin", lambda: _descriptor("fixture"))
    _install_candidates(monkeypatch, entry)

    registry = load_plugin_registry(())

    assert entry.load_count == 0
    assert registry.inventory()[0]["name"] == "fixture"
    assert registry.inventory()[0]["loaded"] is False


def test_incompatible_enabled_plugin_fails_strictly(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = _EntryPoint(
        "fixture",
        "fixture:plugin",
        lambda: _descriptor("fixture", api_version=999),
    )
    _install_candidates(monkeypatch, entry)

    with pytest.raises(WorkflowError, match="supports API 1"):
        load_plugin_registry(("fixture",))


def test_duplicate_registration_rolls_back_atomically(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _EntryPoint("first", "first:plugin", lambda: _descriptor("first", command="shared"))
    second = _EntryPoint("second", "second:plugin", lambda: _descriptor("second", command="shared"))
    _install_candidates(monkeypatch, first, second)

    with pytest.raises(WorkflowError, match="duplicate plugin command registration"):
        load_plugin_registry(("first", "second"))

    # No global registry was mutated by the failed transaction.
    registry = load_plugin_registry(("first",))
    assert [command.name for _, command in registry.commands] == ["shared"]


def test_no_plugins_suppresses_enabled_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = _EntryPoint("fixture", "fixture:plugin", lambda: _descriptor("fixture"))
    _install_candidates(monkeypatch, entry)

    registry = load_plugin_registry(("fixture",), suppress=True)

    assert entry.load_count == 0
    assert registry.inventory()[0]["suppressed"] is True


def test_plugin_command_cannot_shadow_core_command(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = _EntryPoint("fixture", "fixture:plugin", lambda: _descriptor("fixture", command="doctor"))
    _install_candidates(monkeypatch, entry)
    registry = load_plugin_registry(("fixture",))

    with pytest.raises(WorkflowError, match="conflicts with a core command"):
        build_parser(registry)


def test_enabled_plugin_provenance_is_bound_into_launch_command_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    entry = _EntryPoint(
        "fixture",
        "fixture:plugin",
        lambda: _descriptor("fixture", command="fixture-command"),
    )
    _install_candidates(monkeypatch, entry)
    settings = replace(defaults(tmp_path / "config.toml"), plugins_enabled=("fixture",))

    evidence = write_launch_command_artifacts(
        tmp_path,
        role="orchestrator",
        settings=settings,
    )

    catalog = json.loads((tmp_path / evidence["catalog_path"]).read_text(encoding="utf-8"))
    assert catalog["plugins"][0]["name"] == "fixture"
    assert catalog["plugins"][0]["distribution"] == "dist-fixture"
    assert "fixture-command" in {item["command"] for item in catalog["commands"]}
    card = (tmp_path / evidence["card_path"]).read_text(encoding="utf-8")
    assert "`fixture-command`" in card



def _install_resource_package(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    *,
    package: str = "fixture_resources",
    relative_path: str = "schemas/example.json",
    content: bytes = b'{"type":"object"}\n',
) -> tuple[str, str]:
    root = tmp_path / package
    target = root / relative_path
    target.parent.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    target.write_bytes(content)
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    sys.modules.pop(package, None)
    return package, hashlib.sha256(content).hexdigest()


def test_enabled_plugin_resolves_and_reads_digest_bound_package_resource(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    package, digest = _install_resource_package(monkeypatch, tmp_path)
    resource = PluginPackageResource(
        kind="schema",
        identifier="fixture.schema",
        package=package,
        path="schemas/example.json",
        sha256=digest,
    )
    entry = _EntryPoint(
        "fixture",
        "fixture:plugin",
        lambda: PluginDescriptor(
            name="fixture",
            version="1.0",
            package_resources=(resource,),
        ),
    )
    _install_candidates(monkeypatch, entry)

    registry = load_plugin_registry(("fixture",))

    assert registry.read_package_resource("schema", "fixture.schema") == b'{"type":"object"}\n'
    assert registry.package_resources[0].size == len(b'{"type":"object"}\n')
    inventory = registry.inventory()[0]["package_resources"]
    assert inventory[0]["identifier"] == "fixture.schema"
    assert inventory[0]["sha256"] == digest


def test_package_resource_traversal_is_rejected_before_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resource = PluginPackageResource(
        kind="asset",
        identifier="fixture.asset",
        package="fixture_resources",
        path="../secret.txt",
        sha256="0" * 64,
    )
    entry = _EntryPoint(
        "fixture",
        "fixture:plugin",
        lambda: PluginDescriptor(
            name="fixture",
            version="1.0",
            package_resources=(resource,),
        ),
    )
    _install_candidates(monkeypatch, entry)

    with pytest.raises(WorkflowError, match="invalid plugin package resource path"):
        load_plugin_registry(("fixture",))


def test_package_resource_digest_mismatch_fails_activation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    package, _ = _install_resource_package(monkeypatch, tmp_path)
    resource = PluginPackageResource(
        kind="schema",
        identifier="fixture.schema",
        package=package,
        path="schemas/example.json",
        sha256="0" * 64,
    )
    entry = _EntryPoint(
        "fixture",
        "fixture:plugin",
        lambda: PluginDescriptor(
            name="fixture",
            version="1.0",
            package_resources=(resource,),
        ),
    )
    _install_candidates(monkeypatch, entry)

    with pytest.raises(WorkflowError, match="package resource digest mismatch"):
        load_plugin_registry(("fixture",))


def test_package_resource_collision_rolls_back_entire_transaction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    package, digest = _install_resource_package(monkeypatch, tmp_path)

    def descriptor(name: str) -> PluginDescriptor:
        return PluginDescriptor(
            name=name,
            version="1.0",
            package_resources=(
                PluginPackageResource(
                    kind="schema",
                    identifier="shared.schema",
                    package=package,
                    path="schemas/example.json",
                    sha256=digest,
                ),
            ),
        )

    first = _EntryPoint("first", "first:plugin", lambda: descriptor("first"))
    second = _EntryPoint("second", "second:plugin", lambda: descriptor("second"))
    _install_candidates(monkeypatch, first, second)

    with pytest.raises(WorkflowError, match="duplicate plugin schema registration"):
        load_plugin_registry(("first", "second"))

    registry = load_plugin_registry(("first",))
    assert registry.read_package_resource("schema", "shared.schema") == b'{"type":"object"}\n'


def test_missing_package_resource_fails_activation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    package, digest = _install_resource_package(monkeypatch, tmp_path)
    resource = PluginPackageResource(
        kind="asset",
        identifier="fixture.missing",
        package=package,
        path="assets/missing.txt",
        sha256=digest,
    )
    entry = _EntryPoint(
        "fixture",
        "fixture:plugin",
        lambda: PluginDescriptor(
            name="fixture",
            version="1.0",
            package_resources=(resource,),
        ),
    )
    _install_candidates(monkeypatch, entry)

    with pytest.raises(WorkflowError, match="could not resolve package resource|is not a file"):
        load_plugin_registry(("fixture",))
