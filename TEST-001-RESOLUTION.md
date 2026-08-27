# TEST-001 Resolution

`TEST-001` is closed before Phase 7 implementation.

## Finding

The original diagnosis was incomplete. Fixture teardown itself is fast and already reaps fixture-owned detached process groups, but the monolithic acceptance layer had grown to **120.77 seconds inside pytest** (about **124 seconds end-to-end** in the execution harness). A 120-second outer command timeout therefore could not reliably receive the final pytest result even when teardown behaved correctly.

The failure was test-layer execution cost, not a missing second teardown authority.

## Resolution

The acceptance layer was consolidated without removing unique authority coverage:

- the SQLite index journey no longer repeats status/full-verify/incident-query/rebuild operations already proven by stronger assertions or deterministic invariants;
- the evaluation journey keeps the unique installed-product evaluated-run, automatic score/report evidence, collection, and comparison path while removing duplicate review/acceptance, sealed-run assessment, benchmark-report, archive-plan, and explicit rescoring checks covered elsewhere;
- workflow journeys remove redundant validate/status invocations when start/seal or durable event evidence already proves the same boundary;
- the three-template installed-product matrix is reduced to one representative executable-template journey because individual template-shape authority is deterministic and does not require three separate process-heavy acceptance cases.

This reduces the acceptance case count from 19 to 17 while preserving the intended broad journey layer. Test-count reduction is incidental; the objective is authority coverage per unit of runtime cost.

## Targeted verification

Executed the complete acceptance layer monolithically:

```text
python -m pytest -q tests/acceptance --durations=25
```

Result:

- **17 passed**;
- **1 expected skip** because the optional MCP SDK feature is not installed;
- **exit code 0**;
- **90.81 seconds inside pytest**;
- **94.16 seconds end-to-end** from process launch through final result recording;
- slow-test teardown remained approximately **0.05 seconds**.

This leaves roughly 25 seconds of margin beneath the 120-second execution-layer timeout instead of racing it.
