# Phase 0 — Prior art and contract freeze

## Objective

Produce a source-backed local-first messaging decision. No runtime edits.

## Complexity and delegation

| Ticket | Tier | Risk | Dependencies | Reviewer requirement |
|---|---|---|---|---|
| P0-00 | C | Low | none | Independent source/link check |

## Ordering

Follow `task-manifest.yaml`. Do not execute dependent tickets concurrently.

## Phase-wide constraints

Primary sources only; disk authority and replay must remain explicit.

## Required references

`docs/ORCHESTRATOR_MESSAGING_AND_EVALS_PLAN.md`, tmux and inotify primary docs.

## Exit gate

Verify links, contract matrix, threat model, and an explicit non-goal list.
