# Phase 1 — Durable local messaging

## Objective

Deliver validated append/replay, progress, steer, ack, and blocking wait.

## Complexity and delegation

| Ticket | Tier | Risk | Dependencies | Reviewer requirement |
|---|---|---|---|---|
| P1-00 | C | Medium | P0-00 | Independent behavior tests |

## Ordering

Follow `task-manifest.yaml`. Do not execute dependent tickets concurrently.

## Phase-wide constraints

No daemon, broker, database, or fake stdin/keystroke delivery.

## Required references

`events.py`, `sessions.py`, `runner.py`, `state.py`, and Phase 0 decision.

## Exit gate

Run focused message/session/CLI tests and inspect a replayed pending steer.
