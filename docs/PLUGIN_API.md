# Trusted plugin API

`agent-workflow` 0.9.0 includes the trusted in-process plugin host. The boundary exists to keep optional capabilities modular; it is not a sandbox and installing or enabling a plugin does not grant workflow, permission, review, or acceptance authority.

## Enablement and recovery

Plugins are Python distributions advertising the `agent_workflow.plugins` entry-point group. Discovery reads package metadata only. A candidate module is imported only when its entry-point name appears in configuration:

```toml
[plugins]
enabled = ["agent-workflow-spec"]
```

Every configured plugin is required to be installed, uniquely discoverable, and compatible with the current plugin API when a plugin-aware surface is requested. Normal built-in lifecycle commands skip plugin discovery entirely; plugin inventory, doctor/completion, the full maintainer catalog, and unknown top-level commands load the configured registry on demand. A plugin registration failure therefore blocks plugin-aware surfaces without adding import/discovery cost to ordinary Agent Run operations. Use the global recovery option to suppress configured plugins explicitly:

```bash
agent-workflow --no-plugins plugins list
agent-workflow --no-plugins doctor
```

`agent-workflow plugins list --json` reports discovered distribution metadata, configured enablement, load state, and suppression state.

## Public descriptor

An entry point exports either a `PluginDescriptor` or a zero-argument callable returning one. Commands are declared without mutating a core global registry:

```python
from agent_workflow.plugin_api import (
    PluginCommand,
    PluginDescriptor,
    PluginPackageResource,
)


def configure(parser):
    parser.add_argument("spec")


def execute(args, context):
    return {"spec": args.spec, "state_root": str(context.settings.state_root)}


def plugin():
    return PluginDescriptor(
        name="agent-workflow-spec",
        version="0.1.0",
        commands=(
            PluginCommand(
                name="spec",
                summary="author and compile implementation specifications",
                configure=configure,
                execute=execute,
            ),
        ),
        resources=("agent-workflow-spec://capabilities",),
        package_resources=(
            PluginPackageResource(
                kind="schema",
                identifier="agent-workflow-spec/spec/v1",
                package="agent_workflow_spec",
                path="schemas/spec-v1.json",
                sha256="<lowercase SHA-256 of installed bytes>",
            ),
            PluginPackageResource(
                kind="asset",
                identifier="agent-workflow-spec/templates/v1",
                package="agent_workflow_spec",
                path="templates/default.md",
                sha256="<lowercase SHA-256 of installed bytes>",
            ),
        ),
    )
```

The host stages all enabled descriptors, checks API versions and duplicate plugin/command/schema/asset/resource identifiers, resolves declared package files through `importlib.resources`, verifies normalized relative paths and exact SHA-256 digests, and commits one immutable registry only after the complete set passes. Plugin-owned top-level commands and validated package-resource provenance are included in the full parser-derived maintainer catalog. Plugin commands do not automatically expand the normal orchestrator command profile; optional plugin capabilities are discovered explicitly when needed. Consumers read activated bytes through `PluginRegistry.read_package_resource(kind, identifier)`; arbitrary host paths are never accepted.

## Current boundary

Version 1 supports:

- import-free candidate discovery;
- explicit configured enablement;
- strict API compatibility and collision checks;
- atomic command registration;
- top-level plugin command groups;
- schema, asset, and resource identifiers reserved in the registry;
- digest-bound schema and asset files resolved from installed packages;
- traversal, missing-file, collision, and tamper failures before registry activation;
- read-only activated bytes addressed by exact logical identifier;
- installed-distribution and package-resource provenance in command catalogs;
- a `--no-plugins` recovery path.

A general hook framework remains deferred until multiple real plugins require ordered one-to-many hooks. Package-resource activation does not parse schemas, execute templates, or grant authority; feature code must still route all authority-bearing work through core services.
