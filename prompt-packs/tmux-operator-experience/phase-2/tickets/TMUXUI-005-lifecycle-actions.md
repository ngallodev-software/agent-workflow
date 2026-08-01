# TMUXUI-005 — lifecycle-aware actions and next-attention navigation

**Backlog:** [`TMUXUI-005`](../../../../docs/BACKLOG.md)  
**Dependencies:** TMUXUI-003, TMUXUI-004

## Goal

Add operator actions to the popup/dashboard while preserving existing lifecycle, message, review, identity, and receipt authority.

## Writable paths

- A focused action-dispatch/revalidation service.
- Popup/dashboard action bindings and minimal CLI service wiring.
- Tests for state/action matrix, stale selection, confirmations, evidence routing, and installed behavior.
- Command/operations docs for implemented actions.

Avoid rewriting lifecycle implementations, authorization policy, inbox schemas, scheduler authority, or direct pane-kill scripts.

## Required behavior

- Re-read/revalidate the selected run and stable pane binding immediately before mutation.
- Compute allowed actions from current durable/observed/review/message state.
- Require explicit confirmation for destructive actions and support cancellation with no mutation.
- Route interrupt, terminate, kill, restart, archive, acknowledgement, and review operations through existing services or their public command service boundary.
- Preserve existing actor/authentication semantics; do not invent trusted principals or weaken HARD-007's future boundary.
- Show exact authoritative success/failure; do not optimistically remove or relabel rows.
- Implement deterministic `next` selection from central attention ranking.
- Protect against command injection: pass structured arguments, never concatenate untrusted shell commands.

## Acceptance and tests

- Spies/receipts prove managed destructive actions use lifecycle services before tmux removal.
- Stale row after restart/reuse/pane loss cannot target a replacement run.
- Failed lifecycle action leaves the item visible with refreshed truth.
- Confirmation cancellation, unavailable action, concurrent completion, and actor-required message/review cases.
- Installed-product journey executes at least focus/next plus one confirmed lifecycle operation and verifies evidence.

## Stop conditions

Stop if an action requires bypassing current authorization/lifecycle services, if a UI-owned status transition is proposed, or if destructive behavior occurs before durable intent/outcome evidence. Use `templates/TICKET_COMPLETION.md`.
