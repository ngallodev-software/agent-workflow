# BENCH-CORR-004 — Expand browser and accessibility evaluation

**Backlog:** `BENCH-CORR-004`
**Priority:** P0 / High
**Dependencies:** BENCH-CORR-001 and BENCH-CORR-002
**Parallel lane:** visual evaluator lane
**Baseline:** `agent-workflow` 0.7.8

## Objective

Replace presence-only browser assertions with deterministic interaction, download-content, state, keyboard, responsive, and accessibility evidence required by the corrected contract.

## Writable functional scope

The corrected browser capture/evaluator, visual evidence schema, deterministic browser fixtures, runtime-lock integration, focused browser tests, and synchronized package assets. Do not change publication runtime trust semantics except where evidence schema must represent new checks.

## Required coverage

Automate app/item count, search, status/risk filters, sorting, combined controls, pointer/keyboard detail, selected-state communication, verified JSON download, empty and invalid states, persistent labels/accessibility names, landmarks/headings, logical focus order, actual visible focus indication, no keyboard trap, all frozen viewports, console errors, reduced motion, and an automated accessibility scan or justified equivalent.

## Tests and evidence

Use deliberately broken fixtures for every weighted browser check. Verify screenshots/DOM/state captures are deterministic and export content is parsed and asserted.

## Acceptance criteria

Browser check names accurately describe what is proven; no check awards behavior based only on element presence or text when the contract requires successful interaction.

## Stop conditions

Stop if the proposed checks require uncontrolled network access, leak treatment identity, or conflate runtime attestation with UI-quality points.

## 0.7.8 implementation ownership

- Corrected browser capture: `benchmarks/specs/priority-picker-v2/evaluation/capture_visual.py`.
- Corrected visual rubric/runtime files: the corrected suite's `visual-rubric.json`, runtime lock, and deterministic fixtures.
- Built-in visual/runtime integration: `src/agent_workflow/benchmarking/visual.py` and `runtime.py`.
- Visual evidence schema: a new version under `schemas/`; preserve v1 evidence.
- Installed mirror and Playwright acceptance: packaged benchmark assets plus focused comparative-benchmark tests.

All authority-bearing behavior remains in the built-in `agent_workflow.benchmarking` feature. Do not add a scorer/evaluator hook to the trusted plugin API or create a second registry. Pure contracts and evaluator-result interpretation should remain separable so a later, independently approved ARC-004 extraction can be evaluated without rewriting run authority.
