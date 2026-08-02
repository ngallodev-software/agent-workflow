"""Deterministic discovery and atomic registration for trusted plugins."""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import metadata
from types import MappingProxyType
from typing import Iterable

from . import __version__
from .errors import WorkflowError
from .plugin_api import (
    PLUGIN_API_VERSION,
    PLUGIN_ENTRY_POINT_GROUP,
    PluginCommand,
    PluginDescriptor,
)

_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")


@dataclass(frozen=True)
class PluginCandidate:
    name: str
    value: str
    distribution: str | None
    distribution_version: str | None
    entry_point: metadata.EntryPoint

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "entry_point": self.value,
            "distribution": self.distribution,
            "distribution_version": self.distribution_version,
        }


@dataclass(frozen=True)
class LoadedPlugin:
    descriptor: PluginDescriptor
    candidate: PluginCandidate

    def as_dict(self) -> dict[str, object]:
        return {
            **self.candidate.as_dict(),
            "plugin_version": self.descriptor.version,
            "api_version": self.descriptor.api_version,
            "commands": [command.name for command in self.descriptor.commands],
            "schemas": list(self.descriptor.schemas),
            "assets": list(self.descriptor.assets),
            "resources": list(self.descriptor.resources),
        }


@dataclass(frozen=True)
class PluginRegistry:
    """Immutable result of one complete plugin registration transaction."""

    loaded: tuple[LoadedPlugin, ...]
    candidates: tuple[PluginCandidate, ...]
    configured_enabled: tuple[str, ...]
    suppressed: bool = False

    @property
    def commands(self) -> tuple[tuple[LoadedPlugin, PluginCommand], ...]:
        return tuple(
            (plugin, command)
            for plugin in self.loaded
            for command in plugin.descriptor.commands
        )

    def inventory(self) -> list[dict[str, object]]:
        enabled = set(self.configured_enabled)
        loaded = {plugin.descriptor.name: plugin for plugin in self.loaded}
        rows: list[dict[str, object]] = []
        represented: set[str] = set()
        for candidate in self.candidates:
            represented.add(candidate.name)
            row = candidate.as_dict()
            row.update(
                {
                    "enabled": candidate.name in enabled,
                    "loaded": candidate.name in loaded,
                    "suppressed": self.suppressed and candidate.name in enabled,
                }
            )
            if candidate.name in loaded:
                row.update(loaded[candidate.name].as_dict())
                row["enabled"] = True
                row["loaded"] = True
                row["suppressed"] = False
            rows.append(row)
        for name in sorted(enabled - represented):
            rows.append(
                {
                    "name": name,
                    "entry_point": None,
                    "distribution": None,
                    "distribution_version": None,
                    "enabled": True,
                    "loaded": False,
                    "suppressed": self.suppressed,
                }
            )
        return sorted(rows, key=lambda row: (str(row["name"]), str(row.get("entry_point") or "")))

    def catalog_inventory(self) -> list[dict[str, object]]:
        return [plugin.as_dict() for plugin in self.loaded]


EMPTY_PLUGIN_REGISTRY = PluginRegistry((), (), ())


def discover_plugin_candidates() -> tuple[PluginCandidate, ...]:
    """Discover entry-point metadata without importing plugin modules."""
    candidates: list[PluginCandidate] = []
    for entry_point in metadata.entry_points(group=PLUGIN_ENTRY_POINT_GROUP):
        distribution = getattr(entry_point, "dist", None)
        candidates.append(
            PluginCandidate(
                name=entry_point.name,
                value=entry_point.value,
                distribution=getattr(distribution, "name", None),
                distribution_version=getattr(distribution, "version", None),
                entry_point=entry_point,
            )
        )
    return tuple(sorted(candidates, key=lambda item: (item.name, item.value)))


def _validate_name(value: str, *, label: str) -> None:
    if not _NAME.fullmatch(value):
        raise WorkflowError(
            f"invalid {label} {value!r}; expected lowercase letters, digits, and hyphens"
        )


def _validate_identifiers(values: Iterable[str], *, label: str) -> tuple[str, ...]:
    result = tuple(values)
    for value in result:
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise WorkflowError(f"invalid plugin {label} identifier: {value!r}")
    if len(set(result)) != len(result):
        raise WorkflowError(f"duplicate plugin {label} identifier within one descriptor")
    return result


def _load_descriptor(candidate: PluginCandidate) -> PluginDescriptor:
    try:
        exported = candidate.entry_point.load()
        descriptor = exported() if callable(exported) and not isinstance(exported, PluginDescriptor) else exported
    except Exception as exc:  # plugin import failures must become bounded diagnostics
        raise WorkflowError(
            f"enabled plugin {candidate.name!r} could not be loaded from {candidate.value}: {exc}"
        ) from exc
    if not isinstance(descriptor, PluginDescriptor):
        raise WorkflowError(
            f"enabled plugin {candidate.name!r} did not return PluginDescriptor"
        )
    return descriptor


def _stage_registry(
    candidates: tuple[PluginCandidate, ...],
    enabled: tuple[str, ...],
) -> PluginRegistry:
    by_name: dict[str, list[PluginCandidate]] = {}
    for candidate in candidates:
        by_name.setdefault(candidate.name, []).append(candidate)

    staged: list[LoadedPlugin] = []
    for name in enabled:
        matches = by_name.get(name, [])
        if not matches:
            raise WorkflowError(
                f"enabled plugin {name!r} is not installed; disable it in [plugins].enabled "
                "or install a distribution exposing agent_workflow.plugins"
            )
        if len(matches) != 1:
            sources = ", ".join(item.value for item in matches)
            raise WorkflowError(f"enabled plugin {name!r} has ambiguous entry points: {sources}")
        candidate = matches[0]
        descriptor = _load_descriptor(candidate)
        _validate_name(descriptor.name, label="plugin name")
        if descriptor.name != name:
            raise WorkflowError(
                f"plugin entry point {name!r} returned descriptor {descriptor.name!r}"
            )
        if descriptor.api_version != PLUGIN_API_VERSION:
            raise WorkflowError(
                f"plugin {name!r} uses API {descriptor.api_version}; "
                f"agent-workflow {__version__} supports API {PLUGIN_API_VERSION}"
            )
        if not descriptor.version:
            raise WorkflowError(f"plugin {name!r} must declare a non-empty version")
        for command in descriptor.commands:
            if not isinstance(command, PluginCommand):
                raise WorkflowError(f"plugin {name!r} contains an invalid command declaration")
            _validate_name(command.name, label="plugin command")
            if not command.summary or not callable(command.configure) or not callable(command.execute):
                raise WorkflowError(f"plugin {name!r} command {command.name!r} is incomplete")
        _validate_identifiers(descriptor.schemas, label="schema")
        _validate_identifiers(descriptor.assets, label="asset")
        _validate_identifiers(descriptor.resources, label="resource")
        staged.append(LoadedPlugin(descriptor, candidate))

    # Validate the entire transaction before exposing any registration.
    descriptor_names = [item.descriptor.name for item in staged]
    if len(set(descriptor_names)) != len(descriptor_names):
        raise WorkflowError("duplicate enabled plugin descriptor name")
    for label, values in {
        "command": [command.name for item in staged for command in item.descriptor.commands],
        "schema": [value for item in staged for value in item.descriptor.schemas],
        "asset": [value for item in staged for value in item.descriptor.assets],
        "resource": [value for item in staged for value in item.descriptor.resources],
    }.items():
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            raise WorkflowError(f"duplicate plugin {label} registration: {', '.join(duplicates)}")

    # A proxy is constructed as a final duplicate assertion and documents that
    # consumers receive immutable lookup semantics even though the public
    # registry exposes ordered tuples for deterministic rendering.
    MappingProxyType({item.descriptor.name: item for item in staged})
    return PluginRegistry(tuple(staged), candidates, enabled)


def load_plugin_registry(
    enabled: Iterable[str],
    *,
    suppress: bool = False,
) -> PluginRegistry:
    configured = tuple(enabled)
    for name in configured:
        if not isinstance(name, str):
            raise WorkflowError("[plugins].enabled must contain plugin names")
        _validate_name(name, label="enabled plugin")
    if len(set(configured)) != len(configured):
        raise WorkflowError("[plugins].enabled must not contain duplicates")
    candidates = discover_plugin_candidates()
    if suppress:
        return PluginRegistry((), candidates, configured, suppressed=True)
    return _stage_registry(candidates, configured)
