# PROC-002 — durable control-plane handshake

**Backlog:** [`PROC-002`](../../../../docs/BACKLOG.md)

## Goal

Make launch communication testable and truthful. A child progress update must
be durably appended through the supported service path, and steering must have
correlated delivered/applied/rejected evidence when the executor supports it.

## Writable paths

- `src/agent_workflow/messages.py`, `src/agent_workflow/metrics.py`, and the
  existing control-event schema or a narrowly named schema revision.
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

## Non-targets and stop conditions

Do not implement late steering semantics owned by BKL-002 or the MSG-* inbox,
supervisor, or wake/resume features. Stop if the adapter cannot provide a
correlated acknowledgement; record unavailable evidence instead of inventing
success. Use `templates/TICKET_COMPLETION.md`.
