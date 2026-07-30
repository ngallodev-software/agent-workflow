# HIER-GATE-2 — team runtime and messaging review

Review only. Verify canonical launch reuse, capability boundaries, durable
message semantics, escalation chains, restart behavior, and attack cases.

## Dependencies and lane

- Depends on `HIER-006`.
- Critical path; acceptance unblocks `HIER-007`.

## Writable scope

Review reports and evidence artifacts only. Do not implement new behavior or edit the canonical backlog from the gate session.

## Required tests and evidence

Run the focused acceptance/invariant matrix for the phase, package validation, release asset audit, documentation/skill drift checks, and any required live tmux host journey. Record exact commands and exit codes.

## Acceptance criteria

Issue an evidence-backed accept or reject decision against every phase ticket and design invariant. Unverified behavior, mutable projections, terminal prose, or pane liveness are not acceptance evidence.

## Stop conditions

Stop and reject the phase on missing sealed evidence, authority drift, duplicate-launch risk, unbounded capability, positional tmux identity, shell execution, stale documentation, or unresolved release-audit findings.
