# Comparative benchmark: task, evaluations, scoring, and interpretation

> **Applies to:** `agent-workflow` 0.7.8, built-in benchmark `priority-picker-v1`, benchmark specification version `1.1.0`, and the currently shipped v1 evaluator semantics.

## Purpose

The comparative benchmark measures whether applying the full `agent-workflow` discipline improves the quality and reliability of an agent's implementation of the same software task, and what that discipline costs in time, tokens, and money.

Each benchmark repetition runs two arms from the same frozen source revision, fixture, canonical task, model/executor configuration, and benchmark-neutral safety envelope:

- `control_raw`: the agent uses its normal coding approach without the `agent-workflow` planning, traceability, drift-review, completion-evidence, or phase-gate wrapper.
- `workflow_full`: the same agent receives the full benchmarked workflow discipline.

The arms execute in separate Git worktrees and are launched as a synchronized pair. Their output, timing, usage, costs, visual evidence, machine evaluations, and human reviews are retained separately and then consolidated into the benchmark run record.

The experiment is designed to answer two different questions without conflating them:

1. **Quality:** Did the workflow arm produce a more correct, complete, robust, accessible, and polished implementation?
2. **Efficiency:** How much additional or reduced wall time, active process time, token usage, and cost accompanied that quality result?

Efficiency is currently descriptive. It does not add or remove points from the quality score.

---


## Repository ownership and 0.7.8 module boundary

In 0.7.8 the comparative benchmark is a **built-in feature**, not a plugin. Its current source ownership is deliberately split by function:

| Surface | 0.7.8 owner |
|---|---|
| CLI grammar | `src/agent_workflow/cli_parser.py` |
| Benchmark command dispatch | `src/agent_workflow/cli_handlers/benchmark.py` |
| Public feature/service facade | `src/agent_workflow/benchmarking/service.py` and `src/agent_workflow/benchmarking/__init__.py` |
| Contracts and validation | `src/agent_workflow/benchmarking/contracts.py` plus `schemas/benchmark-*.schema.json` |
| Planning, paired execution, metrics, consolidation | `src/agent_workflow/benchmarking/planning.py`, `pairing.py`, `runner.py`, `metrics.py`, and `consolidation.py` |
| Machine scoring and reports | `src/agent_workflow/benchmarking/scoring.py`, `reporting.py`, and `statistics.py` |
| Visual capture/runtime and human review | `src/agent_workflow/benchmarking/visual.py`, `runtime.py`, and `review.py` |
| Repository benchmark source | `benchmarks/specs/priority-picker-v1/` |
| Installed/exported benchmark mirror | `src/agent_workflow/assets/benchmarks/priority-picker-v1/` |
| Focused acceptance/invariants | `tests/acceptance/test_comparative_benchmark_journey.py` and `tests/invariants/test_comparative_benchmark_*.py` |

The trusted plugin API in 0.7.8 supports explicitly enabled top-level plugin commands and digest-bound package schema/asset resources through `agent_workflow.plugins`. It does **not** provide a generic benchmark-scorer or evaluator hook framework. The correction program must therefore remain inside the bounded built-in `agent_workflow.benchmarking` feature, preserve the core authority and evidence services, and keep pure scoring/evaluator contracts extractable for a future evidence-gated feature extraction. It must not add an ad hoc second plugin registry or prematurely move the benchmark into a separate distribution.

The repository suite and installed-package mirror are both authoritative release surfaces: the source suite is edited first, the installed mirror must be synchronized byte-for-byte, and `scripts/audit-release-assets.py` must reject drift.

## What the agents are prompted to build

The reference benchmark is `priority-picker-v1`. It starts from an intentionally incomplete, dependency-free Python repository and asks each arm to implement **Priority Picker**, a small backlog-prioritization web application.

### Input contract

The application reads six supplied backlog records from `data/backlog.json`. Every record must contain:

- `id`: a non-empty, unique string;
- `title`: a non-empty string;
- `impact`, `urgency`, `effort`, `confidence`, and `risk`: numeric values from 1 through 5;
- `status`: one of `planned`, `ready`, `in_progress`, or `blocked`;
- `description`: a string.

Malformed records and duplicate IDs must be rejected with useful errors. Empty input is valid.

### Frozen scoring formula

Each record receives this priority score:

```text
score = round(
    (2*impact + 1.5*urgency + confidence + 0.5*risk)
    / max(effort, 1),
    4
)
```

The default ordering is:

1. score descending;
2. urgency descending;
3. impact descending;
4. ID ascending.

The implementation must preserve deterministic ordering and must rank 1,000 valid records within two seconds on the benchmark host.

### Required Python interface

The module that owns the priority logic must expose these functions:

```python
calculate_priority(item)
validate_items(items)
rank_items(items)
filter_items(items, query="", status="all", risk="all")
sort_items(items, key="priority", direction="desc")
export_ordering(items, destination)
load_backlog(path)
```

### Required browser interface

The finished application must provide:

- a clear title and summary counts;
- persistent visible labels for search, status, risk, and sort controls;
- a ranked list showing rank, title, score, status, and all five scoring factors;
- an item-detail interaction showing the description and full factor breakdown;
- JSON export of the current ordering;
- useful empty-data and invalid-data states;
- keyboard-operable controls and item-detail interaction;
- responsive layouts for desktop, tablet, and mobile;
- no horizontal page overflow at the frozen viewports.

Stable `data-testid` hooks are part of the benchmark contract so the browser evaluator can find the application, controls, list, items, detail region, and export action deterministically.

### Explicit non-targets

The solution must use only the Python standard library and browser-native HTML, CSS, and JavaScript. It must not add:

- package-manager dependencies;
- frameworks or build systems;
- persistence;
- authentication;
- analytics;
- network integrations;
- unrelated abstractions.

The supplied backlog fixture is immutable.

---

## The three benchmark phases

The canonical work is divided into three phases. Both arms receive the same phase objective; only the arm wrapper differs.

### Phase 1: analyze and plan

The agent inspects the starter repository and public tests, then writes `BENCHMARK_PLAN.md` containing:

- a concise requirements map;
- intended file changes;
- verification commands;
- visual and accessibility checks;
- risks;
- explicit non-targets.

The agent is told not to implement the application during this phase.

This phase measures whether the agent understands and bounds the task before editing.

### Phase 2: implement

The agent implements the complete application within the declared writable scope, preserves the input fixture, remains dependency-free, and adds focused tests and documentation.

### Phase 3: verify and repair

The agent runs public tests and relevant standard-library checks, exercises the application, inspects responsive and keyboard behavior where tooling permits, repairs defects, and leaves the worktree in its strongest final state. It may not weaken requirements or tests to obtain a passing result.

---

## What differs between the benchmark arms

### `control_raw`

The control wrapper asks the agent to complete the phase using its normal coding approach. It imposes no particular planning format, workflow protocol, review checklist, completion template, delegation pattern, or evidence narrative beyond the canonical phase deliverable.

### `workflow_full`

The workflow wrapper adds the following discipline:

1. bind every edit to a canonical requirement and preserve explicit non-targets;
2. inspect before editing and maintain the phase plan;
3. stay inside declared writable scope;
4. avoid speculative abstractions and dependencies;
5. implement the smallest coherent vertical slice before expanding;
6. treat public tests as necessary but insufficient;
7. verify malformed, empty, scale, keyboard, responsive, and export paths;
8. perform contradiction, drift, scope, and stale-document reviews;
9. retain concise evidence of commands, outcomes, uncertainties, and changed files;
10. never claim a check that was not actually run.

The benchmark therefore measures the treatment effect of workflow discipline rather than the effect of a different task or fixture.

---

# Machine evaluation

The automated quality score is nominally 100 points across six dimensions.

| Dimension | Maximum |
|---|---:|
| Hidden functional behavior | 45 |
| Public regression suite | 15 |
| Robustness | 10 |
| Accessibility and deterministic UI | 10 |
| Scope and completeness | 10 |
| Engineering quality | 10 |
| **Total** | **100** |

The current evaluator uses an equal-share algorithm within each dimension. If a dimension contains `N` checks and `P` maximum points, each passing check is effectively worth `P / N`. There is no per-check weight field in the implemented evaluator.

## Hidden functional behavior — 45 points

The current hidden evaluator has nine checks. Each passing check is therefore worth 5 points.

| Check | Current machine assertion | Effective points |
|---|---|---:|
| `formula` | One representative item produces exactly `10.0` | 5 |
| `tie-break` | Two otherwise equal items are ordered by ID ascending | 5 |
| `score-attached` | Ranked records expose a `score` value | 5 |
| `search` | Search matches a title case-insensitively | 5 |
| `status` | Status filtering selects the requested status | 5 |
| `risk` | Risk filtering selects the requested risk value | 5 |
| `sort` | Alternate title sort in ascending order works | 5 |
| `export` | Export preserves ranked IDs and includes first rank | 5 |
| `load` | The supplied six-item fixture loads | 5 |

A solution passing seven of the nine checks earns:

```text
45 × 7 / 9 = 35 points
```

### What this currently does not prove exhaustively

The hidden functional dimension does not currently prove all of the behavior implied by the frozen requirement matrix. For example, it does not comprehensively exercise:

- every numeric field and range boundary;
- missing or extra required fields;
- every allowed and disallowed status;
- decimal inputs, effort-floor behavior, and four-place rounding boundaries;
- every level of the score/urgency/impact/ID tie chain;
- stable non-mutating behavior;
- description search or combined filters;
- invalid sort keys and directions;
- complete exported schema and destination behavior;
- browser-side search/filter/sort/export behavior.

These omissions are part of the correction backlog described later in this document.

## Public regression suite — 15 points

The visible public suite checks representative examples for:

- the frozen formula;
- deterministic tie-breaking;
- rejection of an invalid effort value;
- ranked JSON export.

The current scorer executes the entire public suite as one check:

- all public tests pass: 15 points;
- any public test fails: 0 points.

This is intentionally visible evidence, but its current all-or-nothing scoring means a single failing public assertion has the same score effect as a completely nonfunctional public suite.

## Robustness — 10 points

The current robustness evaluator has five checks worth 2 points each.

| Check | Current machine assertion | Points |
|---|---|---:|
| `empty` | `rank_items([])` returns an empty list | 2 |
| `duplicate` | Duplicate IDs raise `BacklogValidationError` | 2 |
| `boolean` | `True` is not accepted as a numeric factor | 2 |
| `malformed-root` | A non-collection root is rejected | 2 |
| `scale` | 1,000 valid records rank in under two seconds | 2 |

The scale check verifies elapsed time and result length. It does not currently prove deterministic output across repeated runs, stable memory behavior, or non-mutation of the input collection.

## Accessibility and deterministic UI — 10 points

Browser capture runs the submitted HTML, CSS, and JavaScript in Chromium at three frozen viewports:

- desktop: `1440 × 1000`;
- tablet: `834 × 1112`;
- mobile: `390 × 844`.

The visual evaluator produces lower-level browser checks. The machine scorer then combines them into five all-or-nothing groups worth 2 points each.

| Group | Required lower-level checks | Points |
|---|---|---:|
| Runtime/application | Runtime versions match and the app renders at least one item | 2 |
| Labels/structure | Controls have persistent labels and exactly one `main` exists | 2 |
| Keyboard | Focus enters/advances and Enter populates item detail | 2 |
| Responsive | No horizontal overflow at all three viewports | 2 |
| Browser/export | No console errors and an export control has visible text | 2 |

A group receives zero when any lower-level member fails. For example, correct desktop and tablet layouts receive no responsive points if mobile overflows.

### Important interpretation limits

The current browser checks are useful but narrower than their labels may suggest:

- `focus-visible` proves that focus can enter and advance; it does not prove a visible focus indicator is actually rendered.
- `export-control` proves the control exists and has visible text; it does not prove that a correctly ordered JSON download occurs.
- `keyboard-detail` checks Enter activation on the first item and meaningful detail text; it does not prove all items, click parity, Escape behavior, or focus restoration.
- the evaluator does not currently automate search, status, risk, or sort interactions in the browser.
- empty and invalid-data visual states are not currently captured.
- accessible names, roles, heading structure, contrast, live-region behavior, and automated accessibility-engine findings are not comprehensively assessed.

## Scope and completeness — 10 points

The current evaluator has five checks worth 2 points each:

- required Python and browser files exist;
- `BENCHMARK_PLAN.md` exists and is longer than 80 characters;
- `README.md` mentions scoring and operation;
- the supplied fixture remains present with six records;
- common dependency files or `node_modules` were not introduced.

Out-of-scope writes are not handled as ordinary points. They are evaluated separately as an eligibility guardrail.

## Engineering quality — 10 points

The current evaluator has five checks worth 2 points each:

- Python sources compile;
- public tests pass;
- no `TODO` or `NotImplementedError` remains in the implementation surface;
- the README states the frozen formula;
- the plan mentions verification and non-targets.

The public tests therefore affect both the 15-point public dimension and a 2-point engineering check. This duplication is visible and should be either explicitly justified or removed in the corrected scoring contract.

---

# Human visual evaluation

Machine checks establish basic behavior and deterministic capture, but they cannot reliably judge whether the interface is visually clear, balanced, coherent, and professional. Human reviewers therefore score blinded evidence.

Review assignments label the two arms only as `left` and `right`. Treatment mappings are stored separately so the reviewer does not know which result came from `control_raw` or `workflow_full`.

## Human visual dimensions

| Dimension | Weight |
|---|---:|
| Visual hierarchy and prioritization | 20 |
| Interaction clarity and affordances | 20 |
| Readability and information density | 15 |
| Consistency and design-system coherence | 15 |
| Responsive behavior | 15 |
| Polish and absence of visible defects | 15 |
| **Total** | **100** |

Each dimension is rated from 1 through 5. The conversion is linear:

```text
dimension points = dimension weight × ((rating - 1) / 4)
```

The scale therefore behaves as follows:

| Rating | Share of that dimension's weight |
|---:|---:|
| 1 | 0% |
| 2 | 25% |
| 3 | 50% |
| 4 | 75% |
| 5 | 100% |

Examples:

- all ratings of 3 produce a human score of 50;
- all ratings of 4 produce 75;
- all ratings of 5 produce 100.

The reviewer also records preference, confidence, comments, and blocking visual defects. Preference and confidence are descriptive and do not directly change the score.

## Minimum reviewers

| Claim level | Minimum reviewers per pair |
|---|---:|
| Development | 1 |
| Internal | 2 |
| Publication | 3 |

When multiple reviews are complete, the human score for each arm is the arithmetic mean of the submitted reviewer scores.

## Blocking defects

A reviewer may identify a blocking defect for the left arm, right arm, or both. A blocking defect prevents the affected arm from receiving a composite score even when its numerical human score is otherwise present.

---

# Eligibility guardrails

A high raw machine score is not sufficient to make a benchmark trial valid. Required experimental and evidence guardrails are evaluated before the machine score is accepted.

| Guardrail | What it protects |
|---|---|
| `paired_identity` | Both arms received the same canonical task and pair-bound inputs |
| `declared_treatment` | The treatment wrappers differ while the canonical task digest remains equal |
| `start_skew` | The paired arms started within the configured synchronization limit |
| `writable_scope` | The arm did not modify prohibited paths |
| `assistance_cohort` | Human assistance matches the sealed operating policy |
| `visual_capture` | Required visual evidence completed under an accepted runtime state |
| `provider_usage` | Required usage evidence is complete |
| `harness_integrity` | The arm did not terminate because the benchmark infrastructure failed |

Sandbox isolation is also recorded. It is required for publication eligibility when the publication policy and runtime demand it.

If a required guardrail fails, or if a scorer itself experiences a harness failure,
the completed scorer observations are still retained:

```text
machine_score = observed sum of earned points
eligible_machine_score = null
eligibility = invalid
```

The observed score is descriptive only. It cannot contribute to a composite or
winner claim unless eligibility is `eligible`. This separation preserves useful
results without presenting an invalid experiment as a qualified comparison.

---

# Composite score and passing status

After an arm is machine-eligible and enough blinded human reviews have been submitted, the composite is:

```text
composite = 0.70 × machine_score
          + 0.30 × human_visual_score
```

Example:

```text
machine = 88
human   = 75

composite = 0.70 × 88 + 0.30 × 75
          = 84.1
```

The current benchmark marks an arm as passing only when both component floors are satisfied:

```text
machine score >= 70
human visual score >= 60
```

There is no separate minimum composite threshold. A composite is not produced when:

- machine eligibility is invalid;
- required human review is incomplete;
- the arm has a blocking visual defect;
- a machine scorer has a harness failure.

This prevents visual polish from masking a broken implementation and prevents machine correctness from masking an unusable interface.

---

# Cohort statistics and winner declaration

A single development pair is descriptive. It cannot establish a statistically supported winner.

| Operating profile | Paired repetitions | Winner policy |
|---|---:|---|
| Development | 1 | Disabled |
| Internal | 10 | Enabled |
| Publication | 20 | Enabled |

For every complete pair, the report calculates:

```text
workflow_full metric - control_raw metric
```

The implementation uses a deterministic paired-bootstrap 95% confidence interval.

For `workflow_full` to be declared the winner:

- every required pair must be machine-eligible;
- every required pair must have complete human review;
- the minimum repetition count must be met;
- the lower confidence bound for composite improvement must be at least 5 points;
- the machine-score confidence interval must not show a regression worse than 3 points;
- the human-score confidence interval must not show a regression worse than 3 points.

The same logic is applied in the opposite direction for `control_raw`. Otherwise, the result is reported as no winner or descriptive only.

---

# Timing, usage, and cost evidence

The benchmark records efficiency and cost separately from quality points. Depending on executor support, evidence includes:

- phase wall time;
- active process time;
- provider elapsed time;
- first-output latency;
- queue wait time;
- visual-capture time;
- machine-verification time;
- pair wall time and critical path;
- input, output, cached, and provider-total tokens;
- provider-billed cost when attributable;
- API-equivalent estimated cost;
- optional subscription allocation;
- local estimated cost;
- infrastructure retry counts.

Subscription-backed CLI sessions are the default real-executor authentication path. API-key adapters are optional and explicit. Subscription use is not represented as zero provider cost: provider-billed cost remains unavailable unless the provider can attribute it to the run, while estimates and optional allocation fields remain separately labeled.

Efficiency metrics do not currently change the machine score, composite, passing status, or winner threshold. This makes the quality conclusion easy to interpret, but it also means a workflow can win on quality despite materially higher time or token cost. The correction backlog includes an explicit decision item for whether efficiency should remain descriptive or become a separate non-inferiority or value threshold.

---

# Known scoring-contract discrepancies

The current evaluator code is authoritative for existing runs, but it is not fully aligned with the frozen requirement-to-evaluation matrix.

## 1. The matrix's requirement-level point arithmetic is internally inconsistent

The matrix states a 45-point hidden-functional total, but the named hidden allocations add to 43:

```text
formula 10
+ ordering 5
+ strict validation 8
+ search/filter/sort 12
+ detail/export 8
= 43
```

The matrix also assigns 4 accessibility points to responsive behavior and 10 accessibility points to keyboard/accessibility while declaring the whole accessibility dimension to be 10 points.

A corrected contract must define an exact, non-overlapping per-check allocation that sums to each dimension total and to 100 overall.

## 2. The implementation equal-weights checks within a dimension

The generic `outcome` calculation awards:

```text
dimension maximum × passed checks / total checks
```

As a result:

- the formula is worth 5 implemented points rather than the matrix's stated 10;
- every hidden check is worth the same amount regardless of requirement importance;
- every robustness and engineering check is equally weighted;
- accessibility group members are all-or-nothing within each two-point group.

## 3. Validation depth is smaller than the stated contract

The evaluator tests duplicate IDs, booleans, a malformed root, and one public invalid-effort case, but it does not comprehensively test all required fields, types, numeric ranges, status values, or error quality.

## 4. Browser behavior is under-tested

The browser evaluator captures the three viewports and basic keyboard behavior, but it does not currently prove browser-side search, filters, sorting, download content, empty/invalid states, visible focus styling, or broad accessibility semantics.

## 5. Public regression scoring is all-or-nothing

The entire public suite is one 15-point check. The corrected contract should explicitly preserve that choice or score public requirements individually.

## 6. Public tests are counted twice

Public-suite success contributes 15 points in the public dimension and 2 points in engineering quality. This may be intentional as a quality-gate signal, but the contract does not explain the duplication.

## 7. Documentation and implementation can drift independently

The requirement matrix, benchmark specification, evaluator code, packaged benchmark assets, man page, and explanatory documentation are maintained as separate surfaces. The correction plan should establish one machine-readable scoring source and generate or validate the derivative documentation.

## 8. The benchmark version surfaces already disagree

In the 0.7.8 tree, `benchmarks/specs/priority-picker-v1/benchmark-spec.json` declares benchmark specification version `1.1.0`, while `REQUIREMENT_EVALUATION_MATRIX.md` says it is frozen for version `1.0.0`. Both files are mirrored into `src/agent_workflow/assets/benchmarks/priority-picker-v1/`. This is a provenance and comparability defect even before changing any points: the correction contract must define separate benchmark-task, scoring-contract, evaluator, and report-schema versions and seal their digests into every corrected run.

---

# Required correction strategy

Existing `priority-picker-v1` results must remain interpretable under the evaluator that produced them. The correction must therefore avoid silently changing the meaning of version 1 scores.

The recommended strategy is:

1. preserve the current benchmark and evaluator as an immutable legacy version;
2. freeze an exact corrected requirement-to-check-to-weight contract;
3. create a new benchmark major version for changed scoring semantics;
4. implement explicit per-check weights and richer evidence;
5. add golden calibration solutions and mutation tests that prove each check changes only its intended points;
6. verify source and packaged benchmark assets are byte-equivalent;
7. generate or validate the matrix, scoring tables, documentation, and man-page summary from the same authoritative contract;
8. run an independent phase gate before using the corrected version for comparative claims.

See [`COMPARATIVE_BENCHMARK_CORRECTION_BACKLOG.md`](COMPARATIVE_BENCHMARK_CORRECTION_BACKLOG.md) and [`../prompt-packs/comparative-benchmark-scoring-corrections/`](../prompt-packs/comparative-benchmark-scoring-corrections/) for the 0.7.8-specific executable work sequence.
