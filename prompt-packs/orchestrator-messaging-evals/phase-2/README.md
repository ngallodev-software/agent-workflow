# Phase 2 — Metrics and deterministic eval

## Objective

Seal normalized metrics and establish a deterministic regression cohort.

## Complexity and delegation

| Ticket | Tier | Risk | Dependencies | Reviewer requirement |
|---|---|---|---|---|
| P2-00 | C | Medium | P1-00 | Independent scorer/report run |

## Ordering

Follow `task-manifest.yaml`. Do not execute dependent tickets concurrently.

## Phase-wide constraints

Raw provider events stay authoritative; missing usage is nullable, not zero.

## Required references

`executors.py`, `runner.py`, `receipts.py`, `eval/`, and Phase 1 artifacts.

## Exit gate

Run fixture baseline/fix/mutation checks and repeat `eval score` on one seal.
