# Phase 3 — Pinned visual handoff eval

## Objective

Exercise explicit parent/child telemetry through a small browser UI task.

## Complexity and delegation

| Ticket | Tier | Risk | Dependencies | Reviewer requirement |
|---|---|---|---|---|
| P3-00 | B with A gate | High | P2-00 | Independent browser/receipt gate |

## Ordering

Follow `task-manifest.yaml`. Do not execute dependent tickets concurrently.

## Phase-wide constraints

Pin browser/image/fonts and never use transcript prose as protocol proof.

## Required references

`inspect_adapter.py`, `docs/adr/0001-inspect-evaluation-topology.md`, Phase 2.

## Exit gate

Run functional, accessibility, screenshot, negative protocol, and seal checks.
