# deterministic-enforcement-foundations

## Purpose

Close the P0 process, filesystem, authority, and read-only MCP gaps that underpin every later hardening task.

This pack owns `HARD-001`, `HARD-002`, `HARD-004`, `HARD-005`. Canonical status remains in [`BACKLOG.md`](../../docs/BACKLOG.md); the [determinism/security assessment](../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md) supplies the findings and the [hardening plan](../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md) supplies the dependency model.

## External prerequisites

- None; this is the first hardening pack.

Do not launch a blocked phase because its prompts are present. The orchestrator must verify prerequisite backlog items and prior phase gates first.

## Phases

1. **Phase 0 — bounded execution and artifact integrity:** Build the two independent foundations that every later security control depends on.
2. **Phase 1 — immutable authority and MCP read boundary:** Use the phase-0 controls to eliminate projection authority and close the current read-only MCP disclosure/path gaps.
3. **Phase 2 — independent foundation gate:** Integrate, rerun shared journeys, audit drift, and accept or reject the foundation.

## Parallel execution

- Phase 0 — bounded execution and artifact integrity: Run HARD-001 and HARD-002 concurrently. Their primary writable surfaces are process execution versus pack/path/schema integrity.
- Phase 1 — immutable authority and MCP read boundary: Run HARD-004 and HARD-005 concurrently after their declared dependencies are accepted.
- Phase 2 — independent foundation gate: No parallel implementation. Use an independent review agent.

No dependency edge means the tickets may run concurrently in separate worktrees. Integration and phase review are serialized.

## Non-targets

- Preventative OS sandboxing (HARD-003).
- Authenticated principals (HARD-007).
- MCP mutation tools (MCP-003).
- Remote transport, multi-host orchestration, or new scheduler infrastructure.

## Validation

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate prompt-packs/deterministic-enforcement-foundations
```

Use the `release-drift-auditor` skill at every phase gate. A valid pack does not override backlog state, runtime policy, executor/model policy, writable-path policy, or human decisions.
