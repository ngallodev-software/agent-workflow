# tmux-operator-experience

## Purpose

Implement an `agent-workflow`-native tmux operator experience based on selected UX ideas from the reviewed `tmux-agent-status` repository: an attention-sorted popup with pane preview, a cache-backed status line, lifecycle-aware actions, event-hint refresh, and a dedicated dashboard window.

Do not vendor the reviewed plugin. `agent-workflow` remains authoritative for run identity, lifecycle, message/review state, receipts, worktrees, and destructive actions.

## Mandatory external prerequisite

Core implementation must not begin until [`PROC-006`](../../docs/BACKLOG.md) is accepted with live-host and sealed evidence. The UI consumes stable pane identity; it must not duplicate or weaken pane-binding migration/recovery.

The optional embedded sidebar (`TMUXUI-008`) additionally requires:

1. accepted `TMUXUI-GATE-001` core review; and
2. explicit maintainer authorization changing the canonical backlog item from `needs-decision`.

The existence of the Phase 4 prompt is not authorization.

## References

Read in this order:

1. [`docs/TMUX_OPERATOR_EXPERIENCE_RECOMMENDATION.md`](../../docs/TMUX_OPERATOR_EXPERIENCE_RECOMMENDATION.md)
2. [`docs/TMUX_OPERATOR_EXPERIENCE_BACKLOG_SEQUENCE.md`](../../docs/TMUX_OPERATOR_EXPERIENCE_BACKLOG_SEQUENCE.md)
3. [`references/PRIOR_ART_ANALYSIS.md`](references/PRIOR_ART_ANALYSIS.md)
4. [`references/IMPLEMENTATION_SEQUENCE.md`](references/IMPLEMENTATION_SEQUENCE.md)
5. current `src/agent_workflow/tmux.py`, `sessions.py`, `state.py`, `orchestrator_inbox.py`, `lifecycle.py`, `cli.py`, and existing pane-identity tests

Current checked-out source and accepted schemas/tests outrank included planning references.

## Phase map

| Phase | Tickets | Objective | Parallelism |
|---|---|---|---|
| 0 | TMUXUI-001 | Authoritative read model and attention contract | Serial foundation |
| 1 | TMUXUI-002, 003, 004 | Status cache, popup/preview, opt-in integration | Three separate worktrees after Phase 0 |
| 2 | TMUXUI-005, 006, 007 | Actions, dashboard, refresh/repair | Parallel according to manifest edges |
| 3 | TMUXUI-009, TMUXUI-GATE-001 | Installed/live/security evidence and independent core gate | Serial closeout |
| 4 | TMUXUI-008 | Optional UI role/sidebar | Blocked on decision after core acceptance |
| 5 | TMUXUI-GATE-002 | Independent optional-sidebar review | Serial gate |

## Clean-room/provenance rule

The prior-art archive is an idea source only. Do not copy source, tests, comments, or distinctive text unless the maintainer supplies and approves the actual license/attribution terms. Record any approved copied material explicitly.

## Universal implementation rules

- Use one isolated worktree and one named session per writable ticket.
- Run exact-worktree preflight and record source/prompt digests.
- Enforce manifest dependencies; prose cannot make blocked work ready.
- Keep shell/tmux assets thin. Python owns snapshot construction, ranking, sanitization, cache writes, and action routing.
- Never add shell-owned lifecycle statuses or heuristic managed-agent discovery.
- Never use mutable pane indexes as identity.
- Never directly kill managed tmux panes from UI scripts; use existing services.
- Preserve existing tmux hooks/options/keybindings and make integration opt-in and reversible.
- Add only focused invariant tests plus installed-product journeys; include opt-in live tmux evidence at Phase 3.
- Update canonical docs/help/config/man pages with implementation, not before behavior exists.
- Run `python3 scripts/audit-release-assets.py`, pack validation, focused tests, installed journeys, and release checks before a gate.

## Completion

Each implementation ticket produces the strict completion handoff and exact command/exit-code evidence. Gate reviewers inspect the integrated tree and sealed receipts independently; green unit tests alone are not acceptance.
