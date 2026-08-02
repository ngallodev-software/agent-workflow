# PLUG-001 — independently review the trusted first-party plugin host

**Backlog:** `PLUG-001`  
**Priority:** P1 / High  
**Current state:** implementation complete; MOD-GATE-1 pending

## Implemented surface to review

- import-free discovery through `importlib.metadata.entry_points(group="agent_workflow.plugins")`;
- explicit `[plugins].enabled` and global `--no-plugins` recovery;
- versioned `PluginDescriptor`, command declarations, and execution context;
- strict missing/ambiguous/API/collision failure;
- atomic typed registration of plugin-owned top-level commands;
- `agent-workflow plugins list`;
- plugin inventory and distribution provenance in parser-derived command catalogs;
- normalized package-relative schema/asset declarations resolved through `importlib.resources`;
- exact lowercase SHA-256 verification, missing-file/traversal/symlink/tamper rejection, and read-only identifier lookup;
- separately built and installed fixture-plugin wheel acceptance with real package data.

## Review constraints

Do not add scope while performing the gate. Use standard entry points. Do not add Pluggy until at least two real plugins require ordered 1:N hooks. Installed code is trusted executable code; plugin presence and package-resource activation never grant runtime authority. Do not create a generic arbitrary-file loader.

## Acceptance

Accept MOD-GATE-1 only if disabled candidates are not imported; duplicate, incompatible, missing, traversing, symlinked, or tampered declarations fail deterministically without partial registration; `--no-plugins` restores core commands; the fixture command and resources work from an installed wheel outside the source checkout; and command catalogs preserve plugin/resource provenance.

## Writable paths

Review evidence and, only for a demonstrated defect, the stable plugin API/host, tests, schemas, and directly related documentation.

## Stop conditions

Stop and reject the gate if implementation bypasses authority services, imports disabled candidates, accepts arbitrary host paths, mutates core registries during plugin import, or makes the base CLI depend on a plugin.
