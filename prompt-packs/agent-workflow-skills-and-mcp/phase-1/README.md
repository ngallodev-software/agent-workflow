# Phase 1 — MCP server decision research

## Objective

Produce a primary-source decision memo covering MCP SDKs, server frameworks,
clients, transports, authentication, lifecycle, observability, and the safest
incremental path for this application. No product code changes are authorized.

## Complexity and delegation

| Ticket | Tier | Risk | Dependencies | Reviewer requirement |
|---|---|---|---|---|
| P1-00 | B | architecture | Phase 0 evidence | maintainer decision |

## Ordering

Follow `task-manifest.yaml`. Do not execute dependent tickets concurrently.

## Phase-wide constraints

Use primary sources only; distinguish evidence from recommendation; do not
modify runtime code, add dependencies, or create an MCP server in this phase.

## Required references

Read `references/README.md`, the P0 task breakdown, the durable-control
research memo, and the current source archive before drawing conclusions.

## Exit gate

Review direct official citations, the distinction between facts/inferences, the
threat model, and the bounded follow-on implementation proposal. No runtime
test can substitute for the decision review.
