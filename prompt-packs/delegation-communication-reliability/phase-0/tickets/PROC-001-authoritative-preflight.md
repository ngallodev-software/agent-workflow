# PROC-001 — authoritative launch preflight

**Backlog:** [`PROC-001`](../../../../docs/BACKLOG.md)

## Goal

Prevent a delegation from stopping or proceeding based on stale mutable
projections. Launch preflight must resolve prerequisite acceptance from live
lifecycle receipts and immutable run evidence.

## Writable paths

- `src/agent_workflow/sessions.py`, `src/agent_workflow/cli.py`, and one
  narrowly scoped preflight/helper module if needed.
- Focused installed-product acceptance journey and compact prerequisite matrix.
- Current operations/help documentation only where behavior changes.

## Acceptance

- A preflight distinguishes accepted, rejected, missing, and stale prerequisite
  evidence using lifecycle receipts. `missing` means the prerequisite run or
  receipt chain is absent; `stale` means the chain cannot be bound to the
  current sealed final-receipt digest or fails immutable-chain validation.
- An old `status.json` or exported archive cannot override a current accepted
  or rejected disposition.
- An accepted lifecycle receipt is usable only when its final-receipt digest is
  verified against the current sealed final receipt; missing, replaced, or
  digest-mismatched sealed evidence must not be accepted.
- A failed preflight records a durable reason and does not create a misleading
  running session.
- An installed launch journey proves the behavior through the public CLI.
- Add or update focused installed-product tests for accepted, rejected,
  missing, stale/digest-mismatched, and mutable-projection cases, and report
  each exit code.

## Non-targets and stop conditions

Do not implement BKL-002, MSG-*, actor authentication, or a second scheduler.
Stop if the source lacks an immutable receipt or if repair would rewrite sealed
evidence. Use `templates/TICKET_COMPLETION.md`.
