# Benchmark Enhancements — Checkpoint 04 Validation

Date: 2026-08-02
Baseline: agent-workflow 0.7.9
Parent implementation checkpoint: `8a4b2f8` (checkpoint 03)

## Scope validated

This checkpoint validates the implementation delivered through checkpoint 03 against the requested benchmark operator experience and the comparative scoring correction pack:

1. paired benchmark arms launch as exactly two additional panes in the invoking tmux window;
2. provider execution remains interactive and visible in those panes;
3. completed panes remain observable rather than disappearing immediately;
4. live applications are preserved after automated evaluation for human assessment and scoring;
5. explicit status, stop, and cleanup lifecycle operations exist for preserved review applications;
6. the corrected full benchmark is versioned separately from the historical benchmark;
7. a compact benchmark uses the same paired/scoring/review lifecycle with a 150-second model phase budget;
8. benchmark scoring contracts, schemas, docs, CLI boundaries, and release assets remain synchronized.

## Repository state

The repository was clean before this report was added. An uncommitted README edit found during validation was an accidental regression to the historical v1-only description and was discarded.

## Test evidence

### Benchmark contracts and operator lifecycle

Command group:

```text
python -m pytest -q \
  tests/invariants/test_benchmark_operator_experience.py \
  tests/invariants/test_cli_benchmark_handler_boundary.py \
  tests/invariants/test_comparative_benchmark_contracts.py \
  tests/invariants/test_comparative_benchmark_operating_policy.py \
  tests/acceptance/test_comparative_benchmark_journey.py
```

Result: **31 passed, 1 skipped** in 8.42 seconds.

The skipped acceptance test requires both Playwright/Chromium and an invoking tmux pane. Its skip condition now checks both prerequisites, so hosts lacking tmux do not report a false failure.

### Documentation and release evidence

Command group:

```text
python -m pytest -q \
  tests/invariants/test_cli_agent_handler_boundary.py \
  tests/invariants/test_release_evidence.py \
  tests/release/test_distribution.py \
  tests/release/test_documentation_sync.py
```

Result: **24 passed** in 17.58 seconds.

### Installer release gate

Command:

```text
python -m pytest -q tests/release/test_release_installers.py
```

Result: **4 passed** in 3.24 seconds.

### CLI product journeys

Command:

```text
python -m pytest -q tests/acceptance/test_cli_product_journeys.py
```

Result: **9 passed** in 24.24 seconds.

## Full-suite note

A single monolithic `pytest -q` invocation did not complete within the available seven-minute command budget. Verbose isolation showed no benchmark regression: the next test at the cutoff passed independently in 17.85 seconds. The suite is therefore being validated in deterministic partitions rather than declaring the monolithic timeout a pass or a failure.

## Current implementation assessment

The requested operator-facing behavior is implemented and covered by focused invariants. The scoring correction pack has been improved and incorporated into the repository-owned prompt pack, including a new phase for pane observability, live-review lifecycle, and the fast suite.

The remaining highest-value validation is a real terminal acceptance run on a host with:

- an active tmux client;
- Codex or Claude subscription authentication;
- Playwright and Chromium;
- enough pane capacity to add exactly two panes;
- permission to bind two local review ports.

That run should confirm visual pane placement, live streaming from real providers, preserved review URLs, human scoring submission, and explicit teardown end to end.
