# Phase 0 — durable shared-window pane identity

## Objective

Make all shared-window lifecycle operations resolve the intended pane by
stable identity rather than mutable pane position, while preserving dedicated
session behavior and an explicit real-orphan outcome.

## Complexity and delegation

| Ticket | Tier | Risk | Dependencies | Reviewer requirement |
|---|---|---|---|---|
| PROC-006 | A | Critical | none | Independent reviewer; run drift audit and live/shared-window regression |

## Ordering

Run `PROC-006` in one isolated worktree and one fresh named session. The
implementation is interactive by default. Phase review and integration are
serialized after the implementation handoff.

## Phase-wide constraints

- The application run/session ID is the authoritative identity.
- A tmux `%pane_id` is the stable locator for a pane while it exists; a pane
  index or `session:window.index` is never authoritative.
- Human pane names are display metadata only and cannot identify a run.
- A pane ID cannot survive actual pane destruction or tmux-server restart;
  recovery must report that fact rather than guessing by name or PID.
- Preserve isolated worktree scope and do not change unrelated messaging,
  provider, or workflow authority.

## Required references

- `references/pane-identity.md`
- `docs/references/WORKTREE_PREFLIGHT.md`
- `docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md`
- `docs/OPERATIONS.md`

## Exit gate

The independent reviewer must inspect the complete diff and run:

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate prompt-packs/tmux-pane-identity-reliability
pytest -q tests/acceptance/test_tmux_pane_identity_journey.py tests/invariants/test_tmux_pane_identity.py
pytest -q
```

When tmux is available, also run the opt-in live shared-window journey and
record its exit code. Verify that the journey adds/removes panes before the
target task completes, and that a genuinely destroyed pane is reported as
orphaned rather than rebound to another agent.
