# Agent-Workflow Comparative Benchmark Prompt Pack Specification


## 0.7.8 interpretation note

The executable `priority-picker-v1` suite is a built-in feature owned by `src/agent_workflow/benchmarking/`, with source assets under `benchmarks/specs/priority-picker-v1/` and an installed/exported mirror under `src/agent_workflow/assets/benchmarks/priority-picker-v1/`. The current evaluator code defines historical v1 score meaning. The frozen matrix and implementation contain known requirement-level weighting, coverage, and version-label discrepancies; see [Comparative benchmark: task, evaluations, scoring, and interpretation](COMPARATIVE_BENCHMARK_EXPLAINED.md). Corrective work is owned by [the benchmark correction backlog](COMPARATIVE_BENCHMARK_CORRECTION_BACKLOG.md) and its prompt pack. It must create a new major benchmark version rather than changing v1 semantics in place.

Under DEC-009, benchmarking remains a built-in feature. The trusted plugin API does not expose scorer/evaluator hooks, and the correction program must not create an ad hoc plugin mechanism or perform feature extraction.

**Version:** 1.0 implemented development baseline
**Target source:** `agent-workflow` 0.7.8
**Status:** paired runner, frozen priority-picker fixture, deterministic scoring, blinded visual review, consolidation, reporting, and cleanup implemented; publication operating policy and hardened browser isolation remain gated
**Primary objective:** measure whether the full `agent-workflow` execution discipline improves task quality, reliability, and auditability enough to justify its token, dollar, and elapsed-time overhead.

## 1. Executive design decisions

The paired-arm experiment, first fixture, and composite weighting are authoritative under [DEC-008](DECISIONS/DEC-008-INITIAL-COMPARATIVE-BENCHMARK.md). Authentication, billing, cache, repetition, retry, assistance, statistics, and publication operating policy are authoritative under [DEC-002](DECISIONS/DEC-002-COMPARATIVE-BENCHMARK-OPERATING-POLICY.md).

The benchmark is a paired experiment. Every benchmark case is executed in parallel in two isolated Git worktrees created from the same base revision:

- **`control_raw` arm:** the canonical task and phase prompts, with no `agent-workflow` execution protocol, prompt-pack behavioral wrapper, workflow skills, delegation rules, completion template, review protocol, or other product-specific constraints.
- **`workflow_full` arm:** the same canonical task and phase prompts, executed with the complete selected `agent-workflow` constraint profile.

A small **benchmark safety envelope** applies identically to both arms. It is not part of the treatment. It enforces process isolation, synthetic inputs, worktree boundaries, resource limits, evidence capture, hidden-oracle protection, and termination. “Unconstrained” therefore means “without `agent-workflow` behavioral and orchestration constraints,” not “allowed to escape the host, read sibling worktrees, access secrets, or bypass benchmark safety.”

Each paired repetition starts behind a launch barrier. The pair is comparable only when both arms have the same task digest, fixture digest, base revision, model, executor version, effort setting, tool availability, environment, resource policy, and pair nonce. The effective prompts may differ because the constraint wrapper is the experimental variable.

All task execution and generated artifacts occur in benchmark-created worktrees. The main checkout remains read-only. Final evidence is consolidated into the coordinator worktree under:

```text
benchmarks/runs/<run-id>/
```

The design extends the existing sealed-run, evaluation-plan, trial-evidence, benchmark-report, worktree, usage, cost, and ledger foundations. It must not create a second incompatible evaluation system.

## 2. Questions this benchmark answers

The initial benchmark should answer five separate questions rather than collapse everything into one score:

1. **Correctness:** Does `workflow_full` complete the required behavior more reliably?
2. **Engineering quality:** Does it produce safer, more maintainable, better-tested changes with less scope drift?
3. **Visual quality:** Does it produce a more usable and polished visual result according to blinded human review?
4. **Efficiency:** What additional or reduced tokens, provider cost, wall time, verification time, retries, and human-review time does it require?
5. **Evidence quality:** Does it leave materially better provenance, requirement coverage, test evidence, and reviewability?

The benchmark must report tradeoffs. A single “winner” is optional and may only be declared when all required evidence and sample thresholds are satisfied.

## 3. Implemented relationship to `agent-workflow`

The benchmark is implemented as the modular `agent_workflow.benchmarking` boundary and reuses existing Git worktrees, contract validation, subprocess controls, atomic writes, and digest utilities. It adds the explicit paired-arm semantics that the generic baseline/candidate evaluation templates did not provide.

Implemented capabilities include:

1. explicit `control_raw` and `workflow_full` treatment profiles;
2. paired identity based on the canonical task, fixture, source revision, executor, environment, tool policy, resource policy, and pair nonce rather than the intentionally different effective prompts;
3. a phase barrier that releases both arms concurrently and records start skew;
4. phase, arm, pair, and run timing plus normalized token, cache, cost, retry, and latency evidence;
5. the frozen 100-point deterministic machine evaluation and eligibility-invalidating guardrails;
6. desktop, tablet, and mobile visual capture plus neutral left/right blinded-review bundles;
7. the adopted 70/30 composite after the claim-level reviewer threshold is met;
8. digest-verified consolidation into the coordinator at `benchmarks/runs/<run-id>`;
9. verification and cleanup that can remove arm worktrees while preserving the complete consolidated run;
10. packaged suite export for installed-product use.

The authoritative implementation guide is [COMPARATIVE_BENCHMARK_IMPLEMENTATION.md](COMPARATIVE_BENCHMARK_IMPLEMENTATION.md). `BKL-004` owns execution and acceptance of controlled real-provider cohorts after prerequisite gates. `BKL-010` owns operator production and independent verification of the content-addressed publication browser image. The supporting adapters, policy profiles, statistics, and runtime seal/attest gates are implemented.

## 4. Experimental arms and constraint profiles

### 4.1 Canonical task content

Every case contains content that is identical across arms:

- task objective and requirements;
- phase objectives;
- fixture inputs;
- acceptance criteria visible to the agent;
- public tests and allowed tools;
- required final deliverables.

These inputs receive stable digests:

```text
task_prompt_sha256
phase_prompt_sha256[]
fixture_sha256
public_tests_sha256
input_bundle_sha256
```

### 4.2 Arm wrappers

The arm wrapper is separate from the canonical task:

```text
control_raw:
  task + minimal benchmark-neutral execution envelope

workflow_full:
  task + benchmark-neutral envelope + selected agent-workflow constraint profile
```

Both effective prompts are retained, but they are **not** part of the paired identity key.

Required arm identity fields:

```json
{
  "arm": "control_raw | workflow_full",
  "task_prompt_sha256": "...",
  "arm_wrapper_sha256": "...",
  "effective_prompt_sha256": "...",
  "constraint_profile_id": "control-raw/v1 | workflow-full/v1",
  "constraint_profile_sha256": "...",
  "enabled_features": [],
  "disabled_features": []
}
```

### 4.3 `control_raw/v1`

Disabled treatment features include:

- prompt-pack execution protocol;
- `AGENTS.md` or repository-owned agent instructions, unless they are inseparable from the fixture and explicitly declared;
- agent-workflow skills;
- required worktree preflight instructions presented to the agent;
- task completion templates and result contracts beyond the neutral output handoff;
- delegation rules, phase-gate review, steering protocol, backlog ownership checks, release-drift audit, and agent-workflow-specific test philosophy;
- workflow-generated plan, checklist, or review prompts.

The control arm still runs in a worktree with a sanitized environment and host-enforced limits.

### 4.4 `workflow_full/v1`

The treatment profile must inventory, version, and hash every enabled mechanism, including:

- prompt-pack execution protocol and phase manifests;
- relevant `AGENTS.md` instructions;
- selected skills and their exact digests;
- worktree preflight and source-baseline requirements;
- writable-scope and non-target rules;
- completion/result contracts;
- testing and evidence requirements;
- delegation, review, drift, and phase-gate procedures;
- host lifecycle and receipt behavior;
- any automated steering, retry, or supervisor policy enabled for the run.

“Full” is meaningful only when this inventory is sealed. Undeclared local instructions invalidate the arm.

### 4.5 Future ablation profiles

The initial benchmark compares only the two required arms. The schema should permit later ablations without changing the core contracts:

- `workflow_prompt_only`
- `workflow_no_review_gate`
- `workflow_no_skills`
- `workflow_no_preflight`
- `workflow_single_agent`

These are future experiments, not initial scope.

## 5. Worktree and run topology

### 5.1 Coordinator worktree

A benchmark run first creates a dedicated coordinator worktree and branch from the selected source revision:

```text
<worktree-root>/benchmarks/<run-id>/coordinator/
branch: benchmark/<run-id>/coordinator
```

The coordinator owns:

- immutable run plan;
- launch barrier and pair scheduling;
- benchmark event journal;
- arm inventory and state projections;
- copied and verified evidence;
- machine score output;
- human-review forms;
- final reports under `benchmarks/runs/<run-id>`.

The original checkout is never a write target.

### 5.2 Arm worktrees

Each case/repetition receives two sibling worktrees from the same exact base commit:

```text
<worktree-root>/benchmarks/<run-id>/<case-id>/r<nn>/control_raw/
<worktree-root>/benchmarks/<run-id>/<case-id>/r<nn>/workflow_full/
```

Recommended branches:

```text
benchmark/<run-id>/<case-id>/r<nn>/control
benchmark/<run-id>/<case-id>/r<nn>/workflow
```

No worktree path, branch, environment variable, prompt, or tool configuration may expose its sibling arm.

### 5.3 Arm-local evidence staging

Before consolidation, each arm writes benchmark-owned output only under:

```text
<arm-worktree>/.agent-workflow-benchmark/<run-id>/<case-id>/r<nn>/<arm>/
```

Task-generated source changes remain in the normal worktree paths and are captured by Git revision, patch, inventory, and selected artifact export.

### 5.4 Consolidated layout

```text
benchmarks/
├── specs/
│   └── priority-picker-v1/
│       ├── benchmark-spec.json
│       ├── canonical-task.md
│       ├── phases/
│       ├── evaluation/
│       ├── visual-rubric.json
│       └── fixture.lock.json
└── runs/
    └── <run-id>/
        ├── run.json
        ├── run-plan.json
        ├── experiment-manifest.json
        ├── events.jsonl
        ├── environment.json
        ├── pairs/
        │   └── <case-id>/r<nn>/
        │       ├── pair.json
        │       ├── control_raw/
        │       │   ├── arm.json
        │       │   ├── phases.json
        │       │   ├── metrics.json
        │       │   ├── score.json
        │       │   ├── patch.diff
        │       │   ├── artifact-inventory.json
        │       │   └── visual/
        │       └── workflow_full/
        ├── machine-scores.json
        ├── human-review/
        │   ├── review-assignment.json
        │   ├── reviews/
        │   └── adjudication.json
        ├── comparison.json
        ├── report.json
        ├── report.md
        ├── consolidation-receipt.json
        └── MANIFEST.sha256
```

Large raw provider streams and logs may be stored as compressed artifacts referenced by digest, but the run directory must remain self-describing and must never silently omit them.

## 6. Multi-phase benchmark lifecycle

### Phase 0 — Validate and freeze

- validate the benchmark spec and prompt pack;
- resolve source revision and fixture revision;
- record executor/model/version/effort/tool policy;
- build environment and visual-runtime lock files;
- generate pair nonces and randomized slot assignments;
- create coordinator and arm worktrees;
- verify clean, identical baselines;
- run public-test baseline and prove the starter fixture does not already pass;
- seal the run plan before any agent starts.

### Phase 1 — Analyze and plan

Both arms receive the same analysis/plan task. The control arm receives no workflow-specific planning format. The workflow arm follows its declared profile. Planning output is retained and scored only for requirement coverage and contradiction detection; style is not scored.

### Phase 2 — Implement

Both arms implement the same functional and visual requirements. Each arm is independently writable only inside its own worktree and allowed scope.

### Phase 3 — Verify and repair

- agents may run public tests and local checks allowed by the task;
- benchmark host runs the same deterministic post-commands in both arms;
- retries caused by task defects are part of the arm result;
- infrastructure failures invalidate the pair and trigger a pair-level retry according to policy;
- no hidden oracle is exposed before terminal agent exit.

### Phase 4 — Capture visual evidence

After the agent exits:

- build and launch the artifact in a pinned browser/container image;
- use a pinned browser version, font manifest, viewport set, device scale, locale, timezone, color scheme, reduced-motion setting, and fixture data;
- execute deterministic interaction scripts;
- capture screenshots, DOM snapshots, console output, accessibility output, and layout checks;
- seal the visual evidence before human review.

### Phase 5 — Machine scoring

Run deterministic scorers against sealed evidence and hidden oracles. Produce eligibility, machine quality, requirement coverage, and efficiency results. Machine scoring must make no model calls in the initial version.

### Phase 6 — Blinded human visual review

- randomize arm display labels and left/right order per reviewer;
- hide arm identity, token/cost/time results, and source code until the visual score is submitted;
- collect absolute rubric scores, pairwise preference, confidence, blocking defects, and review duration;
- preserve individual reviews; never overwrite them with an average;
- optionally adjudicate large disagreements.

### Phase 7 — Consolidate, compare, and report

- verify every copied artifact against its source digest;
- emit a consolidation receipt;
- compute paired comparisons only from eligible pairs;
- preserve invalid, interrupted, missing, and excluded pairs in the report;
- write JSON and Markdown reports;
- optionally commit the coordinator branch after the operator reviews repository-size and privacy policy.

## 7. Timing, token, and cost semantics

Ambiguous “total time” is prohibited. The following fields have distinct meanings.

### 7.1 Per phase and per arm

- `phase_wall_seconds`: monotonic time from phase start to terminal phase state, including waits owned by that arm.
- `active_process_seconds`: sum of measured child-process durations in the phase.
- `provider_elapsed_seconds`: provider request start to terminal provider event.
- `first_output_latency_seconds`: provider start to first structured output event.
- `verification_seconds`: deterministic host verification duration.
- `queue_wait_seconds`: time waiting for rate-limit, resource, or scheduler capacity.
- `human_review_seconds`: active reviewer time, recorded only in human-review phases.

### 7.2 Pair and run totals

- `pair_wall_seconds`: launch-barrier release until both arms reach terminal state.
- `pair_start_skew_seconds`: absolute difference between actual arm start timestamps.
- `pair_sum_arm_wall_seconds`: sum of both arm wall times; useful for consumed effort, not elapsed time.
- `pair_critical_path_seconds`: maximum arm critical path.
- `benchmark_wall_seconds`: run-plan seal to completed consolidation.
- `benchmark_machine_seconds`: sum of measured non-human process durations.
- `benchmark_human_seconds`: sum of reviewer active durations.

### 7.3 Usage fields

Capture per phase, arm, pair, and run:

- input tokens;
- cached input tokens;
- cache-write input tokens;
- output tokens;
- reasoning output tokens;
- provider total tokens;
- retry count and retry usage;
- provider-billed cost;
- locally estimated cost;
- currency and price-catalog identity.

Unknown values remain `null`; they are never converted to zero. Provider-billed and locally estimated cost remain separate. Costs with different currencies or price catalogs are not combined.

### 7.4 Phase allocation

A provider event must be associated with an explicit phase ID at capture time. Usage may not be allocated after the fact by guessing from timestamps. Events that cannot be assigned make phase usage incomplete while preserving arm-level totals if those remain authoritative.

## 8. Machine evaluation

### 8.1 Eligibility guardrails

A trial is `invalid`, not `fail`, when evidence cannot support a fair comparison. Required guardrails include:

- identical task, fixture, base revision, model, executor, effort, environment, and tool-policy identities across the pair;
- valid constraint-profile inventories;
- start skew within the configured limit;
- no writes outside the arm worktree or allowed scope;
- no sibling-worktree or hidden-oracle access;
- complete provider evidence or an explicitly allowed missingness policy;
- valid final receipt and artifact digests;
- no undeclared human steering or assistance;
- no task prompt mutation;
- no secret or restricted-data exposure;
- no benchmark harness failure;
- visual capture environment matches its lock file;
- required artifacts and evaluation commands are present.

A functional defect, test failure, poor UI, excessive scope, or task-induced timeout is a valid scored failure. A host crash, missing provider usage stream, corrupted receipt, unequal environment, or one-sided infrastructure retry makes the pair invalid.

### 8.2 Recommended initial machine score

Machine score is 0–100 after eligibility:

| Dimension | Points | Evidence |
|---|---:|---|
| Hidden functional requirements | 45 | Hidden tests and oracle-linked assertions |
| Public regression suite | 15 | Public tests and unchanged baseline behavior |
| Robustness and edge cases | 10 | Hidden malformed/empty/large input tests |
| Accessibility and deterministic UI behavior | 10 | Interaction script, keyboard path, serious/critical accessibility findings, console errors |
| Scope and deliverable completeness | 10 | Required files, forbidden files, patch scope, artifact inventory |
| Engineering quality gates | 10 | Formatter/linter/type/build checks selected by the fixture; no subjective model judge |

Guardrail failures do not merely subtract points. They invalidate the trial.

### 8.3 Efficiency metrics are not quality points

Tokens, cost, and time are reported beside quality. They do not directly increase quality score. A cheap but incorrect result must not outrank a correct result, and an expensive result must not receive quality credit merely for using more resources.

Recommended derived efficiency fields:

- cost per eligible pass;
- tokens per machine-score point;
- wall seconds per machine-score point;
- incremental workflow cost and time versus control;
- quality-adjusted cost using a declared formula in the benchmark spec.

## 9. Human visual evaluation

### 9.1 Recommended rubric

Human visual score is 0–100:

| Dimension | Weight |
|---|---:|
| Visual hierarchy and prioritization | 20 |
| Interaction clarity and affordances | 20 |
| Readability and information density | 15 |
| Consistency and design-system coherence | 15 |
| Responsive behavior across required viewports | 15 |
| Polish, balance, and absence of visible defects | 15 |

Every dimension uses anchored 1–5 descriptions in the rubric. Reviewers also record:

- pairwise preference: left, right, tie, or neither acceptable;
- blocking visual/usability defects;
- confidence from 1–5;
- review start/end and active duration;
- optional comments tied to screenshot IDs.

### 9.2 Reviewer thresholds

- development run: minimum one reviewer;
- decision-quality internal run: minimum two independent reviewers;
- publication-quality claim: minimum three reviewers or two plus documented adjudication.

Human score remains `not_complete` until the configured minimum is satisfied.

### 9.3 Composite score

Adopted initial composite:

```text
composite_score = 0.70 * machine_score + 0.30 * human_visual_score
```

A passing composite additionally requires:

- all eligibility guardrails pass;
- machine score at least 70;
- human visual score at least 60;
- no blocking human visual defect accepted by adjudication.

The report always exposes machine and human scores separately. The composite must never hide disagreement.

## 10. Adopted initial benchmark fixture

Use the existing backlog direction and make the first fixture a **visual priority picker** in a small, pinned, synthetic web application.

The task should require the agent to:

1. ingest a supplied backlog JSON file;
2. implement a deterministic priority calculation from declared impact, urgency, effort, confidence, and risk fields;
3. present ranked items in a responsive dashboard;
4. provide filtering, sorting, item detail, and keyboard-operable interactions;
5. handle empty, malformed, and large inputs;
6. retain or export the selected ordering in a declared format;
7. add tests and update concise project documentation;
8. produce a polished visual result at pinned desktop, tablet, and mobile viewports.

Why this fixture is useful:

- substantial machine-testable behavior;
- clear visual and usability component;
- bounded implementation size;
- meaningful opportunities for overengineering, scope drift, weak testing, and visual inconsistency;
- no need for live data, secrets, or external services;
- directly aligns with current `BKL-010` rather than adding an unrelated benchmark concept.

The final task requirements, formula, starter framework, and visual rubric should be frozen before pilot runs and must not be tuned after seeing arm results.

## 11. Repetition, cache, retry, and assistance policy

The paired arms, first fixture, and composite weighting are decided by `DEC-008`. This section remains the proposed resolution of the still-open portions of `DEC-002`: first executors, billing semantics, cache controls, repetition/effect thresholds, and assisted/interrupted-trial policy.

### 11.1 Repetitions

- smoke validation: 1 paired repetition;
- development calibration: 3 paired repetitions;
- internal decision run: at least 10 eligible paired repetitions;
- publication or strong winner claim: at least 20 eligible paired repetitions.

The report may describe smaller samples but may not declare a statistically supported winner below the configured threshold.

### 11.2 Pair scheduling

Run the two arms of a pair concurrently. Run pairs sequentially by default (`pair_concurrency = 1`) to reduce host contention and provider-rate-limit confounding. Higher pair concurrency is a separately declared experiment setting.

Randomize which arm receives execution slot A or B. Record actual start skew, host load, and rate-limit events.

### 11.3 Cache policy

Use `provider-default-observed` for the first real-provider benchmark unless the executor provides a verifiable cache-disable control. Add the same fresh pair nonce to both arm requests for each repetition. Record cached and cache-write tokens separately.

Do not describe this as a cold-cache benchmark unless the provider supplies verifiable evidence. Cost comparisons become descriptive when cache evidence is missing or materially asymmetric.

### 11.4 Retry policy

- task-level retries and self-corrections are part of the arm result and its cost;
- infrastructure failures invalidate the pair;
- an infrastructure retry reruns **both arms** under a new pair attempt so one arm does not receive a selective advantage;
- all failed attempts remain in evidence and retry lineage;
- no cherry-picking the best completion.

### 11.5 Interrupted or human-assisted trials

- an operator interrupt caused by infrastructure or safety policy invalidates the pair;
- an agent-requested clarification answered by a human invalidates the default unassisted cohort;
- steering, manual fixes, or review feedback create a separate `assisted` cohort and may not be mixed with unassisted results;
- human visual scoring after execution does not count as assistance because it cannot change the artifact.

## 12. Statistical comparison and winner policy

Primary metric:

```text
eligible_pass_rate
```

Secondary metrics:

- machine score;
- human visual score;
- composite score;
- provider cost;
- tokens;
- pair wall time;
- retries;
- scope violations;
- requirement-level failures.

Recommended quality effect threshold:

```text
5 composite-score points
```

Recommended non-inferiority guardrail for efficiency claims:

```text
workflow_full machine score may not be more than 3 points worse than control_raw
```

A `workflow_full` winner may be declared only when:

1. minimum eligible pair count is met;
2. there is no unresolved missingness or identity contradiction;
3. the paired confidence interval supports the configured primary-metric effect;
4. machine quality is not inferior beyond threshold;
5. human visual review is complete and does not show a material regression;
6. efficiency costs are reported, not hidden.

Otherwise the result is `no_winner`, `descriptive_only`, or `incomplete`.

## 13. Contracts and schema changes

Recommended new or revised contracts:

1. `agent-workflow/benchmark-spec/v1` — suite, cases, phases, arms, profiles, scorers, visual rubric, scheduling, thresholds, retention.
2. `agent-workflow/benchmark-run/v1` — immutable run plan and current run identity.
3. `agent-workflow/benchmark-arm/v1` — arm identity, worktree, effective prompt, profile, terminal state, artifact inventory.
4. `agent-workflow/benchmark-phase-event/v1` — append-only phase lifecycle and metrics event.
5. `agent-workflow/benchmark-pair/v1` — paired identity, start barrier, comparability and retry lineage.
6. `agent-workflow/benchmark-machine-score/v1` — eligibility plus machine score components.
7. `agent-workflow/benchmark-human-review/v1` — blinded review assignment and immutable reviewer result.
8. `agent-workflow/benchmark-consolidation-receipt/v1` — source-to-destination digest mapping.
9. `agent-workflow/benchmark-report/v2` — explicit arms, machine/human scores, phase metrics, pair missingness, and winner policy.
10. `agent-workflow/trial-evidence/v3` — separate `task_prompt_sha256`, `arm_wrapper_sha256`, `effective_prompt_sha256`, `constraint_profile_sha256`, `pair_id`, `phase_metrics`, and visual evidence identity.

The existing `evaluation-plan/v1`, score receipts, final receipts, provider evidence, and command/scope collections remain reused wherever possible.

The paired comparison key must use:

```text
benchmark_id
case_id
pair_id or repetition
base_revision
fixture_sha256
task_prompt_sha256
input_bundle_sha256
model/executor/version/effort
environment_sha256
tool_policy_sha256
resource_policy_sha256
```

It must **not** require equal arm-wrapper or effective-prompt hashes.

## 14. Modular implementation boundary

Add benchmark processing to the `agent-workflow` repository, but isolate it so it can later become a first-party `agent-workflow-bench` plugin.

Recommended package shape:

```text
src/agent_workflow/benchmarking/
├── __init__.py
├── contracts.py
├── planning.py
├── coordinator.py
├── pairing.py
├── phase_events.py
├── metrics.py
├── consolidation.py
├── comparison.py
├── reporting.py
├── ports.py
├── adapters/
│   ├── core_worktrees.py
│   ├── core_runner.py
│   ├── core_receipts.py
│   └── provider_events.py
├── scoring/
│   ├── registry.py
│   ├── functional.py
│   ├── scope.py
│   ├── accessibility.py
│   └── artifacts.py
└── visual/
    ├── capture.py
    ├── rubric.py
    ├── blinding.py
    └── review.py
```

Boundary rules:

- benchmark services depend on explicit ports, not CLI internals;
- core worktree, process, receipt, provider-evidence, and contract validation remain the authority;
- benchmark code may read sealed evidence through a stable evidence-reader interface;
- CLI parsing and rendering remain thin adapters;
- visual/browser dependencies are optional extras;
- no browser, statistics, or human-review dependency enters the minimal core installation;
- scorer registration is explicit and allowlisted, not arbitrary code named in a benchmark file;
- future extraction preserves schema IDs and CLI behavior through the plugin host.

Recommended extras:

```toml
benchmark = [statistics dependency]
benchmark-visual = [pinned browser automation and accessibility dependencies]
```

Do not add a general workflow framework or model-as-judge dependency for the initial benchmark.

## 15. CLI surface

Proposed commands:

```bash
agent-workflow benchmark validate benchmarks/specs/priority-picker-v1/benchmark-spec.json
agent-workflow benchmark auth-check benchmarks/specs/priority-picker-v1/executors/codex-subscription.json
agent-workflow benchmark readiness benchmarks/specs/priority-picker-v1/benchmark-spec.json \
  --executor benchmarks/specs/priority-picker-v1/executors/codex-subscription.json \
  --policy benchmarks/specs/priority-picker-v1/policies/development.json
agent-workflow benchmark plan benchmarks/specs/priority-picker-v1/benchmark-spec.json \
  --repo /path/to/target --base-ref HEAD \
  --executor benchmarks/specs/priority-picker-v1/executors/codex-subscription.json \
  --policy benchmarks/specs/priority-picker-v1/policies/development.json
agent-workflow benchmark run <run-plan.json>
agent-workflow benchmark status <run-id>
agent-workflow benchmark resume <run-id>
agent-workflow benchmark score <run-id>
agent-workflow benchmark visual-capture <run-id>
agent-workflow benchmark review <run-id> --reviewer <local-reviewer-id>
agent-workflow benchmark consolidate <run-id>
agent-workflow benchmark report <run-id> --markdown benchmarks/runs/<run-id>/report.md
agent-workflow benchmark verify benchmarks/runs/<run-id>
```

`run` creates the coordinator worktree and arm worktrees. `consolidate` always targets the coordinator worktree, never the original checkout.

## 16. Prompt-pack structure

Two distinct artifacts should be created:

### 16.1 Capability implementation pack

```text
prompt-packs/comparative-benchmark-foundation/
```

This pack implements the benchmark contracts, coordinator, metrics, scorers, visual review, docs, tests, and backlog updates in phases.

### 16.2 Runnable benchmark pack

```text
benchmarks/specs/priority-picker-v1/
```

This is the actual benchmark suite and fixture definition. It references a canonical prompt pack only for the `workflow_full` arm. The `control_raw` arm receives the same canonical task phases without the workflow wrapper.

Do not make the benchmark fixture itself own implementation backlog items for the `agent-workflow` product.

## 17. Implementation phases and acceptance gates

### Implementation Phase 0 — Decision and contract freeze

- approve this spec;
- resolve `DEC-002` (completed by the subscription-first operating policy);
- define canonical backlog ownership;
- freeze schema names and migration policy;
- write strict future acceptance journeys.

### Implementation Phase 1 — Contracts and deterministic data processing

- schemas and templates;
- task/effective-prompt separation;
- pair comparability logic;
- phase metrics and total-time semantics;
- report v2 and migration from existing trial evidence;
- no live provider runs.

### Implementation Phase 2 — Worktree coordinator and arm profiles

- coordinator and arm worktree topology;
- launch barrier and randomized slots;
- neutral safety envelope;
- control and workflow profile inventory;
- pair-level retry and state recovery;
- synthetic executor journey.

### Implementation Phase 3 — Consolidation and evidence integrity

- arm-local staging;
- copied-artifact digest verification;
- consolidation receipt;
- `benchmarks/runs` layout;
- retention and large-artifact policy;
- resume and verify journeys.

### Implementation Phase 4 — Priority-picker fixture and machine scoring

- frozen starter fixture;
- public and hidden tests;
- oracle/canary handling;
- requirement map;
- machine score and guardrails;
- one synthetic paired benchmark acceptance journey.

### Implementation Phase 5 — Visual capture and human review

- pinned browser image and font manifest;
- pre-seal visual evidence bridge required by `BKL-010`;
- screenshot/DOM/accessibility capture;
- blinded review assignment;
- human-review schema and report integration.

### Implementation Phase 6 — Pilot, calibration, and independent gate

- one smoke pair with a fixture executor;
- three paired development repetitions with a real executor only after security and compatibility prerequisites;
- rubric calibration and hidden-test review without changing requirements based on arm identity;
- independent phase gate and release-drift audit;
- no winner claim from the pilot.

### Implementation Phase 7 — Decision cohort

- at least ten eligible real-provider pairs under one sealed subscription or explicit API cohort;
- complete human review;
- final sealed report and reproducibility package;
- explicit decision on whether evidence justifies workflow defaults or specific simplifications.

## 18. Required installed-product acceptance journeys

The implementation is incomplete without black-box journeys proving:

1. the original checkout remains unchanged while coordinator and arm worktrees receive all writes;
2. both arms start from the same commit and task digest but different declared wrappers;
3. the paired comparator accepts different effective prompts and rejects different task prompts;
4. control does not receive any undeclared agent-workflow instruction or skill;
5. each pair starts behind a barrier and records start skew;
6. one arm cannot read or write the sibling worktree;
7. phase token, cost, wall, verification, and total fields preserve null versus zero semantics;
8. an infrastructure failure retries both arms and preserves the failed attempt;
9. an agent task failure remains a valid fail rather than an invalid trial;
10. human assistance moves a trial out of the unassisted cohort;
11. visual evidence is captured with the pinned image/font/viewport identity;
12. blinded reviewer assignments do not reveal arm identity;
13. consolidation verifies every digest and writes only inside the coordinator worktree;
14. incomplete human review cannot produce a final composite or winner;
15. a full run can be verified from `benchmarks/runs/<run-id>` after arm worktrees are removed.

## 19. Explicit non-goals for version 1

- benchmarking many providers or models simultaneously;
- automatic model-as-judge scoring;
- online adaptive stopping or self-modifying rubrics;
- tuning the task after observing treatment/control results;
- arbitrary third-party scorer execution;
- cloud benchmark orchestration;
- multi-host scheduling;
- public leaderboard service;
- storing secrets or live customer data;
- extracting the benchmark module into a separate repository before its interfaces have real evidence;
- measuring every agent-workflow feature through ablation in the first run.

## 20. Adopted and pending decisions

| Decision | Value | State |
|---|---|---|
| First comparison | `control_raw/v1` vs `workflow_full/v1` | adopted |
| Execution mode | paired parallel, one pair at a time | adopted |
| First fixture | synthetic visual priority picker | adopted by `DEC-008` |
| Machine/human composite | 70% / 30% | adopted by `DEC-008` |
| Primary metric | eligible pass rate | pending `DEC-002` |
| Minimum internal decision cohort | 10 eligible pairs | pending `DEC-002` |
| Publication cohort | 20 eligible pairs | pending `DEC-002` |
| Cache policy | provider-default-observed unless verifiably disabled | pending `DEC-002` |
| Human assistance | separate cohort; excluded from unassisted result | pending `DEC-002` |
| Infrastructure retry | rerun both arms; preserve all attempts | pending `DEC-002` |
| Task failure | valid fail | pending `DEC-002` |
| Infrastructure/evidence failure | invalid pair | pending `DEC-002` |
| Human reviewers | 1 development, 2 internal decision, 3 publication or adjudication | pending `DEC-002` |
| Real paid execution | blocked until required isolation/privacy/compatibility gates are accepted | existing product gate |
| Future modularization | benchmark module first, `agent-workflow-bench` plugin only after proven | design baseline |

## 21. Implemented frozen fixture

The priority-picker canonical task and requirement-to-evaluation matrix are frozen at [`../benchmarks/specs/priority-picker-v1/`](../benchmarks/specs/priority-picker-v1/). The suite defines every visible requirement, hidden check, machine-score point, visual capture, human-rubric dimension, allowed path, non-target, and phase prompt. Changes to those artifacts require a new benchmark version and may not be made after observing arm results for an existing version.
