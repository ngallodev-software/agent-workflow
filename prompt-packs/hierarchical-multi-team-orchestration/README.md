# hierarchical-multi-team-orchestration

Implement the bounded root-orchestrator → team-lead → worker architecture in `docs/HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_DESIGN.md`. Durable contracts and replay precede tmux mutation; accepted managed topology precedes the team-lead runtime; accepted hierarchical messaging precedes root fan-out/fan-in. Do not add arbitrary recursion, a daemon, or multi-host transport.

## Execution gates

- `DEC-005` is approved; `HIER-001` may execute when its canonical backlog state is `ready`.
- `PROC-006` must be accepted before `HIER-003`.
- `MSG-001`, `PROC-001`, and `PROC-002` must be accepted before `HIER-005`.
- `BKL-002` must be accepted before `HIER-006`.
- Manifest `dependencies` are authoritative for all in-pack ordering.

The core path is `HIER-001` → `HIER-002` → `HIER-GATE-0` → `HIER-003` → `HIER-GATE-1` → `HIER-005` → `HIER-006` → `HIER-GATE-2` → `HIER-007` → `HIER-008` → `HIER-GATE-3`.

The external-terminal path is optional and independently reviewed: `HIER-003` → `HIER-004` → `HIER-GATE-1A`. It does not block the core path.

## Feature-module boundary

Hierarchy is a first-party built-in feature, not unconditional core behavior. New hierarchy-specific implementation belongs under `src/agent_workflow/features/hierarchy/` (or an equivalently narrow package approved by the phase gate). Existing core modules may expose small stable services/facades, but tickets must not grow `sessions.py`, `scheduler.py`, `cli.py`, or tmux modules with hierarchy-only policy and state. Direct single-level orchestration remains the default compatibility path, and hierarchy requires explicit enablement.
