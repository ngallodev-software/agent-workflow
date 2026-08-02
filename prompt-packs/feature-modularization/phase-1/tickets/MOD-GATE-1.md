# MOD-GATE-1 — plugin-host gate

Independently inspect discovery, explicit enablement, atomic registration, collision handling, recovery mode, installed fixture evidence, command-catalog provenance, and documentation. Confirm the host is a modularity boundary rather than a sandbox or authorization shortcut.

## Writable paths

Review evidence only. Do not modify production source.

## Acceptance

Accept only when candidate discovery is import-free, activation is explicit, registration is atomic, collisions fail deterministically, provenance is sealed, and core commands recover with `--no-plugins`.

## Tests

Build and install the core wheel plus the fixture-plugin wheel in a clean environment and independently rerun all plugin-host acceptance cases.

## Stop conditions

Reject authorization-by-presence, partial registration, hidden imports, unversioned API exposure, or a base-install dependency on the fixture plugin.

