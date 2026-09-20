# Trusted plugin API

`agent-workflow` 0.11.0 includes the trusted in-process plugin host. The boundary exists to keep optional capabilities modular; it is not a sandbox and installing or enabling a plugin does not grant workflow, permission, review, or acceptance authority.

## Enablement and recovery

Plugins are Python distributions advertising the `agent_workflow.plugins` entry-point group. Discovery reads package metadata only. A candidate module is imported only when its entry-point name appears in configuration:

```toml
[plugins]
enabled = ["example-plugin"]
```

`example-plugin` is an illustrative external plugin name; it is enabled
only when that plugin's release artifact is installed in the same Python
environment as the host. The host does not download plugin source dynamically.

Every configured plugin is required to be installed, uniquely discoverable, and compatible with the current plugin API when a plugin-aware surface is requested. Normal built-in lifecycle commands skip plugin discovery entirely; plugin inventory, doctor/completion, the full maintainer catalog, and unknown top-level commands load the configured registry on demand. A plugin registration failure therefore blocks plugin-aware surfaces without adding import/discovery cost to ordinary Agent Run operations. Use the global recovery option to suppress configured plugins explicitly:

```bash
agent-workflow --no-plugins plugins list
agent-workflow --no-plugins doctor
```

`agent-workflow plugins list --json` reports discovered distribution metadata, configured enablement, load state, and suppression state.

## Ingesting an external plugin release

An external plugin is consumed as an immutable installed distribution, not as a
checkout or a vendored source tree. The host-side input is the plugin release
artifact (normally a wheel) plus its `plugin-integration-handoff/v1` record.
Before installation, the host verifies that the record names the supplied
artifact filename and exact lowercase SHA-256, and records the plugin version
and target host API version. It then installs that exact artifact into an
isolated environment containing the target Agent-Workflow product. The
handoff is an input and compatibility record; it does not grant the plugin
authority over Agent Runs, policy, evaluation, review, or acceptance.

After installation, add the plugin entry-point name to `[plugins].enabled` and
use `agent-workflow plugins list --json` (or another plugin-aware surface) to
verify discovery and loading. The host checks the plugin's declared
`PluginDescriptor.api_version` against the host's supported plugin API and
reports the installed distribution and plugin versions. A compatible plugin
API does not by itself certify the plugin's product or SDK compatibility: the
plugin owns that matrix, and host qualification records the exact tested
Agent-Workflow/plugin/SDK pair separately. The host must not infer that
qualification from the handoff or from API compatibility alone.

For an operator rollback, remove the plugin name from `[plugins].enabled` or
use the global `--no-plugins` option, install a previously qualified wheel in
the same environment, and repeat the inventory/doctor checks. Suppression is
host recovery; it does not mark the plugin compatible or change Agent Run
authority.

If the candidate is missing, has the wrong digest, is not installed, or fails
the host API check, do not substitute a source checkout or silently continue
with another version. Disable the entry or use `--no-plugins` for core-only
recovery, then resolve the release-artifact or compatibility issue before
claiming qualification. No plugin-specific dependency belongs in
Agent-Workflow's core dependencies.

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
