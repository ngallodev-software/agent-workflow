# HIER-GATE-1 — managed tmux core review

Review only. Verify stable session/window/pane identity, topology reconciliation, scoped pane creation, duplicate-launch prevention, direct-mode compatibility, and release drift for `HIER-003`. Do not require or review the optional external-terminal adapter in this gate.

## Dependencies and lane

- Depends on `HIER-003`.
- Critical path. Acceptance unblocks `HIER-005` once its external prerequisites are also accepted.

## Writable scope

Review reports and evidence artifacts only. Do not implement new behavior or edit the canonical backlog from the gate session.

## Required tests and evidence

Run the focused acceptance/invariant matrix for managed tmux topology, package validation, release asset audit, documentation/skill drift checks, and required live tmux host journeys. Record exact commands and exit codes.

## Acceptance criteria

Issue an evidence-backed accept or reject decision against `HIER-003` and every core topology invariant. Unverified behavior, mutable projections, terminal prose, pane indexes, or pane liveness are not acceptance evidence.

## Stop conditions

Stop and reject the phase on missing sealed evidence, authority drift, duplicate-launch risk, positional tmux identity, shell execution, stale documentation, or unresolved release-audit findings.
