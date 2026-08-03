# Benchmark enhancements checkpoint 08 validation

## Scope

Checkpoint 08 closes documentation and execution-state drift in the canonical comparative-benchmark correction backlog. The implementation already present in checkpoints 04 through 07 is unchanged.

## Corrections

- Rebased the implementation map from 0.7.8 to 0.7.9.
- Marked BENCH-CORR-001 through BENCH-CORR-010 as implemented rather than ready or blocked.
- Added explicit BENCH-OPS-001 through BENCH-OPS-003 status for same-window panes, interactive provider output, and preserved live applications.
- Added BENCH-FAST-001 status for the compact one-phase suite and its synthetic paired timing calibration.
- Split the independent gate into completed deterministic/source/package validation and still-open real-host/publication validation.
- Linked the backlog to the checkpoint evidence and executable benchmark contract suites.

## Validation

Commands executed from the repository root:

```text
python -m pytest -q \
  tests/invariants/test_comparative_benchmark_contracts.py \
  tests/invariants/test_comparative_benchmark_operating_policy.py \
  tests/invariants/test_cli_benchmark_handler_boundary.py
```

Result: `23 passed in 0.63s`.

```text
python -m pytest -q \
  tests/release/test_documentation_sync.py \
  tests/release/test_distribution.py
```

Result: `10 passed in 13.69s`.

## Remaining external gates

This checkpoint does not claim evidence that cannot be produced on the current host. The following remain open:

1. authenticated Codex and Claude subscription execution;
2. exact two-pane placement in the invoking tmux window;
3. visible interactive provider output through completion;
4. Playwright/Chromium capture against both preserved live applications;
5. blinded multi-reviewer scoring and adjudication;
6. publication acceptance using a content-addressed browser runtime and verified font manifest.

The source is suitable for deterministic development and internal validation. Publication claims remain blocked until those gates are independently completed.
