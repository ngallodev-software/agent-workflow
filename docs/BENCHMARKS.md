# Comparative Benchmarks

## Purpose

The comparative benchmark asks one product question: **does the full Agent-Workflow discipline improve implementation outcomes enough to justify its additional time, token, and cost overhead compared with the same task executed without Agent-Workflow-specific constraints?**

The benchmark is paired. Both arms receive the same canonical task, source revision, fixture, model/executor cohort, safety envelope, and evaluation contract. The treatment difference is the declared Agent-Workflow workflow discipline.

Machine-readable suite assets are authoritative. This document explains the current system but does not override a frozen benchmark specification, scoring contract, policy, evaluator, runtime lock, or sealed run artifact.

Canonical built-in assets live under:

```text
src/agent_workflow/assets/benchmarks/
```

They are packaged as shared immutable layers plus thin suite overlays. Consumers should materialize a self-contained suite through the CLI rather than reading the internal layer layout directly.

## Built-in suites

Current built-ins are:

| Benchmark | Schema | Purpose |
| --- | --- | --- |
| `priority-picker-v1` | `benchmark-spec/v1` | Frozen original Priority Picker benchmark. Historical score meaning remains immutable. |
| `priority-picker-v2` | `benchmark-spec/v2` | Corrected deterministic/scoring-contract benchmark with live review support. Preferred full benchmark for new development work. |
| `priority-picker-fast-v1` | `benchmark-spec/v2` | Bounded repair/verification variant designed for a model phase under 150 seconds and under roughly three minutes wall time. |

`priority-picker-v2` carries an explicit `benchmark-scoring-contract/v1`. Historical `priority-picker-v1` receipts remain immutable and mixed-version comparison is rejected rather than silently normalizing different score meanings.

Materialize a suite with:

```bash
agent-workflow benchmark suite-export /tmp/priority-picker-v2 \
  --benchmark-id priority-picker-v2
```

## Experimental arms

Every pair contains two isolated arms.

### `control_raw`

Receives the canonical task plus the benchmark-neutral safety envelope and allowed local tools/tests, but not Agent-Workflow-specific prompt-pack, skill, planning/completion, phase-gate, delegation, or drift-review constraints.

### `workflow_full`

Receives the same canonical task and safety envelope plus the declared Agent-Workflow treatment, including requirements traceability, bounded plan-before-edit discipline, writable-scope/non-target checks, acceptance-first verification, phase completion evidence, and self-review/drift auditing.

The task prompt digest and treatment/wrapper digest are recorded separately. A pair is invalid if the canonical task differs between arms or if undeclared treatment leaks into control.

## Priority Picker task

The full benchmark asks the model to implement a dependency-free Python/browser dashboard that reads `data/backlog.json`, validates backlog records, computes deterministic priority scores, ranks/filters/sorts them, exposes a small Python API, and presents a responsive accessible browser UI with JSON export.

The frozen score formula is:

```text
score = round((2*impact + 1.5*urgency + confidence + 0.5*risk) / max(effort, 1), 4)
```

Default ordering is score descending, urgency descending, impact descending, then ID ascending. The fixture includes deterministic validation, empty/invalid-state, scale, accessibility, responsiveness, and export requirements.

`priority-picker-v2` additionally requires unsupported sort keys/directions to fail with `BacklogValidationError`, caller-owned input structures not to be mutated, and decimal values in the allowed range to be handled deterministically.

The fast benchmark supplies an almost-complete application and asks the model to repair and verify it without changing the architecture or adding dependencies.

The complete task contract is the suite's `canonical-task.md`; this prose is only a summary.

## Execution phases

The full suites use three model phases:

1. **Analyze and plan** — inspect the task/repository and create `BENCHMARK_PLAN.md`.
2. **Implement** — make the bounded implementation changes.
3. **Verify and repair** — run required verification and correct remaining defects.

Each arm executes in its own Git worktree. The coordinator and pair metadata remain outside both arm worktrees so consolidation and comparison do not mutate the original checkout.

The pair scheduler starts both arms behind the same launch barrier and records start skew. Current suites require a maximum start skew of 0.25 seconds for eligibility.

## Eligibility and guardrails

A score is not enough to make a trial comparable. Current suites require guardrails covering:

- paired task/source identity;
- declared treatment identity;
- start skew;
- writable-scope isolation;
- assistance cohort;
- visual capture when required;
- provider usage/accounting evidence;
- benchmark harness integrity.

Infrastructure/evidence failure makes the pair invalid rather than a task failure. A model that simply produces a poor or incomplete implementation receives the corresponding score/fail result and remains valid evidence when the harness itself was sound.

The benchmark-neutral safety envelope applies equally to both arms and may enforce isolation, resource limits, evidence capture, oracle protection, and termination. It must not smuggle the Agent-Workflow treatment into control.

## Machine evaluation

The corrected v2 scoring contract totals 100 machine points:

| Dimension | Points |
| --- | ---: |
| Hidden functional behavior | 45 |
| Public regression tests | 15 |
| Robustness | 10 |
| Accessibility/deterministic UI | 10 |
| Scope and completeness | 10 |
| Engineering quality | 10 |

The v2 scoring contract enumerates each check, its evidence producer/reference, maximum points, and partial-credit rule. Checks are binary unless the contract explicitly says otherwise. Evaluators are explicit suite assets; arbitrary scorer code named by an untrusted benchmark file is not executed.

Efficiency is **not** converted into quality points. Time, tokens, retries, and cost are reported alongside quality and participate only through configured comparison/non-inferiority policy.

## Human visual evaluation

The Priority Picker fixture intentionally contains visual qualities that deterministic tests cannot fully judge. Visual capture records a pinned runtime identity, fixed viewports, screenshots/DOM/accessibility evidence, and the suite's visual rubric.

Required reviewer counts are policy-dependent:

- development: 1 reviewer;
- internal decision: 2 reviewers;
- publication: 3 reviewers or adjudication as required by policy.

Assignments are blinded to arm identity. An incomplete required review cannot produce a final composite or winner claim.

The adopted composite is:

```text
composite_score = 0.70 * machine_score + 0.30 * human_visual_score
```

Current suites require at least 70 machine and 60 human points for their configured passing thresholds. Machine, human, and composite scores remain separately visible.

## Operating-policy profiles and winner claims

[DEC-002](DECISIONS/DEC-002-COMPARATIVE-BENCHMARK-OPERATING-POLICY.md) defines three machine-readable operating profiles:

| Profile | Claim level | Paired repetitions | Winner claim |
| --- | --- | ---: | --- |
| `comparative-development/v1` | development | 1 | disabled |
| `comparative-internal/v1` | internal | 10 | enabled after 10 eligible pairs |
| `comparative-publication/v1` | publication | 20 | enabled after 20 eligible pairs |

Winner-enabled profiles use paired deltas and a deterministic 95% paired-bootstrap confidence interval. A winner additionally requires a configured minimum composite improvement (currently 5 points), no machine-score regression greater than 3 points, no human-score regression greater than 3 points, and no required comparability/guardrail failure.

If those conditions are not met, the correct result is no winner, descriptive only, or incomplete—not a forced product conclusion.

## Authentication and cohort identity

Production benchmark execution is subscription-only. Codex CLI and Claude Code CLI adapters verify an existing authenticated subscription session and must fail closed when ambient API credentials are present; API-key/access-token profiles are not supported in 0.9. The synthetic executor is development/test-only.

A cohort pins material execution identity, including provider, model, executor configuration/version, authentication mode, benchmark version, operating policy, and pricing catalog. Different identities are separate cohorts and must not be pooled as though they were interchangeable.

## Timing, usage, and cost semantics

The benchmark preserves phase and arm timing rather than collapsing every duration into one ambiguous number. Critical-path wall time and active execution time remain distinguishable where available.

Usage evidence keeps provider-reported token categories explicit, including cached/cache-write fields when the provider exposes them. Missing usage is not rewritten as zero.

Cost has three distinct meanings:

1. `provider_billed_cost` — directly attributable metered provider billing;
2. `local_estimated_cost` — API-equivalent/local estimate derived from sealed usage and a named price catalog;
3. `subscription_allocated_cost` — optional accounting allocation of a subscription fee.

Subscription runs normally have `provider_billed_cost = null`; they are not described as free. Actual rates live in the versioned executor price catalog/profile rather than a hand-maintained prose pricing table. Historical evidence seals the relevant catalog identity/digest.

## Retries, interruption, and assistance

Operating policy permits only infrastructure-class retries. A retry creates fresh paired worktrees and a new attempt/pair identity; all attempts remain in evidence. Task failure or low score does not qualify for an infrastructure retry.

An interrupted pair is retried from fresh paired worktrees rather than resumed as if temporal comparability were unchanged.

Assisted and unassisted runs are separate cohorts. Assistance state is sealed before execution and, when enabled, the same declared assistance channel must be available to both arms.

## Running a benchmark

Typical development flow:

```bash
agent-workflow benchmark suite-export /tmp/priority-picker-v2 \
  --benchmark-id priority-picker-v2
agent-workflow benchmark validate /tmp/priority-picker-v2/benchmark-spec.json
agent-workflow benchmark auth-check /tmp/priority-picker-v2/executors/codex-subscription.json
agent-workflow benchmark readiness /tmp/priority-picker-v2/benchmark-spec.json \
  --executor /tmp/priority-picker-v2/executors/codex-subscription.json \
  --policy /tmp/priority-picker-v2/policies/development.json
agent-workflow benchmark plan /tmp/priority-picker-v2/benchmark-spec.json \
  --repo /path/to/target --base-ref HEAD \
  --executor /tmp/priority-picker-v2/executors/codex-subscription.json \
  --policy /tmp/priority-picker-v2/policies/development.json
agent-workflow benchmark run RUN_PLAN.json
```

Operational commands also include `status`, `resume`, `live-start`, `live-stop`, `visual-capture`, `score`, `review`, `consolidate`, `report`, `verify`, and `cleanup`. Generate exact signatures from the installed parser with:

```bash
agent-workflow commands --format markdown
```

## Evidence, consolidation, and reproducibility

Arm-local evidence is staged independently. Consolidation copies results into the coordinator area and verifies content digests; it does not write benchmark results into the original source checkout.

A reproducible run records enough identity to determine what was compared: task/spec/scoring digests, source revision, arm wrappers, executor/model/authentication identity, policy, runtime lock, usage/cost evidence, scorer outputs, human reviews, and consolidation/verification receipts.

`benchmark verify` checks the consolidated evidence manifest/receipt. Worktrees may be removed only after required evidence has been consolidated and verified.

## Versioning rules

A frozen benchmark is not repaired in place after results are observed. Changes to task requirements, scoring allocation, hidden checks, visual rubric, evaluator behavior, or other result-affecting semantics require a new benchmark version/identity.

This rule is why `priority-picker-v1` remains available even though v2 corrects contract/determinism issues. Historical receipts keep their original meaning.

## Interpretation

The benchmark is designed to isolate the effect of the declared Agent-Workflow treatment, not to rank providers or models in general. It does not justify claims across different providers/models/authentication modes, benchmark versions, or materially different runtime policies unless those are run as separately designed cohorts.

Do not tune the fixture, hidden oracle, rubric, or score allocation after seeing arm identities/results for the same benchmark version.
