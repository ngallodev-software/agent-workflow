# PROC-005 — operator policy, reminders, and recovery references

**Backlog:** [`PROC-005`](../../../../docs/BACKLOG.md)

## Goal

Make the reliable launch/observe/close pattern obvious and repeatable in the
repo’s steering index, skills, templates, hooks, and runbook without claiming
controls that phase 0 did not implement.

## Writable paths

- `AGENTS.md` or its tracked steering equivalent, relevant `skills/`,
  `docs/references/`, `templates/`, and existing hook/reminder scripts.
- No runtime code unless a phase-0 evidence gap requires a narrowly scoped
  correction.

## Acceptance

- Implementation launches are interactive-first; exploration/research may be
  structured non-interactive; pane-capacity fallback is explicit.
- Launch, handshake, observation, retry, completion validation, and closeout
  commands are documented with evidence requirements.
- Reminder hooks identify the correct control-plane command and never claim
  that terminal/TUI output is evidence.
- Templates require substantive identity, scope, commands, exit codes,
  communication evidence, and unresolved issues.
- Stale or contradictory steering text is removed or moved to a references
  folder with an explicit read-when-needed boundary.
- Add or update a documentation/installer smoke test where the public surface
  is executable, and report its exit code.

## Stop conditions

Stop rather than add prompt-only enforcement when the desired behavior is not
implemented in a deterministic service. Use `templates/TICKET_COMPLETION.md`.
