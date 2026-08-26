# DEC-008 — Initial comparative benchmark fixture and scoring

- **Status:** decided
- **Date:** 2026-08-01
- **Scope:** first `agent-workflow` paired comparative benchmark
- **Design/operating guide:** [`BENCHMARKS.md`](../BENCHMARKS.md); frozen suite assets remain machine authority

## Decision

The first comparative benchmark will execute the same canonical multiphase task in parallel through two isolated Git worktrees:

- `control_raw/v1`: the task without `agent-workflow`-specific behavioral, prompt-pack, skill, orchestration, review, or completion constraints;
- `workflow_full/v1`: the same task with a sealed inventory of the selected `agent-workflow` constraints.

A benchmark-neutral safety envelope applies equally to both arms. It provides isolation, resource bounds, evidence capture, oracle protection, and termination without becoming part of the product treatment.

The first fixture is the synthetic **visual priority picker**. It must combine deterministic machine-testable behavior with a responsive visual implementation that requires blinded human review.

The adopted initial composite is:

```text
composite_score = 0.70 * machine_score + 0.30 * human_visual_score
```

Machine and human scores remain separately visible. The composite cannot be final while required human review is incomplete, and guardrail-invalid trials cannot receive a valid composite.

## Rationale

The priority-picker fixture is bounded enough to reproduce but broad enough to expose differences in correctness, testing, scope control, maintainability, accessibility, responsiveness, and visual quality. A 70/30 split keeps deterministic and hidden machine evaluation dominant while preserving a material human judgment component for qualities that screenshot, DOM, and accessibility checks cannot fully establish.

The paired design measures the actual product question: whether the complete `agent-workflow` discipline improves outcomes enough to justify its token, dollar, and elapsed-time overhead compared with the same task executed without those product-specific constraints.

## Consequences

- The canonical task and requirement-to-evaluation matrix are frozen with the implemented `priority-picker-v1` suite.
- `BKL-010` owns the content-addressed browser image, verified font manifest, and trusted pre-seal visual-evidence bridge required for publication-grade human-review claims; development capture is implemented.
- `BKL-004` must compare explicit `control_raw` and `workflow_full` arms rather than generic cohorts and must preserve separate task, wrapper, and effective-prompt digests.
- Benchmark processing belongs in a modular `agent_workflow.benchmarking` boundary that can later become a first-party plugin after the interfaces have real use evidence.
- No task requirement, scoring allocation, visual rubric, or hidden oracle may be tuned after arm identities or results are observed.

## Operating policy

The previously open executor, authentication, billing, cache, repetition, retry, interruption, assistance, statistical, and publication-review choices are decided by [DEC-002](DEC-002-COMPARATIVE-BENCHMARK-OPERATING-POLICY.md). Subscription-backed CLI sessions are the default; API keys and access tokens are optional explicit cohort profiles.

## Implemented evidence

The frozen `priority-picker-v1` requirement-to-evaluation matrix now covers visible requirements, hidden tests, machine-score points, visual captures, human-rubric anchors, allowed paths, non-targets, phase prompts, guardrails, and evidence identities. The paired development journey verifies worktree isolation, concurrent phase starts, deterministic scoring, blinded review, composite calculation, consolidation, manifest verification, and cleanup.
