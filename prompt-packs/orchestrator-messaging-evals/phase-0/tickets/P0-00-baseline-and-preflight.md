# P0-00 — Research and contract decision

## Role and objective

Act as a research lead. Compare local filesystem inbox/outbox, `tmux wait-for`
and control mode, SQLite WAL, Redis Streams, NATS JetStream, and Temporal
signals. Use primary documentation only. Write
`docs/MESSAGING_PRIOR_ART_REPORT.md` with a decision matrix.

## Required conclusions

- Choose authority, wakeup accelerator, replay rule, idempotency identity, ack
  ordering, retention bound, and failure recovery behavior.
- Explain why arbitrary `tmux send-keys` is not proof of semantic prompt
  delivery and what an executor adapter must acknowledge.
- Cover path/symlink, multiwriter, partial-write, duplicate-delivery, payload,
  and local-authority threats with concrete mitigations.

## Writable paths

`docs/MESSAGING_PRIOR_ART_REPORT.md` only. Do not modify runtime code.

## Acceptance and stop

Provide at least five primary-source links and a source-backed recommendation.
Stop if the design requires a new service or unverified executor behavior.

## Tests

No runtime tests. Verify each cited link and compare every contract field with
the current source before declaring the research complete.
