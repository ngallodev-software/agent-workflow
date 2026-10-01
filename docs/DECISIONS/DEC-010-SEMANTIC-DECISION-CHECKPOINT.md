# DEC-010 — Provider-neutral semantic decision checkpoint and reconciliation gate

- **Status:** proposed / prototype approved for mechanism development
- **Date:** 2026-10-01
- **Scope:** consequential bounded semantic decisions made during Agent-Workflow execution
- **First seam:** `implementation.proposal_selection/v1`
- **Related backlog:** `TYPE-001`

## Context

The Agentic-Jev manager pilot exposed a structural failure mode rather than a transport failure. An agent-facing Jev decision skill could activate on synthetic fixtures, including Choice and Noul/Score use, but the six frozen real manager tasks made zero Jev calls. A later exploratory comparison against public SWE-Lancer proposal labels found three of the six selections matched the public gold proposal and three did not. The known six cases are therefore useful mechanism/replay cases, not an effectiveness cohort.

The working hypothesis is a self-gating bootstrap problem: the same coding agent whose semantic judgment may be overconfident decides whether independent semantic evidence is needed. Making a skill progressively more eager does not remove that structural dependency.

The current Agent-Workflow architecture already has the correct authority boundary:

- immutable workflow snapshots plus append-only workflow events are canonical workflow evidence;
- Agent Run execution journals and sealed receipts are canonical execution evidence;
- review and acceptance are separate deterministic/evidence gates;
- TypeSafe/Jev is a bounded semantic-evidence provider, not lifecycle authority;
- SQLite and other projections remain rebuildable rather than authoritative.

The current Jev decision-support source adds an additional constraint relevant here: neutral provider context should exclude the coding agent's preferred answer and confidence, classify other-agent notes as claims rather than deterministic tool output, and exclude prior Jev answers by default. Candidate artifacts remain necessary when they are the objects being judged, but the selecting agent's tentative conclusion must not contaminate the independent provider projection.

## Decision

Agent-Workflow will prototype a **provider-neutral semantic checkpoint** owned by Agent-Workflow rather than a Jev-specific agent harness.

For `implementation.proposal_selection/v1`, the intended execution shape is:

```text
investigation-only Agent Run
        |
        v
DecisionDraft
  - finite candidate IDs
  - initial agent choice
  - evidence references
        |
        v
Agent-Workflow semantic checkpoint
  - validates draft
  - independently projects neutral primary evidence
  - excludes the initial agent choice from provider context
  - invokes configured semantic provider
        |
        v
SemanticEvidence
        |
        v
Agent-Workflow reconciliation policy
        |
        +-- agreement ----------> DecisionResolution -> continue
        |
        +-- disagreement -------> mandatory reconciliation
        |
        +-- uncertainty --------> more evidence / independent review / human
        |
        +-- provider failure ---> explicit application-owned fallback or block
        |
        v
semantic-checkpoint-receipt
  - applied result
  - advance_allowed
  - evidence hashes/refs
        |
        v
implementation Agent Run may start only when advance_allowed == true
```

The key invariant is:

> An agent may disagree with semantic evidence, but it may not silently discard a registered disagreement.

Jev does not become authoritative. Agent-Workflow decides whether a disposition is permitted and whether the required evidence exists before downstream work is allowed to advance.

## First prototype contract

The first branch introduces mechanism-level contracts and a pure checkpoint engine without registering a new production decision or workflow node yet.

### DecisionDraft

`agent-workflow/decision-draft/v1` records:

- `draft_id`;
- exact decision identity `implementation.proposal_selection/v1`;
- 2–16 bounded candidate IDs;
- the agent's tentative selection;
- stable evidence references.

The initial choice is reconciliation evidence. It is **not** semantic-provider input.

### Neutral projection

The prototype projector accepts only:

- verbatim requirement text plus a stable source reference;
- candidate artifacts and their source references;
- scoped deterministic evidence such as tests, type checks, or lint results;
- fixed application metadata declaring the semantic provider evidence-only.

It does not accept an agent verdict, confidence, preferred candidate, rationale, prior Jev answer, or unlabelled other-agent conclusion. The projected state is bounded to 64 KiB and hashed with fixed serialization. Candidate order is the DecisionDraft order and therefore becomes part of the request identity.

### SemanticEvidence

The provider returns the existing provider-neutral `DecisionEvidence` shape. The first seam requires Choice evidence whose selected value is one of the bounded candidate IDs. The complete returned distribution is retained.

Confidence and probability are evidence, not correctness. A configured minimum confidence and minimum top-two margin determine whether the checkpoint has enough semantic separation to call the result agreement/disagreement. A close distribution is `uncertainty`, not a strong decision.

### Reconciliation

`agent-workflow/decision-resolution/v1` makes disagreement handling explicit.

Permitted successful dispositions are:

- retain the initial choice on semantic agreement;
- accept the semantic candidate explicitly;
- reject the semantic candidate only with deterministic authority, additional evidence, independent review, or human authority plus evidence references;
- use the initial choice on provider failure only when an application-owned provider-failure policy explicitly permits that fallback.

`defer_for_evidence` and `escalate_review` remain non-advancing dispositions.

An unsupported provider value, wrong primitive, low-confidence/close distribution, or provider failure cannot be converted into an advancing choice merely because one label has the highest decimal probability.

### Receipt

`agent-workflow/semantic-checkpoint-receipt/v1` records at minimum:

- draft and projected-state digests;
- request identity and projector/question-set versions;
- initial agent choice;
- normalized semantic candidate and complete typed distribution;
- agreement/disagreement/uncertainty/provider-failure classification;
- structured resolution when present;
- applied result;
- `advance_allowed`;
- provider failure policy;
- source refs, model/request identity, usage, and error class where supplied.

The receipt contains observable decision evidence only. It does not claim access to hidden chain-of-thought.

## Structural workflow integration — next phase, not this prototype

The durable production seam should be an **outer Agent-Workflow workflow gate**, not an instruction inside a single coding-agent turn.

The target workflow shape is:

```text
investigation task -> semantic checkpoint gate -> implementation task -> existing review/acceptance gates
```

The investigation task must be unable to make implementation side effects outside its authorized scope. Its structured result supplies the DecisionDraft and evidence refs. The checkpoint gate produces an immutable decision receipt. The implementation task depends on checkpoint completion and receives only the resolved candidate plus explicitly bound evidence.

This phase requires a separately reviewed extension to workflow node semantics and restart/idempotency rules. In particular, the provider call and receipt installation must be crash-safe so replay cannot create ambiguous double decisions. Until that proof exists, the prototype does **not** add a new live workflow node kind.

## LangGraph decision

Do **not** add LangGraph as a core dependency for the first checkpoint seam.

LangGraph is technically capable of the desired conditional edges, checkpoints, and pause/resume behavior. Its current persistence model stores graph-state checkpoints per thread, and `interrupt()` persists graph state and resumes with a thread ID. Current interrupt semantics also restart the interrupted node from its beginning, so effects before the interrupt must be replay-safe.

Those mechanics substantially overlap with authority Agent-Workflow already owns: immutable workflow snapshots, append-only event journals, restart-safe scheduler reconciliation, Agent Run lifecycle state, and separate review/acceptance evidence. Adding a LangGraph checkpointer now would either duplicate durable state or require treating LangGraph persistence as non-authoritative execution convenience while Agent-Workflow remains canonical. The first seam does not remove enough custom orchestration to justify that second layer.

Reconsider LangGraph only if a later requirement specifically needs an **inner, single-agent execution graph** with conditional loops/interrupts that cannot be represented cleanly as Agent-Workflow task/gate boundaries. If adopted later:

1. Agent-Workflow snapshots/events/receipts remain canonical;
2. LangGraph `thread_id` must bind to an Agent-Workflow run/checkpoint identity;
3. LangGraph checkpoints are disposable/reconstructable execution state, never acceptance or decision authority;
4. side effects before an interrupt must be idempotent because interrupted nodes restart on resume;
5. no decision may exist only in LangGraph state.

References:

- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts

## Temporal decision

Do **not** add Temporal for this seam.

Temporal is a durable-execution platform built around a service, durable Event History, workers, workflow replay, and deterministic workflow-code constraints. That is valuable when the product requires distributed, multi-host, long-lived crash-resilient workflow infrastructure. Agent-Workflow already owns a local-first event/journal/scheduler authority model. Layering Temporal over it now would duplicate the core durability model rather than merely filling the semantic-checkpoint gap.

Reconsider Temporal only if Agent-Workflow intentionally moves toward distributed workflow authority and is prepared to migrate, rather than duplicate, the current scheduler/event-history responsibilities.

References:

- Temporal overview: https://docs.temporal.io/temporal
- Temporal Workflow Tasks and replay: https://docs.temporal.io/tasks

## Receipt-v2 prerequisite found during inspection

The current `decisions.py` emits `agent-workflow/decision-execution-receipt/v2`, while the repository currently ships only the older `agent-workflow/decision-execution-receipt/v1` schema. The v1 schema also names fields that no longer match the emitted receipt.

This is contract drift and should be corrected before expanding decision semantics. The checkpoint prototype branch therefore adds a v2 schema matching the current runtime receipt and validates newly emitted runtime receipts against it while preserving the v1 schema for historical compatibility.

This prerequisite is independent of Jev effectiveness. It is a contract-integrity fix discovered while tracing the existing decision boundary.

## Repository ownership

No ownership boundary changes:

- **Agent-Workflow:** DecisionDraft/DecisionResolution/checkpoint receipt semantics, state projection, provider invocation boundary, fallback/reconciliation policy, lifecycle gate, deterministic application.
- **agent-workflow-comparative-eval:** provider-neutral observation contracts, pair identity, statistics, metrics, report semantics.
- **agent-workflow-benchmark:** experiment execution, frozen cohorts, scoring, sealing, collection, publication preparation.
- **agent-workflow-benchmark-results:** sanitized public evidence only.
- **Jev/TypeSafe:** semantic evidence provider only.

## Mechanism-development sequence

### Phase 0 — contract integrity

- ship and validate `decision-execution-receipt/v2` against current runtime output;
- retain v1 schema compatibility.

### Phase 1 — provider-neutral checkpoint core

- ship DecisionDraft, DecisionResolution, and checkpoint-receipt schemas;
- ship pure `implementation.proposal_selection/v1` projection/reconciliation mechanics;
- prove that initial agent preference is absent from provider state;
- prove disagreement blocks without reconciliation;
- prove split distributions remain uncertainty;
- prove provider failure is fail-closed unless explicit policy permits fallback.

### Phase 2 — structural workflow gate

- specify/version a workflow checkpoint node or equivalent host-owned gate;
- make provider invocation and receipt installation restart-safe/idempotent;
- bind resolved choice into a downstream implementation task;
- prohibit downstream launch while a registered checkpoint is unresolved;
- preserve existing review/acceptance authority.

### Phase 3 — mechanism replay

Use the six known SWE-Lancer manager tasks only to test whether the structural checkpoint activates and records complete evidence. Their known proposal labels must not be used to tune thresholds, question wording, projection, or policy for a future effectiveness claim.

### Phase 4 — preregistered effectiveness cohort

Freeze a new disjoint manager cohort and specify scoring/pairing/exclusions before outcomes are observed. Run paired control/checkpoint treatments with identical source/candidate evidence where applicable.

### Phase 5 — promotion decision

Only after representative evidence exists should `implementation.proposal_selection/v1` be considered for a registered production seam. Promotion must satisfy the existing `TYPE-001` criteria and preserve deterministic lifecycle/acceptance authority.

## Evidence and metrics for the future experiment

| Measure | Question answered | Required data / origin | Captured now? | Independent oracle? | Public reporting |
| --- | --- | --- | --- | --- | --- |
| checkpoint activation rate | Did the structural seam actually invoke semantic evidence? | checkpoint receipts / Agent-Workflow | prototype yes; production no | no | count + rate |
| agreement/disagreement/uncertainty rate | How often did independent semantic evidence differ or split? | initial choice + typed distribution + checkpoint outcome | prototype yes | no | counts/rates with CIs where meaningful |
| reconciliation disposition | What happened after disagreement? | DecisionResolution | prototype yes | no | disposition counts; no hidden reasoning |
| final decision accuracy | Did the applied proposal match independent ground truth? | applied result + frozen gold/oracle | no new cohort yet | **yes** | paired accuracy/delta with exact cohort identity |
| disagreement recovery | When initial choice was wrong, did the checkpoint lead to a correct final choice? | initial/final choices + oracle | no new cohort yet | **yes** | exploratory unless preregistered; paired counts |
| semantic false diversion | When initial choice was correct, did checkpoint move it wrong? | initial/final choices + oracle | no new cohort yet | **yes** | paired count/rate |
| provider latency | What wall-time overhead did semantic evidence add? | provider call timing / receipt | routing captures analogous data; checkpoint future | no | median/distribution with n |
| token overhead | What provider token cost did the checkpoint add? | provider usage | routing captures when provider reports it | no | aggregate + per-case; completeness flag |
| dollar cost | What monetary overhead did the checkpoint add? | provider billing evidence joined to request identity | not complete in current AW receipt | no | only when evidence complete |
| escalation rate | How often did policy require more evidence/reviewer/human? | DecisionResolution/checkpoint receipt | prototype yes | no | counts/rates |
| final task correctness | Did downstream implementation succeed, beyond proposal selection? | deterministic evaluation / independent task oracle | benchmark responsibility | **yes** for effectiveness | paired outcome with limitations |

Small mechanism cohorts must be reported as mechanism evidence, not generalized effectiveness. Semantic agreement is not correctness.

## Consequences

### Positive

- Removes optional self-gating at consequential registered seams.
- Preserves Jev as evidence rather than authority.
- Makes disagreement and fallback observable and auditable.
- Reuses Agent-Workflow's existing durable authority model instead of introducing a second canonical state store.
- Keeps provider substitution possible.
- Creates a clean experimental boundary for measuring both benefits and false diversions.

### Costs and risks

- Requires phase separation between investigation and implementation for strong enforcement.
- Adds one more explicit artifact family and later a workflow gate.
- Poor evidence projection can still produce confidently wrong semantic evidence.
- Provider distributions are context/serialization sensitive; request ordering and serialization must remain frozen within comparative runs.
- Structural checkpoints add latency and token/cost overhead that must be measured rather than assumed acceptable.

## Non-goals

This decision does not:

- make Jev authoritative;
- claim Jev improves correctness;
- promote `implementation.proposal_selection/v1` to production yet;
- rerun or mutate frozen v2/v3 experiments;
- treat the six known manager cases as a clean effectiveness cohort;
- add LangGraph or Temporal to Agent-Workflow;
- capture or require hidden chain-of-thought;
- replace deterministic tests, type checking, linting, review, or acceptance.
