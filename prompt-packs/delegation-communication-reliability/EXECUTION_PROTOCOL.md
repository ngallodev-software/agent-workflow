# Execution protocol

## Authority

Current source, public parsers, schemas, sealed lifecycle receipts, and the
active pack manifest are authoritative in that order. Mutable projections,
terminal output, and historical archives are not authority.

## Implementation rules

- Use a dedicated worktree and stable `ticket`/`pack` identity.
- Start implementation interactively unless the operator explicitly selects a
  structured non-interactive fallback.
- In a new worktree, follow [`docs/references/WORKTREE_PREFLIGHT.md`](../../docs/references/WORKTREE_PREFLIGHT.md): probe codebase-memory once and use an exact-worktree index when available. If unavailable, record the limitation and continue with bounded RTK discovery without retrying. This is optional operator tooling, not an application dependency.
- Use the graph before structural code discovery when available, and RTK for shell work in every case.
- Keep child communication append-only and correlated. Tmux wakeups are hints,
  never delivery proof.
- Never let a child-controlled message select a lifecycle authority or mutate a
  sealed/read-only parent projection.
- Preserve failed, skipped, unavailable, and rejected evidence.
- Do not broaden into BKL-002/MSG-* runtime work or add a second scheduler.

## Required evidence

Every implementation handoff uses `templates/TICKET_COMPLETION.md` and names
the ticket, pack, revision, changed paths, non-targets, acceptance journeys,
invariant matrix, commands with exit codes, communication events, unresolved
issues, and no-drift result. Placeholder-only reports fail validation.

The independent gate uses `templates/PHASE_GATE_REPORT.md`. Acceptance requires
independent review, valid completion and final-receipt evidence, correlated
control-plane evidence, a substantive completion report, and a clean release
drift audit.
