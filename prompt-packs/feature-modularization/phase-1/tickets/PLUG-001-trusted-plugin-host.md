# PLUG-001 — close the trusted first-party plugin host

**Backlog:** `PLUG-001`  
**Priority:** P1 / High  
**Current state:** in progress in 0.7.7

## Implemented baseline to preserve

- import-free discovery through `importlib.metadata.entry_points(group="agent_workflow.plugins")`;
- explicit `[plugins].enabled` and global `--no-plugins` recovery;
- versioned `PluginDescriptor`, command declarations, and execution context;
- strict missing/ambiguous/API/collision failure;
- atomic typed registration of plugin-owned top-level commands;
- `agent-workflow plugins list`;
- plugin inventory and distribution provenance in parser-derived command catalogs;
- separately built and installed fixture-plugin wheel acceptance;
- reserved schema, asset, and resource identifiers.

Do not reimplement these surfaces or introduce a second plugin registry.

## Remaining implementation

- Define a bounded package-resource descriptor for plugin schema and asset bundles.
- Resolve resources through `importlib.resources` without arbitrary filesystem traversal, copying plugin files into core, or importing disabled plugins.
- Validate declared bundle existence and identifier collisions as part of the same atomic staging transaction.
- Expose read-only resolved bundle metadata through the registry; activation must remain explicit and must not mutate core authority registries during import.
- Extend the separately installed fixture distribution with real packaged schema/asset resources and prove bounded resolution from the installed wheel.
- Reconcile `docs/PLUGIN_API.md`, the command catalog/evidence description, and backlog state.

## Constraints

Use standard entry points. Do not add Pluggy until at least two real plugins require ordered 1:N hooks. Installed code is trusted executable code; plugin presence never grants runtime authority. Do not create a generic arbitrary-file loader.

## Acceptance

Disabled candidates are not imported, duplicate or incompatible enabled plugins fail deterministically without partial registration, `--no-plugins` restores core commands, the fixture command works from an installed wheel outside the source checkout, and packaged schema/asset bundles resolve only through validated read-only package-resource declarations.

## Writable paths

The stable plugin API/host package, minimal config and CLI registration seams, command-catalog provenance, fixture-plugin package/tests, schema/assets registration support, and directly related documentation.

## Tests

Preserve all existing plugin invariants and installed fixture tests. Add path-traversal, missing-resource, duplicate-resource, disabled-import, atomic rollback, and installed-wheel package-resource cases.

## Stop conditions

Stop if implementation requires plugin code to bypass authority services, import disabled candidates, add a general hook framework, expose arbitrary host paths, or make the base CLI dependent on a plugin.
