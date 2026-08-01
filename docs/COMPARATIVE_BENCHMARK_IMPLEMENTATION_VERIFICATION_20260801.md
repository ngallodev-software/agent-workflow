# Comparative benchmark implementation verification — 2026-08-01

> Historical 0.7.5 verification record. DEC-002 and the locally implementable BKL-004/BKL-010 mechanics were subsequently completed in 0.7.6; see [`COMPARATIVE_BENCHMARK_OPERATING_POLICY_VERIFICATION_20260801.md`](COMPARATIVE_BENCHMARK_OPERATING_POLICY_VERIFICATION_20260801.md) for the current state.

## Scope

This verification covers the implemented `priority-picker-v1` development benchmark and the modular `agent_workflow.benchmarking` runtime introduced under DEC-008. It verifies the paired worktree lifecycle, synchronized phase execution, evidence contracts, deterministic machine scoring, visual capture, blinded human-review workflow, composite reporting, consolidation, installed-wheel packaging, resumability, and cleanup behavior.

## Acceptance results

The focused benchmark contract and end-to-end journey pass:

```text
pytest -q \
  tests/invariants/test_comparative_benchmark_contracts.py \
  tests/acceptance/test_comparative_benchmark_journey.py

6 passed
```

The acceptance journey proves:

- a coordinator and two arm worktrees are created from the exact frozen fixture revision;
- `control_raw/v1` and `workflow_full/v1` receive the same task content but distinct, retained treatment wrappers;
- each phase is released through a shared barrier and records bounded start skew;
- phase, arm, pair, and pipeline timings are retained without conflating wall and summed process time;
- provider tokens, cache fields, provider-billed cost, local-estimated cost, retries, latency, and missing values are preserved correctly;
- the synthetic reference arms score 88 and 96 machine points, respectively;
- browser evidence is captured at the frozen desktop, tablet, and mobile viewports;
- blinded assignments expose only neutral `left` and `right` evidence paths;
- the report remains `awaiting_human_review` before the configured review threshold is met;
- submitted review evidence produces the adopted 70% machine / 30% human composite;
- consolidation and manifests verify before cleanup;
- cleanup removes arm worktrees and branches while preserving the coordinator and consolidated run;
- resuming a complete automated run is idempotent and does not append duplicate phase events;
- the source checkout remains unchanged by benchmark execution.

## Broader repository checks

The release-asset audit passes:

```text
python scripts/audit-release-assets.py
release assets: valid
```

The available invariant, release, and future-contract selection passes:

```text
pytest -q tests/invariants tests/release tests/future \
  -k 'not documented_commands_match_the_installed_public_surface'

137 passed, 1 deselected, 12 xfailed
```

The 12 expected failures are existing approved future contracts. They remain intentionally unimplemented and are unrelated to this benchmark delivery.

The unrestricted test command cannot collect in the current validation environment because the repository-pinned runtime dependency `mcp==1.28.1` is unavailable there. The failure occurs before test execution in `tests/acceptance/test_mcp_product_journeys.py`; benchmark-specific and dependency-independent repository tests pass as recorded above.

## Installed-wheel verification

A clean wheel was built with no dependency resolution and installed into an isolated validation environment. The wheel contains:

- all `agent_workflow.benchmarking` modules;
- the packaged `priority-picker-v1` suite, fixture, profiles, phase prompts, evaluators, rubric, and synthetic executor;
- all comparative benchmark JSON Schemas;
- the `benchmark-visual` optional dependency declaration.

The installed CLI successfully completed:

```text
benchmark suite-export
benchmark validate
benchmark fixture-create
benchmark plan
benchmark run
benchmark verify
```

The installed run produced a valid consolidated report in `awaiting_human_review`, with machine scores of 88 for `control_raw` and 96 for `workflow_full`. Provider-billed and local-estimated costs were both retained independently.

## Remaining gates

This implementation is complete for development evidence. The following are deliberately not represented as complete:

- **DEC-002:** paid executor/model selection, cache and billing publication semantics, final repetition counts, statistical/effect thresholds, retry treatment, interrupted trials, and assisted cohorts;
- **BKL-004:** controlled real-provider comparative cohorts after the required security, privacy, and release gates are accepted;
- **BKL-010:** content-addressed browser image, verified font manifest, and trusted browser-evidence bridge for publication-grade visual claims.

These gates do not block local synthetic execution, machine scoring, blinded development review, evidence consolidation, or installed-product use of the suite.
