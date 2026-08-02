"""Deterministic discovery and atomic registration for trusted plugins."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from importlib import metadata, resources
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from . import __version__
from .errors import WorkflowError
from .plugin_api import (
    PLUGIN_API_VERSION,
    PLUGIN_ENTRY_POINT_GROUP,
    PluginCommand,
    PluginDescriptor,
    PluginPackageResource,
    PluginResourceKind,
    ResolvedPluginPackageResource,
)

_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_PACKAGE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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
    package_resources: tuple[ResolvedPluginPackageResource, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            **self.candidate.as_dict(),
            "plugin_version": self.descriptor.version,
            "api_version": self.descriptor.api_version,
            "commands": [command.name for command in self.descriptor.commands],
            "schemas": list(self.descriptor.schemas),
            "assets": list(self.descriptor.assets),
            "resources": list(self.descriptor.resources),
            "package_resources": [item.as_dict() for item in self.package_resources],
        }


@dataclass(frozen=True)
class PluginRegistry:
    """Immutable result of one complete plugin registration transaction."""

    loaded: tuple[LoadedPlugin, ...]
    candidates: tuple[PluginCandidate, ...]
    configured_enabled: tuple[str, ...]
    suppressed: bool = False
    _resource_contents: Mapping[tuple[PluginResourceKind, str], bytes] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )

    @property
    def commands(self) -> tuple[tuple[LoadedPlugin, PluginCommand], ...]:
        return tuple(
            (plugin, command)
            for plugin in self.loaded
            for command in plugin.descriptor.commands
        )

    @property
    def package_resources(self) -> tuple[ResolvedPluginPackageResource, ...]:
        return tuple(item for plugin in self.loaded for item in plugin.package_resources)

    def read_package_resource(self, kind: PluginResourceKind, identifier: str) -> bytes:
        """Return validated immutable resource bytes by exact logical identifier."""
        try:
            return self._resource_contents[(kind, identifier)]
        except KeyError as exc:
            raise WorkflowError(
                f"plugin package resource is not registered: {kind}:{identifier}"
            ) from exc

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
        descriptor = (
            exported()
            if callable(exported) and not isinstance(exported, PluginDescriptor)
            else exported
        )
    except Exception as exc:  # plugin import failures must become bounded diagnostics
        raise WorkflowError(
            f"enabled plugin {candidate.name!r} could not be loaded from {candidate.value}: {exc}"
        ) from exc
    if not isinstance(descriptor, PluginDescriptor):
        raise WorkflowError(
            f"enabled plugin {candidate.name!r} did not return PluginDescriptor"
        )
    return descriptor


def _validate_resource_path(value: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or "\\" in value:
        raise WorkflowError(f"invalid plugin package resource path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(part in {"", ".", ".."} for part in path.parts):
        raise WorkflowError(f"invalid plugin package resource path: {value!r}")
    return path.parts


def _read_package_resource(
    plugin_name: str,
    declaration: PluginPackageResource,
) -> tuple[ResolvedPluginPackageResource, bytes]:
    if not isinstance(declaration, PluginPackageResource):
        raise WorkflowError(
            f"plugin {plugin_name!r} contains an invalid package resource declaration"
        )
    if declaration.kind not in {"schema", "asset"}:
        raise WorkflowError(
            f"plugin {plugin_name!r} package resource has invalid kind {declaration.kind!r}"
        )
    _validate_identifiers((declaration.identifier,), label=declaration.kind)
    if not isinstance(declaration.package, str) or not _PACKAGE.fullmatch(declaration.package):
        raise WorkflowError(
            f"plugin {plugin_name!r} package resource has invalid package {declaration.package!r}"
        )
    parts = _validate_resource_path(declaration.path)
    if not isinstance(declaration.sha256, str) or not _SHA256.fullmatch(declaration.sha256):
        raise WorkflowError(
            f"plugin {plugin_name!r} package resource {declaration.identifier!r} "
            "must declare a lowercase SHA-256 digest"
        )

    try:
        root = resources.files(declaration.package)
        target = root.joinpath(*parts)
        if isinstance(root, Path) and isinstance(target, Path):
            root_resolved = root.resolve(strict=True)
            target_resolved = target.resolve(strict=True)
            if not target_resolved.is_relative_to(root_resolved):
                raise WorkflowError(
                    f"plugin {plugin_name!r} package resource escapes package root: "
                    f"{declaration.path!r}"
                )
            relative = target.relative_to(root)
            cursor = root
            for part in relative.parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise WorkflowError(
                        f"plugin {plugin_name!r} package resource may not traverse symlinks: "
                        f"{declaration.path!r}"
                    )
        if not target.is_file():
            raise WorkflowError(
                f"plugin {plugin_name!r} package resource is not a file: {declaration.path!r}"
            )
        content = target.read_bytes()
    except WorkflowError:
        raise
    except Exception as exc:
        raise WorkflowError(
            f"plugin {plugin_name!r} could not resolve package resource "
            f"{declaration.package}:{declaration.path}: {exc}"
        ) from exc

    actual = hashlib.sha256(content).hexdigest()
    if not hmac.compare_digest(actual, declaration.sha256):
        raise WorkflowError(
            f"plugin {plugin_name!r} package resource digest mismatch for "
            f"{declaration.identifier!r}: expected {declaration.sha256}, got {actual}"
        )
    return (
        ResolvedPluginPackageResource(
            plugin=plugin_name,
            kind=declaration.kind,
            identifier=declaration.identifier,
            package=declaration.package,
            path=declaration.path,
            sha256=actual,
            size=len(content),
        ),
        content,
    )


def _stage_registry(
    candidates: tuple[PluginCandidate, ...],
    enabled: tuple[str, ...],
) -> PluginRegistry:
    by_name: dict[str, list[PluginCandidate]] = {}
    for candidate in candidates:
        by_name.setdefault(candidate.name, []).append(candidate)

    staged: list[LoadedPlugin] = []
    staged_contents: dict[tuple[PluginResourceKind, str], bytes] = {}
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

        resolved: list[ResolvedPluginPackageResource] = []
        for declaration in descriptor.package_resources:
            metadata_record, content = _read_package_resource(name, declaration)
            key = (metadata_record.kind, metadata_record.identifier)
            if key in staged_contents:
                raise WorkflowError(
                    f"duplicate plugin {metadata_record.kind} registration: "
                    f"{metadata_record.identifier}"
                )
            staged_contents[key] = content
            resolved.append(metadata_record)
        staged.append(LoadedPlugin(descriptor, candidate, tuple(resolved)))

    # Validate the entire transaction before exposing any registration.
    descriptor_names = [item.descriptor.name for item in staged]
    if len(set(descriptor_names)) != len(descriptor_names):
        raise WorkflowError("duplicate enabled plugin descriptor name")
    for label, values in {
        "command": [command.name for item in staged for command in item.descriptor.commands],
        "schema": [
            *[value for item in staged for value in item.descriptor.schemas],
            *[
                resource.identifier
                for item in staged
                for resource in item.package_resources
                if resource.kind == "schema"
            ],
        ],
        "asset": [
            *[value for item in staged for value in item.descriptor.assets],
            *[
                resource.identifier
                for item in staged
                for resource in item.package_resources
                if resource.kind == "asset"
            ],
        ],
        "resource": [value for item in staged for value in item.descriptor.resources],
    }.items():
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            raise WorkflowError(f"duplicate plugin {label} registration: {', '.join(duplicates)}")

    MappingProxyType({item.descriptor.name: item for item in staged})
    return PluginRegistry(
        tuple(staged),
        candidates,
        enabled,
        _resource_contents=MappingProxyType(dict(staged_contents)),
    )


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
