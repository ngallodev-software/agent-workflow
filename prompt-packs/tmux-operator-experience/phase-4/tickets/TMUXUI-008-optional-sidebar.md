# TMUXUI-008 — optional embedded sidebar and first-class UI pane role

**Backlog:** [`TMUXUI-008`](../../../../docs/BACKLOG.md)  
**Dependencies:** TMUXUI-GATE-001 accepted  
**Decision gate:** explicit maintainer authorization is required while the backlog state is `needs-decision`.

## Goal

Only if authorized, introduce a first-class `@agent-workflow-role=ui` and an opt-in embedded sidebar that cannot alter agent capacity accounting, deterministic work-window layout, orchestrator placement, or stable run identity.

## Writable paths

- Role-aware tmux pane inventory/capacity/layout logic.
- Sidebar renderer/controller and opt-in configuration/assets.
- Focused layout invariants and opt-in live stress journey.
- Sidebar-specific operations/install/uninstall docs.

Do not change core snapshot authority, create the sidebar globally, or make it required for popup/dashboard operation.

## Required behavior

- Define and consistently apply a `ui` role distinct from `agent` and `orchestrator`.
- Count capacity from live managed `agent` panes only.
- Exclude UI panes from agent column selection, split placement, reusable-agent discovery, and lifecycle inventory.
- Make sidebar opt-in per session/window with explicit minimum dimensions and graceful refusal/collapse.
- Open/close during concurrent launches without renumbering/rebinding semantics or orchestrator displacement.
- Preserve popup/dashboard as fully functional alternatives.
- Remove all sidebar panes/options/hooks cleanly.

## Acceptance and tests

- Invariant matrix for role-aware pane counts/layout.
- Opt-in real tmux stress: repeated open/close, concurrent launches, pane exits, window resize, layout change, and session restart.
- Before/after evidence for capacity, columns, geometry, orchestrator, stable run bindings, and cleanup.
- Narrow terminal and capacity-boundary cases.

## Stop conditions

Stop immediately if maintainer authorization is absent, if layout calculations cannot be made role-aware without broad destabilization, or if live stress reveals nondeterministic placement/rebinding. The acceptable outcome may be to retain dashboard-only persistent UX. Use `templates/TICKET_COMPLETION.md`.
