# Comparative benchmark scoring correction backlog

## Purpose

This backlog corrects the mismatch between the benchmark's frozen requirement matrix, implemented evaluator behavior, browser coverage, and published scoring explanation.

This backlog is rebased to the 0.7.9 repository layout and records the implementation state reached by the benchmark-corrections checkpoints. Ticket prompts name the current relative owners while still requiring a bounded preflight so later behavior-preserving moves do not cause edits to stale compatibility facades.

## 0.7.9 implementation map

- CLI grammar: `src/agent_workflow/cli_parser.py`.
- Benchmark dispatch: `src/agent_workflow/cli_handlers/benchmark.py`.
- Built-in benchmark feature: `src/agent_workflow/benchmarking/`.
- Repository suite: `benchmarks/specs/priority-picker-v1/`.
- Installed/exported suite mirror: `src/agent_workflow/assets/benchmarks/priority-picker-v1/`.
- Evidence schemas: `schemas/benchmark-*.schema.json`.
- Focused tests: `tests/acceptance/test_comparative_benchmark_journey.py`, `tests/invariants/test_comparative_benchmark_contracts.py`, `tests/invariants/test_comparative_benchmark_operating_policy.py`, and `tests/invariants/test_cli_benchmark_handler_boundary.py`.
- Release drift: `scripts/audit-release-assets.py`.
- Documentation and operations: `docs/COMPARATIVE_BENCHMARK_*.md`, `docs/man/agent-workflow.1`, `README.md`, and `docs/COMMAND_REFERENCE.md`.

Under DEC-009, benchmarking remains a built-in feature. The 0.7.9 trusted plugin host exposes top-level plugin commands and digest-bound schema/asset resources, but no benchmark evaluator hook. This correction program must preserve the built-in authority boundary, avoid creating a second plugin registry, and make pure contract/evaluator surfaces extractable only for the later evidence-gated ARC-004 decision.

## Non-negotiable rules

- Do not silently change the meaning of an existing benchmark version.
- Preserve historical runs with the scorer and contract that produced them.
- Any point-weight or acceptance-semantic change requires a new benchmark major version.
- The corrected contract must be machine-readable and must sum exactly to 100 points.
- Quality score, experiment eligibility, human visual score, and efficiency metrics remain distinct concepts.
- `benchmarks/specs/priority-picker-v1/` and `src/agent_workflow/assets/benchmarks/priority-picker-v1/` must remain byte-identical for every exported asset.
- Do not use real provider cohorts to calibrate scoring logic; use deterministic fixtures and controlled mutations.

## Backlog summary

| ID | Priority | Risk | State | Objective | Dependencies |
|---|---:|---:|---|---|---|
| BENCH-CORR-001 | P0 | Critical | implemented | Corrected v2 contract and immutable v1 boundary are present | — |
| BENCH-CORR-002 | P0 | Critical | implemented | Explicit weighted scoring and deterministic receipts are enforced | BENCH-CORR-001 |
| BENCH-CORR-003 | P0 | High | implemented | Hidden functional and validation coverage is mapped to weighted checks | BENCH-CORR-001, BENCH-CORR-002 |
| BENCH-CORR-004 | P0 | High | implemented | Browser, keyboard, export, responsive, and accessibility evaluation is expanded | BENCH-CORR-001, BENCH-CORR-002 |
| BENCH-CORR-005 | P1 | High | implemented | Public-suite gate semantics and duplicate-credit policy are frozen | BENCH-CORR-001, BENCH-CORR-002 |
| BENCH-CORR-006 | P1 | High | implemented | Blinded human-review aggregation and adjudication contracts are hardened | BENCH-CORR-001 |
| BENCH-CORR-007 | P0 | Critical | implemented | Golden, mutation, scorer-isolation, and compact timing calibration exist | BENCH-CORR-002 through BENCH-CORR-005 |
| BENCH-CORR-008 | P1 | High | implemented | Contract, packaged assets, generated docs, and release drift checks share one authority | BENCH-CORR-001, BENCH-CORR-002 |
| BENCH-CORR-009 | P1 | High | implemented | v1 evidence remains immutable and mixed-version comparison fails closed | BENCH-CORR-001, BENCH-CORR-007, BENCH-CORR-008 |
| BENCH-CORR-010 | P1 | Medium | implemented | Efficiency remains separately reported and is not hidden in quality points | — |
| BENCH-OPS-001 | P0 | High | implemented; real-host verification pending | Paired arms run visibly in exactly two new panes in the invoking tmux window | benchmark lifecycle |
| BENCH-OPS-002 | P0 | High | implemented; real-host verification pending | Provider output streams interactively while bounded evidence is retained | BENCH-OPS-001 |
| BENCH-OPS-003 | P0 | High | implemented; real-host verification pending | Live applications persist for capture and blinded human scoring until explicit cleanup | BENCH-OPS-001 |
| BENCH-FAST-001 | P1 | Medium | implemented; provider timing pending | Compact one-phase suite has a 150-second model limit and paired synthetic calibration | BENCH-CORR-007 |
| BENCH-CORR-GATE | P0 | Critical | partially verified | Deterministic/source/package gates pass; independent real-host and publication review remain | all rows above |

---

## Implementation evidence and remaining gates

Implementation evidence is recorded in:

- [`COMPARATIVE_BENCHMARK_IMPLEMENTATION.md`](COMPARATIVE_BENCHMARK_IMPLEMENTATION.md) for the authoritative command, evidence, scoring, pane, and live-review behavior;
- [`BENCHMARK_ENHANCEMENTS_CHECKPOINT_04_VALIDATION.md`](BENCHMARK_ENHANCEMENTS_CHECKPOINT_04_VALIDATION.md) through [`BENCHMARK_ENHANCEMENTS_CHECKPOINT_07_VALIDATION.md`](BENCHMARK_ENHANCEMENTS_CHECKPOINT_07_VALIDATION.md) for focused acceptance, release, installer, and compact-suite timing evidence;
- `tests/invariants/test_comparative_benchmark_contracts.py`, `tests/invariants/test_comparative_benchmark_operating_policy.py`, and `tests/acceptance/test_comparative_benchmark_journey.py` for executable contracts.

The following gates remain intentionally open and must not be described as locally verified:

1. an authenticated Codex/Claude subscription run on a real tmux host;
2. confirmation that exactly two panes are added to the invoking window and remain observable through completion;
3. Playwright/Chromium capture against both preserved live applications;
4. blinded multi-reviewer human scoring and adjudication on the preserved URLs;
5. independent acceptance for publication claims, including a content-addressed browser runtime and verified font manifest.

Development and internal deterministic use are supported by the implemented contracts. Publication use remains blocked until the five gates above are independently evidenced.

---

## BENCH-CORR-001 — Freeze the corrected scoring contract

**Priority:** P0
**Risk:** Critical
**State:** Implemented

### Problem

The current requirement matrix is not arithmetically self-consistent, and the evaluator equal-weights checks rather than implementing requirement-level weights. Existing scores are interpretable only by reading the code.

### Required work

- Inventory the 0.7.9 owners listed above, including the split CLI handler, built-in benchmarking modules, source suite, installed asset mirror, schemas, focused tests, release audit, documentation, and man page.
- Define one machine-readable scoring contract containing:
  - dimension IDs and maximums;
  - check IDs;
  - exact per-check weights;
  - partial-credit rules;
  - evidence source for every check;
  - eligibility-versus-score classification;
  - human-review dimensions and formula;
  - component floors and composite formula;
  - winner-policy inputs;
  - benchmark and scorer version identifiers.
- Resolve the missing two hidden-functional points and the accessibility over-allocation in the existing matrix.
- Resolve whether public-test success receives duplicate engineering credit.
- State whether public tests remain all-or-nothing or become individually scored.
- Freeze the corrected contract under a new major benchmark version and resolve the existing `benchmark-spec.json` version `1.1.0` versus matrix version `1.0.0` mismatch without rewriting historical evidence.
- Preserve the current version and its evaluator without semantic modification.

### Acceptance evidence

- A validator proves every machine dimension sums to its declared maximum and all dimensions sum to 100.
- Every check ID is unique and maps to one evidence producer.
- No requirement is accidentally scored twice unless the contract explicitly names and justifies the duplicate signal.
- A compatibility test proves an existing v1 report still renders with v1 semantics.
- The new version cannot be compared directly with v1 without an explicit cross-version warning.

### Stop conditions

Stop if the proposed correction edits v1 scores in place, changes old report interpretation, or leaves any unallocated or multiply allocated points unexplained.

---

## BENCH-CORR-002 — Implement explicit weighted scoring

**Priority:** P0
**Risk:** Critical
**State:** Implemented

### Problem

The current generic outcome calculation assigns equal value to every check in a dimension. It cannot represent the intended requirement importance.

### Required work

- Replace equal-share calculation for the corrected benchmark version in the source-suite evaluator and built-in scoring service with explicit check weights from the authoritative contract; preserve the existing v1 evaluator asset unchanged.
- Support deterministic states such as pass, fail, partial, not-applicable, and harness-failure only where the contract defines them.
- Fail closed when:
  - a required check is missing;
  - a result includes an unknown check;
  - weights do not match the contract;
  - earned points exceed allowed points;
  - a scorer result omits required evidence.
- Include each check's maximum, earned points, state, evidence reference, and explanation in the score receipt.
- Keep scorer harness failure separate from a solution failure.
- Preserve eligibility invalidation independently from numerical quality points.

### Acceptance evidence

- Unit/invariant tests for exact weight arithmetic and rounding.
- Installed-product journey using `benchmark suite-export` to score a known fixture from the packaged mirror.
- Negative tests for duplicate, missing, unknown, and over-awarded checks.
- v1 equal-share behavior remains available only through the v1 scorer.

---

## BENCH-CORR-003 — Expand hidden functional and validation evaluation

**Priority:** P0
**Risk:** High
**State:** Implemented and BENCH-CORR-002

### Required coverage

Add explicit checks for the corrected version covering at least:

- exact formula with integer and decimal inputs;
- effort-floor behavior;
- four-place rounding boundaries;
- all tie-break levels: score, urgency, impact, then ID;
- attached score and rank schema;
- all required fields;
- missing, empty, wrong-type, non-finite, below-range, and above-range numeric values;
- boolean rejection for every numeric field;
- all allowed and disallowed status values;
- duplicate and empty IDs;
- useful validation error identity/message contract without brittle prose matching;
- empty input;
- deterministic repeated ranking;
- no unexpected mutation of inputs;
- title/description search and case handling;
- status and risk filters individually and in combination;
- supported sort keys and directions;
- invalid sort key/direction behavior;
- export ordering, rank, score, schema, destination handling, and deterministic JSON;
- fixture loading and malformed-file behavior;
- 1,000-item performance under the sealed host/runtime policy.

### Acceptance evidence

- Every requirement is traceable to one or more weighted check IDs.
- Controlled mutations demonstrate that each failure changes only the expected points.
- Evaluation failures are recorded as solution failures; evaluator crashes remain harness failures.
- Hidden oracle files are inaccessible to both benchmark arms.

---

## BENCH-CORR-004 — Expand deterministic browser and accessibility evaluation

**Priority:** P0
**Risk:** High
**State:** Implemented and BENCH-CORR-002

### Required coverage

For the corrected benchmark version, add deterministic browser journeys for:

- application load and expected item count;
- search behavior;
- status filtering;
- risk filtering;
- supported sorting;
- combined-control behavior;
- item detail by pointer and keyboard;
- selected-state communication;
- export download occurrence, filename policy, JSON parseability, ordering, and current-filter/sort semantics;
- empty result state;
- invalid-data state;
- visible persistent labels and accessible names;
- one main landmark and coherent heading structure;
- keyboard reachability and logical focus order;
- actual visible focus indication, not merely focused DOM state;
- no keyboard trap;
- viewport overflow and task completion at desktop, tablet, and mobile;
- no console/page errors;
- reduced-motion and deterministic runtime settings;
- an automated accessibility scan or a narrowly justified equivalent contract.

### Acceptance evidence

- Browser assertions produce structured evidence with stable check IDs.
- Screenshots and DOM snapshots are captured for every frozen state and viewport required by the contract.
- Download evidence is content-verified, not inferred from button text.
- A deliberately broken fixture fails each intended browser check.
- Publication-mode runtime attestation remains separate from UI quality points.

---

## BENCH-CORR-005 — Resolve public regression and duplicate-credit semantics

**Priority:** P1
**Risk:** High
**State:** Implemented and BENCH-CORR-002

### Required decision

Choose and document one of these policies:

1. **Granular public scoring:** each public requirement has an explicit weight; or
2. **Gate scoring:** the public suite remains a single all-or-nothing 15-point signal.

Also decide whether public-suite success remains an engineering-quality check. If retained, explain that it measures a distinct engineering behavior rather than correctness already counted elsewhere. Otherwise, replace it with a non-duplicative engineering signal.

### Acceptance evidence

- The scoring contract and generated documentation state the chosen semantics exactly.
- A one-test public failure produces the documented point change.
- No accidental double-credit remains.

---

## BENCH-CORR-006 — Harden human visual-review reliability

**Priority:** P1
**Risk:** High
**State:** Implemented

### Required work

- Preserve treatment blinding and audit evidence for possible label/path leaks.
- Add reviewer calibration examples for ratings 1 through 5.
- Define blocking-defect criteria and an adjudication path when reviewers disagree.
- Record and report inter-rater agreement for internal and publication cohorts.
- Define handling for missing, invalid, duplicate, late, or withdrawn reviews.
- Keep reviewer preference/confidence descriptive unless a future contract explicitly scores them.
- Confirm reviewer active time is measured consistently and not mixed into agent execution time.

### Acceptance evidence

- A blind-leak test proves reviewer bundles do not expose treatment identity.
- Multiple reviewer submissions aggregate deterministically.
- Conflicting blocking defects follow the documented adjudication rule.
- Review immutability and authenticated reviewer identity requirements are enforced at the appropriate claim level.

---

## BENCH-CORR-007 — Add scorer calibration and mutation acceptance

**Priority:** P0
**Risk:** Critical
**State:** Implemented

### Required work

Create deterministic calibration fixtures including:

- a complete known-good solution expected to earn full machine points;
- a minimally functional solution with a frozen expected score;
- one mutation per weighted requirement/check;
- guardrail-invalid cases that must produce `machine_score = null`;
- scorer-harness-failure cases distinct from solution failure;
- visual fixtures representing rating anchors and blocking defects.

### Acceptance evidence

- Every weighted check has at least one mutation that causes only the intended score delta.
- Repeated calibration runs are byte-stable except for explicitly volatile timestamps/paths.
- Source-tree and installed-package execution produce identical scoring results.
- The full corrected machine score sums exactly to 100 for the known-good solution.

---

## BENCH-CORR-008 — Establish a single source of scoring truth

**Priority:** P1
**Risk:** High
**State:** Implemented and BENCH-CORR-002

### Required work

- Keep authority-bearing run planning, process execution, evidence sealing, review submission, and comparison in the built-in `agent_workflow.benchmarking` feature.
- Do not add benchmark hooks to `agent_workflow.plugin_api` or `agent_workflow.plugins` unless a separately approved plugin-API decision establishes a general need.
- Make the machine-readable scoring contract authoritative.
- Generate or validate from it:
  - the requirement-to-evaluation matrix;
  - machine scoring tables;
  - human rubric summary;
  - benchmark documentation;
  - man-page benchmark section;
  - schema enums/check IDs where practical;
  - packaged/exported benchmark assets.
- Extend `scripts/audit-release-assets.py` so the repository suite and packaged asset mirror cannot drift, including the new scoring contract and generated derivatives.
- Prevent stale manual point tables from passing release validation.

### Acceptance evidence

- Deliberately changing one weight causes generated-doc or drift validation to fail until synchronized.
- The wheel/exported suite contains digest-identical contract and evaluator assets to `benchmarks/specs/priority-picker-v2/` (or the accepted corrected-version directory).
- Documentation names the benchmark/scorer version that it explains.

---

## BENCH-CORR-009 — Preserve historical comparability and define migration

**Priority:** P1
**Risk:** High
**State:** Implemented, BENCH-CORR-007, and BENCH-CORR-008

### Required work

- Keep v1 reports renderable and verifiable.
- Prevent v1 and corrected-version cohorts from being combined in one winner calculation.
- Add explicit cross-version warnings in reports and comparison commands.
- Define whether old worktree outputs may be rescored under the corrected version; if allowed, label them as rescored and never replace original receipts.
- Document benchmark version, scorer version, contract digest, evaluator digest, fixture digest, visual-runtime digest, and policy digest in each corrected run.

### Acceptance evidence

- Comparison rejects mixed-version cohorts by default.
- Original v1 receipts remain unchanged.
- Optional rescore output is additive, lineage-linked, and clearly distinguished from original execution evidence.

---

## BENCH-CORR-010 — Decide efficiency treatment

**Priority:** P1
**Risk:** Medium
**State:** Implemented

### Decision required

Choose one of these policies for the corrected benchmark:

- keep time, tokens, and cost descriptive only;
- add non-inferiority limits for efficiency regressions;
- add a separate value/efficiency verdict without changing the quality composite;
- create a declared multi-objective decision rule.

Do not hide efficiency inside the 100-point quality score unless the benchmark's purpose is formally changed.

### Acceptance evidence

- The winner rule states exactly how quality and efficiency interact.
- Missing provider-billed cost does not become zero.
- Subscription allocations, API-equivalent estimates, and provider-billed costs remain separate.
- Timing definitions distinguish critical-path wall time from summed process time.

---

## BENCH-CORR-GATE — Independent acceptance of corrected benchmark

**Priority:** P0
**Risk:** Critical
**State:** Partially verified; independent real-host/publication acceptance remains

### Required review

An independent reviewer must verify:

- exact 100-point arithmetic;
- requirement-to-check traceability;
- v1 immutability and version separation;
- golden and mutation calibration;
- browser and human-review evidence integrity;
- source/package asset equality;
- mixed-version comparison rejection;
- eligibility invalidation behavior;
- installed-product benchmark export/calibration journey through the public 0.7.9 CLI and `agent_workflow.cli_handlers.benchmark` dispatch boundary;
- documentation and man-page agreement with the authoritative contract.

### Exit evidence

- focused correction suites pass;
- installed-package benchmark export and calibration pass;
- release/drift audit passes;
- prompt pack validates;
- independent gate report explicitly accepts or rejects the corrected benchmark for development, internal, and publication use.

---

## Recommended phase sequence

| Phase | Work | Parallelism |
|---|---|---|
| 0 | BENCH-CORR-001 and BENCH-CORR-010 | May run in parallel; contract must settle before implementation |
| 1 | BENCH-CORR-002, then BENCH-CORR-003/004/005 | Functional, browser, and public scoring may run in parallel after weighted engine lands |
| 2 | BENCH-CORR-006, BENCH-CORR-007, BENCH-CORR-008 | Human review and docs can proceed in parallel; calibration depends on scorer work |
| 3 | BENCH-CORR-009 and BENCH-CORR-GATE | Migration first, then independent acceptance |
