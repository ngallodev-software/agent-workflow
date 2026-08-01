# Comparative benchmark implementation

The adopted `priority-picker-v1` paired benchmark is implemented behind the modular `agent_workflow.benchmarking` package. It runs the same canonical three-phase task through `control_raw/v1` and `workflow_full/v1`, one pair at a time, with the two arms in each phase released concurrently behind a barrier.

## What is implemented

- coordinator plus isolated arm Git worktrees from one frozen fixture revision;
- separate canonical-task, arm-wrapper, constraint-profile, and effective-prompt digests;
- phase-local execution evidence, stdout/stderr, process identity, token usage, cache fields, cost, latency, and timing;
- pair wall time, summed arm wall time, critical-path time, and measured start skew;
- deterministic 100-point machine scoring with eligibility-invalidating guardrails;
- Playwright/Chromium visual capture at desktop, tablet, and mobile viewports;
- blinded reviewer assignments copied into neutral `left` and `right` namespaces;
- 70% machine / 30% human composite after the required reviews exist;
- digest-verified consolidation under `benchmarks/runs/<run-id>`;
- post-consolidation verification and safe deletion of arm worktrees;
- packaged benchmark-suite export for installed-wheel use;
- subscription-session authentication preflight for Codex and Claude CLIs, with optional explicit API-key/access-token adapters and no silent fallback;
- versioned development, internal, and publication operating policies;
- one infrastructure-only fresh-pair retry with every attempt retained;
- deterministic paired-bootstrap confidence intervals and policy-gated winner declarations;
- development runtime attestation plus publication runtime sealing from a content-addressed browser image.

The first suite is frozen at [`../benchmarks/specs/priority-picker-v1`](../benchmarks/specs/priority-picker-v1/). Its requirement-to-evaluation matrix is [`REQUIREMENT_EVALUATION_MATRIX.md`](../benchmarks/specs/priority-picker-v1/REQUIREMENT_EVALUATION_MATRIX.md).
The initial implementation validation record is [`COMPARATIVE_BENCHMARK_IMPLEMENTATION_VERIFICATION_20260801.md`](COMPARATIVE_BENCHMARK_IMPLEMENTATION_VERIFICATION_20260801.md). The completed operating-policy, subscription-authentication, statistics, retry, and publication-runtime verification is [`COMPARATIVE_BENCHMARK_OPERATING_POLICY_VERIFICATION_20260801.md`](COMPARATIVE_BENCHMARK_OPERATING_POLICY_VERIFICATION_20260801.md).

## Development quick start

Install the visual extra and the pinned Chromium runtime used by the suite:

```bash
python -m pip install -e '.[benchmark-visual]'
playwright install chromium
```

Export the packaged suite, create its starter repository, plan the paired run, and execute the automated stages:

```bash
agent-workflow benchmark suite-export /tmp/priority-picker-v1
agent-workflow benchmark fixture-create \
  /tmp/priority-picker-v1/benchmark-spec.json \
  /tmp/priority-picker-fixture

agent-workflow benchmark plan \
  /tmp/priority-picker-v1/benchmark-spec.json \
  --executor /tmp/priority-picker-v1/executors/synthetic.json \
  --repo /tmp/priority-picker-fixture \
  --run-id priority-picker-smoke

agent-workflow benchmark run priority-picker-smoke
agent-workflow benchmark status priority-picker-smoke
```

`run` performs execution, visual capture, machine scoring, consolidation, and report generation. It normally stops in `awaiting_human_review`.

Create a blinded assignment, complete the generated template, and submit it. Each blocking defect must identify the blinded side, for example `{"label":"left","description":"Primary action is clipped at mobile width"}`; use `both` only when the same defect applies to both submissions.

```bash
agent-workflow benchmark review priority-picker-smoke --reviewer reviewer-01
agent-workflow benchmark review priority-picker-smoke \
  --reviewer reviewer-01 \
  --input /path/to/completed-review.json

agent-workflow benchmark report priority-picker-smoke
agent-workflow benchmark verify priority-picker-smoke
agent-workflow benchmark cleanup priority-picker-smoke
```

`cleanup` refuses to remove arm worktrees unless consolidated evidence verifies. The coordinator worktree and `benchmarks/runs/<run-id>` remain intact.


## Authentication and operating profiles

Real runs default to an existing provider CLI subscription session. `benchmark auth-check` verifies the selected session before any worktree is created and stores only bounded status evidence and output digests. Subscription profiles reject ambient API-key/access-token variables so a run cannot silently switch to metered API billing. Optional API profiles are separate executor configurations and therefore separate cohorts.

The suite includes `development`, `internal`, and `publication` policies. They seal repetitions, retry semantics, cache treatment, assistance cohort, allowed authentication modes, confidence level, effect threshold, regression limits, and reviewer requirements. Use `benchmark readiness` to evaluate the selected executor, policy, authentication state, and visual runtime before planning. See [DEC-002](DECISIONS/DEC-002-COMPARATIVE-BENCHMARK-OPERATING-POLICY.md) and the [operations guide](COMPARATIVE_BENCHMARK_OPERATIONS.md).

## Executor adapter contract

A real executor is supplied through `agent-workflow/benchmark-executor-config/v1`. Its argv template may use:

```text
{run_id} {benchmark_id} {pair_id} {case_id} {repetition}
{pair_nonce} {arm} {slot} {phase_id} {worktree} {stage_dir}
{phase_dir} {prompt_file} {usage_file} {suite} {run_dir}
```

The process runs with the arm worktree as its current directory. The same values are also exposed through bounded `AGENT_WORKFLOW_BENCHMARK_*` environment variables. The executor must consume `{prompt_file}`, perform only the current phase, and leave task changes in `{worktree}`.

For complete efficiency evidence, write JSON to `{usage_file}` containing these fields:

```json
{
  "input_tokens": 1000,
  "cached_input_tokens": 0,
  "cache_write_input_tokens": 0,
  "output_tokens": 250,
  "reasoning_output_tokens": 100,
  "provider_total_tokens": 1350,
  "retry_count": 0,
  "provider_billed_cost": 0.0123,
  "local_estimated_cost": 0.0123,
  "provider_elapsed_seconds": 12.4,
  "first_output_latency_seconds": 1.2,
  "currency": "USD",
  "price_catalog_id": "provider-model-prices-YYYYMMDD"
}
```

Unknown values remain `null`; they are never converted to zero. A required `provider_usage` guardrail invalidates the score when the configured benchmark requires complete usage and the adapter does not supply every frozen field.

## Timing semantics

The report preserves distinct timing categories instead of labeling one ambiguous duration as “total”:

- each phase: wall, active process, provider elapsed, first-output latency, queue wait;
- each arm: summed phase wall, active process, visual capture, machine verification, and measured non-human total;
- each pair: concurrent pair wall, sum of arm walls, critical path, and start skew;
- each run: execution, visual, machine-scoring, consolidation, reporting, and automated-pipeline wall time;
- human review: reviewer-reported active review time.

Tokens and provider/local costs remain separate from quality scores. Efficiency is reported descriptively and does not add machine-quality points.

## Guardrails and claim levels

Required guardrails cover paired identity, declared treatment, start skew, writable scope, unassisted execution, visual capture, provider usage, and harness integrity. A failed required guardrail produces an invalid trial rather than a reduced score.

The included synthetic executor and host-detected browser capture support **development** evidence only. Internal and publication profiles reject synthetic authentication. Publication readiness requires a runtime lock sealed from inside a content-addressed browser image with verified browser and font digests.

`DEC-002` is decided and encoded in machine-readable profiles. Each pair may receive one infrastructure-only retry in fresh worktrees; all attempts remain evidence. Interrupted pairs are discarded and retried fresh. Assisted and unassisted runs are distinct cohorts. Winner-enabled profiles require the configured eligible-pair count, a deterministic 95% paired-bootstrap interval, at least a five-point composite improvement, and no machine or human regression beyond three points.

`BKL-004` and `BKL-010` now retain external acceptance evidence rather than missing implementation: the first real subscription-backed cohort must be run after its security/privacy/release prerequisites, and the publication browser image must be built, published, and independently digest-verified by the operator.

## Modular boundary

All orchestration and processing code lives under `src/agent_workflow/benchmarking/`. It depends on narrow existing ports for contracts, subprocesses, Git worktrees, atomic files, and hashes. The suite itself is data-driven and packaged under `agent_workflow/assets/benchmarks/`, allowing the module to be split behind the first-party plugin boundary later without changing its versioned evidence contracts.
