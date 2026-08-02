"""Stable public API for trusted in-process agent-workflow plugins.

Plugins are executable Python code with the same local privileges as the host. The
API is a modularity boundary, not a security sandbox or authority grant.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .config import Settings

PLUGIN_API_VERSION = 1
PLUGIN_ENTRY_POINT_GROUP = "agent_workflow.plugins"

PluginConfigure = Callable[[argparse.ArgumentParser], None]
PluginExecute = Callable[[argparse.Namespace, "PluginExecutionContext"], Any]
PluginResourceKind = Literal["schema", "asset"]


@dataclass(frozen=True)
class PluginCommand:
    """One plugin-owned top-level command group."""

    name: str
    summary: str
    configure: PluginConfigure
    execute: PluginExecute


@dataclass(frozen=True)
class PluginPackageResource:
    """One immutable file shipped inside the plugin distribution.

    ``package`` is an importable package name and ``path`` is a normalized
    POSIX-relative path beneath that package. The declared digest makes plugin
    activation fail closed when installed bytes differ from the descriptor.
    """

    kind: PluginResourceKind
    identifier: str
    package: str
    path: str
    sha256: str


@dataclass(frozen=True)
class ResolvedPluginPackageResource:
    """Read-only metadata for a package resource validated by the host."""

    plugin: str
    kind: PluginResourceKind
    identifier: str
    package: str
    path: str
    sha256: str
    size: int

    def as_dict(self) -> dict[str, object]:
        return {
            "plugin": self.plugin,
            "kind": self.kind,
            "identifier": self.identifier,
            "package": self.package,
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
        }


@dataclass(frozen=True)
class PluginDescriptor:
    """Versioned, side-effect-free declaration returned by a plugin entry point.

    ``schemas``, ``assets``, and ``resources`` are stable logical identifiers.
    ``package_resources`` binds schema and asset identifiers to immutable files
    installed inside the plugin distribution.
    """

    name: str
    version: str
    api_version: int = PLUGIN_API_VERSION
    commands: tuple[PluginCommand, ...] = ()
    schemas: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()
    package_resources: tuple[PluginPackageResource, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginExecutionContext:
    """Bounded host context supplied when a plugin command executes."""

    settings: "Settings"
    json_output: bool
    host_version: str
