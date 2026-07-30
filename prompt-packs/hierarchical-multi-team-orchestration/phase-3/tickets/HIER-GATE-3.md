# HIER-GATE-3 — final hierarchical orchestration gate

Review only. Execute the full installed-product journey, restart/tamper matrix,
release audit, package validation, documentation/skill drift review, and provide
an evidence-backed accept/reject decision.

## Dependencies and lane

- Depends on `HIER-008`.
- Final core hierarchy acceptance gate. The optional adapter is accepted separately by `HIER-GATE-1A` when implemented.

## Writable scope

Review reports and evidence artifacts only. Do not implement new behavior or edit the canonical backlog from the gate session.

## Required tests and evidence

Run the focused acceptance/invariant matrix for the phase, package validation, release asset audit, documentation/skill drift checks, and any required live tmux host journey. Record exact commands and exit codes.

## Acceptance criteria

Issue an evidence-backed accept or reject decision against every phase ticket and design invariant. Unverified behavior, mutable projections, terminal prose, or pane liveness are not acceptance evidence.

## Stop conditions

Stop and reject the phase on missing sealed evidence, authority drift, duplicate-launch risk, unbounded capability, positional tmux identity, shell execution, stale documentation, or unresolved release-audit findings.
