# PROC-002 — durable control-plane handshake

**Backlog:** [`PROC-002`](../../../../docs/BACKLOG.md)

## Goal

Make launch communication testable and truthful. A child progress update must
be durably appended through the supported service path, and steering must have
correlated delivered/applied/rejected evidence when the executor supports it.

## Writable paths

- `src/agent_workflow/messages.py`, `src/agent_workflow/runner.py`,
  `src/agent_workflow/sessions.py`, `src/agent_workflow/agent_context.py`,
  `src/agent_workflow/metrics.py`, and the existing control-event schema or a
  narrowly named schema revision.
- Focused installed-product handshake journey and compact correlation matrix.

## Acceptance

- Launch performs a bounded progress/ack handshake before reporting healthy
  execution.
- Child communication never writes a sealed or read-only parent projection;
  append-only control events remain the authority.
- Delivery, application, rejection, and unavailable-adapter outcomes are
  distinct, correlated, idempotent, and visible in sealed evidence.
- Tmux wakeups remain hints and cannot make terminal text count as delivery.
- A failed communication attempt remains evidence and does not disappear on
  retry.
- A workspace-sandboxed child must not write the host state root or invoke the
  tmux socket. It writes only a bounded, atomic, worktree-local control intent
  in its handoff directory; the host runner validates identity/digest/sequence,
  appends the authoritative host control event, and performs any tmux or
  lifecycle action.
- `progress`, `ack`, and `task-complete` must either use that bridge or return
  an explicit unavailable outcome. They must not fail merely because the child
  lacks host filesystem or tmux permissions when the host runner is available.
- Add an installed-product sandbox fixture that denies the child host-state and
  tmux access while proving a bridged progress/ack/completion request is
  persisted, correlated, and sealed by the host. Include duplicate, malformed,
  stale, and post-exit requests in the compact matrix.

## Non-targets and stop conditions

Do not implement late steering semantics owned by BKL-002 or the MSG-* inbox,
supervisor, or wake/resume features. Stop if the adapter cannot provide a
correlated acknowledgement, if a request would allow child-controlled tmux
arguments or arbitrary host paths, or if a bridge would trust an unsealed
mutable status projection; record unavailable evidence instead of inventing
success. Use `templates/TICKET_COMPLETION.md`.
