# ChatGPT handoff — public beta trust and release

Treat current source, [`BACKLOG.md`](../../BACKLOG.md), the [feature assessment](../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md), and the [hardening plan](../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md) as authoritative.

1. Run the deterministic release drift audit and validate this pack.
2. Confirm all external prerequisites and prior phase gates.
3. Launch independent tickets concurrently only when the manifest has no dependency edge between them; use separate worktrees and durable sessions.
4. Require installed-product acceptance evidence first and retain only compact security/state invariant matrices.
5. Integrate completed tickets, rerun shared journeys, then delegate the gate to an independent reviewer using both `phase-gate-review` and `release-drift-auditor`.
6. Stop on backlog ownership collisions, newer conflicting architecture, missing security prerequisites, or guidance that is being mislabeled as deterministic enforcement.

Do not add an alternate scheduler, daemon, database, web UI, remote transport, memory layer, persona taxonomy, autonomous routing, or unrelated cleanup.
