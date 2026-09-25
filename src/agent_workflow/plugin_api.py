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
DecisionDisposition = Literal["shadow", "advisory", "automated"]


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
class DecisionRequest:
    """One bounded application-owned semantic decision set request."""

    decision_ids: tuple[str, ...]
    state: Mapping[str, object]
    control_values: Mapping[str, object]


@dataclass(frozen=True)
class DecisionEvidence:
    """Provider-neutral semantic evidence returned by a decision provider."""

    decision_id: str
    status: str
    semantic_type: str
    value: object | None = None
    confidence: float | None = None
    probability: float | None = None
    distribution: Mapping[str, float] = field(default_factory=dict)
    model: str | None = None
    question_set_version: str | None = None
    request_sha256: str | None = None
    request_id: str | None = None
    projector_version: str | None = None
    usage: Mapping[str, object] = field(default_factory=dict)
    source_refs: tuple[str, ...] = ()
    error_class: str | None = None


@dataclass(frozen=True)
class DecisionContext:
    """Host context supplied to a plugin semantic decision provider."""

    settings: "Settings"
    host_version: str


DecisionEvaluate = Callable[[DecisionRequest, DecisionContext], Mapping[str, DecisionEvidence]]




@dataclass(frozen=True)
class PluginDecisionProvider:
    """A plugin-owned semantic evidence provider for stable host decision IDs."""

    name: str
    decisions: tuple[str, ...]
    evaluate: DecisionEvaluate


@dataclass(frozen=True)
class PluginDecisionMode:
    """A plugin-advertised execution mode backed by one semantic provider.

    ``capture_comparison`` asks the host to record control/candidate evidence using
    the provider-neutral comparative-eval capability. The host, not the plugin,
    owns persistence and lifecycle outcome joining.
    """

    name: str
    summary: str
    provider: str
    disposition: DecisionDisposition
    capture_comparison: bool = False


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
    decision_providers: tuple[PluginDecisionProvider, ...] = ()
    decision_modes: tuple[PluginDecisionMode, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginExecutionContext:
    """Bounded host context supplied when a plugin command executes."""

    settings: "Settings"
    json_output: bool
    host_version: str
