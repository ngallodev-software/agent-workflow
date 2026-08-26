# Phase {{PHASE_NUMBER}} Master Implementation Prompt

## Role

Act as the phase coordinator. Execute or delegate only the tickets listed by the phase entry in root `pack.yaml`.

## Objective

## Source-of-truth hierarchy

Use current source first, then current tests/schemas, then verified references, then documentation and historical plans.

## Execution rules

1. Create one clean worktree per writable ticket.
2. Prepare every delegation as a new durable Agent Run, then start an AW-owned headless worker when appropriate.
3. Record source baseline and prompt hash.
4. Enforce dependencies and writable paths.
5. Inspect durable Agent Run status, progress, logs, and evidence before interruption.
6. Do not merge implementation and independent phase review into the same unchecked delegation.
7. Use AW-owned headless workers for unattended execution. Use external Agent Runs only when an interactive host intentionally provides the worker; host presentation is outside core workflow authority.

## Test policy

Add only tests required by explicit acceptance criteria or a demonstrated regression boundary. Prefer one semantic assertion over broad snapshots or repeated CLI help coverage.

## Completion

Require ticket completion reports, independently rerun phase gates, and produce `PHASE_GATE_REPORT.md`.
