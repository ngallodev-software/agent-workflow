# Benchmark Enhancements — Checkpoint 06 Validation

Date: 2026-08-02
Baseline: agent-workflow 0.7.9
Parent checkpoint: `5cc2a1b` (checkpoint 05)

## Scope

Checkpoint 06 expands acceptance validation beyond the benchmark-specific and invariant partitions. It verifies the benchmark enhancements and the checkpoint 05 completion-boundary correction against adjacent installed-product journeys involving CLI operation, durable cursors, delegation, evaluation, and hierarchy contracts.

No additional implementation defect was found in this partition. This checkpoint therefore adds validation and handoff evidence only.

## Acceptance evidence

### CLI product journeys

```text
9 passed in 23.84s
```

File:

```text
tests/acceptance/test_cli_product_journeys.py
```

### Comparative benchmark journey

```text
1 skipped in 0.03s
```

The journey requires Playwright/Chromium and an invoking tmux pane. This host does not provide the complete interactive environment, and the test now skips explicitly rather than failing misleadingly.

### Durable consumer cursor journey

```text
1 passed in 7.35s
```

### Delegation journeys

```text
17 passed
```

The file was executed in bounded groups because the environment limits individual command windows. All collected tests passed, including:

- interactive completion bridge and assignment closure;
- post-exit control-intent policy;
- durable message acknowledgement;
- restart and sealed-evidence behavior;
- interactive agent reuse and completion correlation;
- provider event normalization.

### Evaluation journeys

```text
1 passed in 28.05s
2 passed in 13.12s
```

Covered files:

```text
tests/acceptance/test_evaluation_journeys.py
tests/acceptance/test_evaluation_template_journey.py
```

### Hierarchy contract journey

```text
1 passed in 6.76s
```

## Aggregate checkpoint result

```text
31 passed, 1 skipped
```

The skip is environmental, not an assertion failure.

## Combined evidence through checkpoint 06

Previously recorded evidence remains valid:

- complete invariant suite: `283 passed`;
- benchmark/operator contract partition: `31 passed, 1 skipped`;
- documentation and release evidence: `24 passed`;
- installer release gate: `4 passed`;
- checkpoint 05 completion-race regressions: `2 passed`.

Checkpoint 06 adds broader installed-product acceptance confidence without changing runtime behavior.

## Remaining validation

The remaining acceptance files should continue in bounded partitions, followed by:

1. live adapter tests;
2. remaining release tests;
3. future tests as non-gating evidence;
4. a real tmux + provider + Playwright benchmark run on a capable host.

The real interactive run remains necessary to visually confirm same-window pane placement, provider output streaming, preserved review URLs, human scoring, and explicit teardown.
