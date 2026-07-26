# public-beta-trust-and-release

## Purpose

Add authenticated review, deterministic drift detection, supply-chain evidence, clean-host compatibility, and an explicit public-preview decision gate.

This pack owns `HARD-007`, `HARD-009`, `HARD-010`, `REL-003`, `REL-004`. Canonical status remains in [`BACKLOG.md`](../../docs/BACKLOG.md); the [determinism/security assessment](../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md) supplies the findings and the [hardening plan](../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md) supplies the dependency model.

## External prerequisites

- `FOUND-GATE-01` and `ISO-GATE-01` are accepted.
- HARD-001 through HARD-006 and HARD-008 are integrated.
- REL-001 and REL-002 remain external maintainer prerequisites for the final REL-004 gate.

Do not launch a blocked phase because its prompts are present. The orchestrator must verify prerequisite backlog items and prior phase gates first.

## Phases

1. **Phase 0 — trust, drift, supply chain, and compatibility:** Run four independent public-beta preparation lanes after the technical hardening foundations are accepted.
2. **Phase 1 — public-preview decision gate:** Integrate all lanes and issue an explicit go/no-go decision; no new runtime features.

## Parallel execution

- Phase 0 — trust, drift, supply chain, and compatibility: Run HARD-007, HARD-009, HARD-010, and REL-003 concurrently in separate worktrees/environments.
- Phase 1 — public-preview decision gate: No parallel implementation. REL-004 is an independent release gate and may only make narrow release-blocking fixes.

No dependency edge means the tickets may run concurrently in separate worktrees. Integration and phase review are serialized.

## Non-targets

- MCP-003 mutation implementation.
- Remote/HTTP MCP, multi-host orchestration, web UI, daemon, autonomous routing, or new agent classes.
- Publishing a release without maintainer authorization.

## Validation

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate prompt-packs/public-beta-trust-and-release
```

Use the `release-drift-auditor` skill at every phase gate. A valid pack does not override backlog state, runtime policy, executor/model policy, writable-path policy, or human decisions.
