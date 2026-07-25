# Phase 0 — research, review, and executable plan

Refresh primary-source MCP evidence, independently review the approved decisions
against current source, and emit an implementation-ready plan and revised ticket
pack before production code changes.

## Complexity and delegation

| Ticket | Tier | Risk | Dependencies | Reviewer requirement |
|---|---|---|---|---|
| P0-00 | C | Read-only | none | coordinator verifies baseline |
| P0-01 | B | Read-only research | P0-00 | source links and version claims checked |
| P0-02 | A | Architecture judgment | P0-01 | independent reviewer signs decision delta |

## Ordering

Follow `task-manifest.yaml`. Do not execute dependent tickets concurrently.

No production writes. Research uses primary sources. Do not silently reopen
approved decisions; record any challenge as a decision delta with evidence.

Root README, `BACKLOG.md`, `docs/MCP_SERVER_DECISION.md`, MCP source/tests,
official SDK snapshot, and `references/`.

Evidence contains the exact source baseline, research matrix, threat review,
decision deltas, dependency graph, bounded tickets, and revised prompt pack.
`agent-workflow pack validate` passes and an independent review finds no
unbounded ticket or unsupported protocol claim.
