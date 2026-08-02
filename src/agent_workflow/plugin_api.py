"""Stable public API for trusted in-process agent-workflow plugins.

Plugins are executable Python code with the same local privileges as the host.  The
API is a modularity boundary, not a security sandbox or authority grant.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import Settings

PLUGIN_API_VERSION = 1
PLUGIN_ENTRY_POINT_GROUP = "agent_workflow.plugins"

PluginConfigure = Callable[[argparse.ArgumentParser], None]
PluginExecute = Callable[[argparse.Namespace, "PluginExecutionContext"], Any]


@dataclass(frozen=True)
class PluginCommand:
    """One plugin-owned top-level command group."""

    name: str
    summary: str
    configure: PluginConfigure
    execute: PluginExecute


@dataclass(frozen=True)
class PluginDescriptor:
    """Versioned, side-effect-free declaration returned by a plugin entry point.

    ``schemas``, ``assets``, and ``resources`` are stable logical identifiers.
    Their transport/loading contracts can evolve without allowing import-time
    mutation of core registries.
    """

    name: str
    version: str
    api_version: int = PLUGIN_API_VERSION
    commands: tuple[PluginCommand, ...] = ()
    schemas: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginExecutionContext:
    """Bounded host context supplied when a plugin command executes."""

    settings: "Settings"
    json_output: bool
    host_version: str
