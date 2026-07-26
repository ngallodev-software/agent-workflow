# orchestrator-two-way-messaging

## Purpose

Implement reliable two-way messaging between spawned agents and the orchestrator without making tmux, terminal output, polling, or prompt prose authoritative.

The target architecture is documented in [`docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md`](../../docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md). This pack owns `BKL-001`, `BKL-002`, and `MSG-001` through `MSG-007`. Canonical status remains in [`BACKLOG.md`](../../docs/BACKLOG.md).

## Collision-free ownership

- `BKL-001` and `BKL-002` existed in the backlog but were not owned by another active pack. This pack becomes their sole implementation owner.
- `MSG-*` is a new namespace reserved for this messaging implementation.
- `DEC-001` is a prerequisite decision and is not owned by this pack.
- `HARD-*` controls remain owned by the existing hardening packs.
- `MCP-003` remains owned by `mcp-server-next`; this pack exposes shared services that a later authorized MCP tool may call, but implements no MCP mutation surface.

See [`references/collision-and-ownership.md`](references/collision-and-ownership.md).

## External prerequisites

Do not start phase 0 until:

- `DEC-001` has an explicit accepted decision;
- `HARD-002` and `HARD-004` are accepted.

Later tickets additionally require the exact `HARD-*` prerequisites named in their prompts. The complete pack should not pass its final gate until `HARD-001`, `HARD-006`, `HARD-007`, and `HARD-008` are accepted.

Presence of this pack does not make a blocked backlog item executable.

## Phases

1. **Phase 0 — durable fan-in foundations:** Run `BKL-001` and `MSG-001` in parallel.
2. **Phase 1 — supervisor and late delivery:** Run `MSG-002` and `BKL-002` in parallel after phase 0.
3. **Phase 2 — safe wake/resume and restart reconstruction:** Run `MSG-003` and `MSG-005` in parallel after `MSG-002`.
4. **Phase 3 — acknowledgement and scheduling semantics:** Implement `MSG-004` after the wake and recovery surfaces stabilize.
5. **Phase 4 — adversarial hardening and acceptance:** Run `MSG-006` and `MSG-007` concurrently with separate writable scopes.
6. **Phase 5 — independent gate:** Run `MSG-GATE-01` against the integrated tree.

## Parallel execution

Parallel tickets use separate worktrees and sessions. They may not share a writable checkout.

- Phase 0 divides per-session consumer-cursor work from the new orchestrator registry/inbox store.
- Phase 1 divides supervisor fan-in from executor-specific child steering adapters.
- Phase 2 divides orchestrator wake/resume adapters from restart reconstruction.
- Phase 4 divides security implementation/invariant matrices from installed-product and opt-in live compatibility journeys.

Integration and phase review are serialized.

## Non-targets

- Redis, NATS, SQLite migration, remote transport, or multi-host orchestration.
- A second workflow scheduler or lifecycle state machine.
- Terminal scraping, prompt parsing, or process silence as authority.
- Arbitrary shell hooks or child-controlled text injection into the orchestrator pane.
- MCP mutation tools.
- An always-on system daemon or implicit host startup changes.

## Validation

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate prompt-packs/orchestrator-two-way-messaging
```

Use `release-drift-auditor` at every phase gate. Validate backlog state and external prerequisites immediately before launching each ticket.
