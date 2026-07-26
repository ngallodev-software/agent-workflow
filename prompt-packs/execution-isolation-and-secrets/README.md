# execution-isolation-and-secrets

## Purpose

Convert writable-scope, credential, network, executable-trust, and sensitive-content guidance into enforceable local controls.

This pack owns `HARD-008`, `HARD-003`, `HARD-006`. Canonical status remains in [`BACKLOG.md`](../../BACKLOG.md); the [determinism/security assessment](../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md) supplies the findings and the [hardening plan](../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md) supplies the dependency model.

## External prerequisites

- `FOUND-GATE-01` from `deterministic-enforcement-foundations` is accepted.
- HARD-001, HARD-002, HARD-004, and HARD-005 are integrated.

Do not launch a blocked phase because its prompts are present. The orchestrator must verify prerequisite backlog items and prior phase gates first.

## Phases

1. **Phase 0 — config and executor trust:** Make runtime policy and executable identity explicit before applying a sandbox.
2. **Phase 1 — preventative isolation and sensitive content:** Implement the execution barrier and disclosure/retention controls in parallel on separate surfaces.
3. **Phase 2 — independent isolation gate:** Integrate and attack the sandbox and redaction/retention boundaries.

## Parallel execution

- Phase 0 — config and executor trust: One implementation ticket; do not overlap its config/process policy changes with later sandbox work.
- Phase 1 — preventative isolation and sensitive content: Run HARD-003 and HARD-006 concurrently after HARD-008 is accepted.
- Phase 2 — independent isolation gate: No parallel implementation; use an independent reviewer.

No dependency edge means the tickets may run concurrently in separate worktrees. Integration and phase review are serialized.

## Non-targets

- Remote execution, Kubernetes, or a long-running sandbox daemon.
- Authenticated human principals (HARD-007).
- Provider benchmarking or MCP mutation.
- General-purpose DLP, vault, or content-indexing systems.

## Validation

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate prompt-packs/execution-isolation-and-secrets
```

Use the `release-drift-auditor` skill at every phase gate. A valid pack does not override backlog state, runtime policy, executor/model policy, writable-path policy, or human decisions.
