# Trusted plugin API

`agent-workflow` 0.7.7 includes the first version of its trusted in-process plugin host. The boundary exists to keep optional capabilities modular; it is not a sandbox and installing or enabling a plugin does not grant workflow, permission, review, or acceptance authority.

## Enablement and recovery

Plugins are Python distributions advertising the `agent_workflow.plugins` entry-point group. Discovery reads package metadata only. A candidate module is imported only when its entry-point name appears in configuration:

```toml
[plugins]
enabled = ["agent-workflow-spec"]
```

Every configured plugin is required to be installed, uniquely discoverable, and compatible with the current plugin API. A failure stops command registration before a parser or registry is exposed. Use the global recovery option to start the core product without importing configured plugins:

```bash
agent-workflow --no-plugins plugins list
agent-workflow --no-plugins doctor
```

`agent-workflow plugins list --json` reports discovered distribution metadata, configured enablement, load state, and suppression state.

## Public descriptor

An entry point exports either a `PluginDescriptor` or a zero-argument callable returning one. Commands are declared without mutating a core global registry:

```python
from agent_workflow.plugin_api import PluginCommand, PluginDescriptor


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
        schemas=("agent-workflow-spec/spec/v1",),
        assets=("agent-workflow-spec/templates/v1",),
        resources=("agent-workflow-spec://capabilities",),
    )
```

The host stages all enabled descriptors, checks API versions and duplicate plugin/command/schema/asset/resource identifiers, and commits one immutable registry only after the complete set passes. Plugin-owned top-level commands are included in the parser-derived command catalog and in orchestrator command cards.

## Current boundary

Version 1 supports:

- import-free candidate discovery;
- explicit configured enablement;
- strict API compatibility and collision checks;
- atomic command registration;
- top-level plugin command groups;
- schema, asset, and resource identifiers reserved in the registry;
- installed-distribution provenance in command catalogs;
- a `--no-plugins` recovery path.

The next PLUG-001 slice must define bounded package-resource resolution and validation for declared schema and asset bundles before those declarations become active host resources. A general hook framework remains deferred until multiple real plugins require ordered one-to-many hooks.
