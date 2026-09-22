# BM3 TypeSafe/Jev Optimization Audit

## Purpose

Round 2 showed substantial Agent-Workflow overhead relative to raw direct execution, but it did not include machine scoring. Before Benchmark Round 3, this audit identifies decision work that may be better served by bounded TypeSafe/Jev judgments while preserving deterministic Agent-Workflow authority.

The implementation pattern remains:

```text
StateProjector
  -> QuestionSetRegistry
  -> TypeSafe/Jev Choice | Noul | Score
  -> normalized DecisionReceipt
  -> application DecisionPolicy
  -> deterministic consumer
```

TypeSafe/Jev is not a replacement for lifecycle authority. It is a bounded semantic decision layer for messy context and finite alternatives.

## Round 2 evidence

Round 2 compared `raw-direct/v1` with `agent-workflow-full/v1` using one paired development repetition.

| Metric | raw-direct | Agent-Workflow | Candidate delta |
| --- | ---: | ---: | ---: |
| wall time | 471.606 s | 969.786 s | +105.6% / 2.06x |
| provider total tokens | 587,452 | 2,626,699 | +347.1% / 4.47x |
| uncached input tokens | 154,840 | 265,294 | +71.3% / 1.71x |
| output tokens | 22,500 | 43,837 | +94.8% / 1.95x |
| reasoning output tokens | 3,599 | 13,663 | +279.6% / 3.80x |

Phase wall-time deltas were:

- analyze/plan: +106.112 s;
- implement: +369.865 s;
- verify/repair: +22.203 s.

Round 2 was execution-only, so these numbers qualify overhead and telemetry only. They do not show whether the extra work improved correctness or quality.

## Optimization question

BM3 should distinguish three categories instead of treating all Agent-Workflow overhead as one cost:

1. **open-ended generation** — code changes, repairs, explanations, and synthesis that require a general-purpose coding model;
2. **bounded semantic decision work** — finite classification, ranking, escalation, evidence-selection, or path-selection decisions that may be suitable for Jev;
3. **deterministic host work** — source identity, schema validation, persistence, process facts, receipts, verification, lifecycle transitions, review gates, and acceptance authority.

The optimization target is category 2. Category 3 should remain deterministic. Category 1 should remain with the coding model unless evidence shows a smaller bounded decision can remove an unnecessary general-model pass.

## TypeSafe implementation rules

### StateProjector

Project only evidence that materially affects the semantic question.

A projected state should:

- be a named JSON object;
- preserve stable IDs and relevant relationships;
- separate observed evidence from policy facts;
- retain provenance/source references;
- redact irrelevant secrets;
- remain bounded in size;
- avoid embedding the deterministic answer during comparative evaluation;
- use canonical hashing for reproducibility.

Large context is not automatically better context. BM3's request/response audit is required specifically so projected state can be reviewed for missing, noisy, duplicated, or anchoring information.

### QuestionSetRegistry

Every semantic seam needs a versioned bounded question definition.

Use:

- **Choice** when exactly one item must be selected from a finite catalog;
- **Noul** for a single yes/no proposition expressed as `P(true)`;
- **Score** for an ordered consequence/intensity dimension.

Choice sets should include `other`, `none`, or `no_match` when the supplied alternatives may be incomplete. Selected values must be revalidated locally.

Noul probabilities near 0.5 represent uncertainty, not weak permission.

Score criteria must be behaviorally distinct and ordered. If ranking several items, score them consistently and sort deterministically in application code.

### DecisionPolicy

Thresholds are Agent-Workflow policy, not SDK semantics.

Policy owns:

- automation eligibility;
- thresholds;
- fallback;
- escalation;
- composition of multiple semantic results;
- calibration version.

Confidence is never correctness, authorization, or permission to mutate state.

### Decision receipts

A receipt should preserve enough information to reproduce and audit the decision:

- decision definition/version;
- projector version;
- question-set version;
- request hash;
- model/SDK identity;
- normalized semantic evidence;
- distribution/probability;
- policy version;
- policy candidate;
- applied result;
- source references;
- comparative control result when applicable.

The private TypeSafe API audit additionally preserves the redacted logical and HTTP request/response exchange.

## Current seams

The existing runtime seams are appropriate:

| Seam | Primitive | Current role |
| --- | --- | --- |
| `routing.task_class` | Choice | bounded task classification |
| `routing.interaction_required` | Noul | whether a material decision/authorization is missing |
| `routing.semantic_risk` | Score | consequence of a wrong semantic interpretation |

These should remain and be calibrated from representative cases.

## BM3 candidates for moving decision work out of the coding LLM

The following are candidates for comparative/shadow evaluation first. They are not automatically approved production seams.

### 1. Verification-path selection — high priority

Current workflow discipline asks the coding model to decide which verification activity is relevant and how broad it should be.

Candidate:

`verification.path` — Choice over a host-provided finite catalog such as:

- focused unit checks;
- integration checks;
- full suite;
- documentation/static checks;
- visual/accessibility checks;
- no additional check applicable;
- other/escalate.

The deterministic consumer owns the actual command catalog and execution. Jev chooses only among commands/actions already authorized by the host.

Potential benefit: avoid spending a general coding-model pass reasoning about a bounded test-selection problem.

### 2. Review-attention triage — high priority

Current review prompts ask a general model to inspect broad evidence and determine where to focus.

Candidate:

`review.attention` — Choice or per-dimension Score over bounded categories:

- requirement drift;
- scope drift;
- incomplete verification;
- provenance mismatch;
- risky semantic assumption;
- stale documentation;
- no material concern.

The result can prioritize deterministic checks and reviewer context. It cannot approve or accept a run.

Potential benefit: reduce broad repeated context review and focus expensive model review where uncertainty remains.

### 3. Evidence relevance / context selection — high priority

Agent-Workflow should not indiscriminately feed all available evidence into every model step.

Candidate:

`context.relevance` — Score or Choice over host-enumerated evidence bundles.

The application can rank bounded evidence items and deterministically construct the next context window from the top eligible items.

Potential benefit: reduce cached and uncached context growth while improving semantic signal density.

This is especially relevant because Round 2 input grew 4.57x while uncached input grew only 1.71x; repeated/cached context appears to be a material part of the current cost.

### 4. Failure/remediation classification — high priority

Observed process facts remain deterministic, but selecting the likely remediation class from messy stderr/evidence can be semantic.

Candidate:

`remediation.class` — Choice over:

- environment/infrastructure;
- dependency/configuration;
- source defect;
- verification mismatch;
- incomplete task interpretation;
- external authorization required;
- unknown/escalate.

The host still decides which remediation actions are legal and whether retry is permitted.

Potential benefit: remove general-model classification passes where the output is already a finite remediation taxonomy.

### 5. Planning-depth / strategy selection — medium priority

The general coding model currently performs substantial plan reasoning even when the host may only need to select a bounded planning strategy.

Candidate:

`planning.strategy` — Choice over:

- direct bounded edit;
- inspect-then-edit;
- diagnosis-first;
- test-first;
- documentation-only;
- multi-component implementation;
- escalate/other.

This should not generate the plan. It can decide how much open-ended planning is warranted before invoking the coding model.

Potential benefit: reduce analyze/plan cost, which was +106.1 s in Round 2.

### 6. Need-for-second-pass decision — medium/high priority

Before launching another expensive model pass, use bounded evidence to decide whether one is warranted.

Candidate:

`execution.additional_pass_required` — Noul.

State could include deterministic verification results, unresolved criteria, diff size/classification, and existing review findings.

A high-confidence false result may allow the host to skip an otherwise routine LLM self-review pass, subject to calibrated policy.

This does not bypass required deterministic verification or independent review gates.

### 7. Delegation/context role metadata — medium priority

When the user has not explicitly supplied a role, bounded semantic routing may choose among configured logical roles or evidence bundles.

It must not select a provider/model directly and must not override explicit role instructions.

## Work that should remain with the general-purpose coding model

Do not move these to Jev merely to reduce token count:

- source-code generation;
- nontrivial patch synthesis;
- debugging that requires forming a novel causal explanation;
- repair implementation;
- architectural design with an open output space;
- prose/document generation;
- unconstrained task decomposition.

A bounded semantic call may decide whether one of these operations is needed, but Jev should not be used as a code/spec generator.

## Deterministic authority that must remain outside TypeSafe

The following remain deterministic even if semantic advice helps select a path around them:

- leases and ownership;
- duplicate-execution prevention;
- source/revision identity;
- schema/path/permission validation;
- authorization;
- executor/process state;
- command exit status;
- lifecycle transitions;
- retry eligibility bookkeeping;
- evidence existence and persistence;
- cryptographic hashes;
- required verification;
- scoring arithmetic;
- review independence;
- acceptance/rejection authority;
- irreversible actions.

## BM3 observability requirements

BM3 introduces two complementary timing layers.

### Benchmark phase timing

Each phase should preserve:

- phase wall time;
- executor-active time;
- first-output latency;
- provider usage;
- direct-runner postprocessing;
- Agent-Workflow delegate-call time;
- Agent-Workflow terminal wait;
- benchmark evidence-copy time;
- derived host overhead.

### Agent-Workflow terminal timing

Each Agent Run should additionally preserve host-only section timing for:

- completion collection;
- assignment close;
- task-result collection;
- post-policy collection;
- patch capture;
- provider-evidence normalization;
- policy evaluation;
- provenance update;
- final-status write;
- execution-evidence generation;
- pre-seal total.

The combination is intended to answer:

- Is BM3 slow because the coding model itself spends longer under the Agent-Workflow prompt/context?
- Is host orchestration/finalization materially slow?
- Is repeated context responsible for token expansion?
- Are expensive general-model phases actually making bounded choices that Jev can perform faster?

## TypeSafe audit requirements for BM3

BM3 must not add TypeSafe routing work to only the Agent-Workflow treatment arm. The paired comparison pins executor/model/class for runtime comparability, so the current scheduler routing seam is qualified separately **before** paired execution. The benchmark runner exercises `advise_routing_with_policy()` on the three exported phase prompts, keeps deterministic control applied in comparative mode, records a separate semantic-qualification receipt, and requires zero additional TypeSafe calls during the paired treatment.

For each pre-treatment semantic qualification call, retain private redacted audit evidence for:

- exact projected state;
- exact Choice/Noul/Score question definitions;
- requested/resolved model;
- request hash;
- SDK version;
- raw HTTP request/response when exposed;
- normalized typed result;
- duration;
- status/error.

Review each call for:

1. missing context;
2. irrelevant/noisy context;
3. duplicate context;
4. deterministic-answer anchoring;
5. poorly bounded criteria;
6. wrong primitive choice;
7. policy threshold mismatch;
8. semantic disagreement with deterministic control.

The benchmark summary may publish counts, durations, disagreement rates, primitive coverage, and hashes. Raw semantic request/response bodies should remain private evidence.

## BM3 interpretation

BM3 compares:

```text
structured-direct/v1
vs
agent-workflow-full/v1
```

Both arms receive the same structured workflow prompt discipline. The treatment difference is the real Agent-Workflow lifecycle/orchestration/evidence machinery.

This is intentionally narrower than Round 2. It allows the study to distinguish:

- prompt-discipline cost;
- coding-model execution cost;
- host lifecycle cost;
- bounded semantic-decision cost measured outside the treatment;
- machine quality outcome.

A development run with one repetition remains descriptive. It is useful for diagnosis and qualification, not a generalized product-performance claim.

## Decision after BM3

Do not introduce new Jev production authority merely because a seam looks plausible.

Promote a candidate only when BM3/follow-up evidence shows:

1. the output is genuinely bounded;
2. the projected state is sufficient and stable;
3. TypeSafe is at least as reliable as the current decision path for that seam;
4. uncertainty is detectable and fallbacks work;
5. the call reduces general-model work, wall time, context, or retries enough to matter;
6. deterministic policy remains able to reject or ignore the result;
7. the semantic receipt is auditable and calibratable.

The objective is not to maximize TypeSafe calls. The objective is to use the cheapest reliable decision mechanism appropriate to each boundary.
