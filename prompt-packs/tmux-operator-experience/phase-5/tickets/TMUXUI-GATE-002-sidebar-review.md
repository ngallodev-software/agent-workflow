# TMUXUI-GATE-002 — independent optional-sidebar and layout review

This is a gate task and claims no backlog ownership. It may not repair implementation.

## Writable paths

Only the phase-gate report and permitted review evidence.

## Acceptance review

Verify:

- explicit maintainer authorization existed before implementation;
- `ui`, `agent`, and `orchestrator` roles are distinct across every inventory/capacity/layout/reuse path;
- opening/closing the sidebar under concurrent launch and resize leaves deterministic agent columns and stable run bindings;
- narrow/capacity boundary behavior is safe;
- no sidebar is auto-created globally;
- popup/dashboard remain independent;
- uninstall removes panes/options/hooks/cache/workers and preserves unrelated tmux configuration;
- existing pane-identity, launch, lifecycle, installed-product, and release-drift checks pass.

## Test evidence

Run the opt-in real tmux stress journey yourself and record versions, exact commands, exit codes, pane inventories, and cleanup in `templates/PHASE_GATE_REPORT.md`.

## Stop/reject conditions

Reject if any UI pane is counted as an agent, capacity changes when opening/closing the sidebar, a run can be rebound by location, orchestrator placement shifts nondeterministically, global autocreation occurs, or removal is incomplete. Acceptance of the core popup/status/dashboard remains separate.
