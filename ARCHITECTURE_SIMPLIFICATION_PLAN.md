# Agent-Workflow deterministic protocol simplification

## Design objective

Agent-Workflow should treat language-model workers as sources of bounded semantic
judgment, not as protocol engines. Administrative state, lifecycle sequencing,
identity, Git facts, process facts, enum values, schema construction, and sealing
belong to deterministic code.

The governing rule is:

> If getting a value or ordering wrong can invalidate a run, the worker should
> invoke an operation that constructs or transitions it rather than write the
> protocol value itself.

## Target model

```text
request
  -> planner/supervisor
  -> deterministic launch operation
  -> isolated worker
       -> criterion(result, evidence)
       -> verify(argv)
       -> complete(result, review disposition, unresolved)
  -> deterministic collection
  -> deterministic finalization
  -> deterministic seal
  -> review operation
  -> acceptance operation
```

Workers provide semantic inputs only. Every administrative operation validates
its finite choices before state is written and performs one fixed ordered series
of actions.

## What should be deterministic

- Agent Run, ticket, pack, role, retry and prerequisite identity.
- Allowed lifecycle transitions.
- Allowed completion/result/review/acknowledgement values.
- Git base and HEAD revisions and changed-file inventory.
- Verification command argv, cwd and observed exit status.
- Source-drift authorization inherited from the launch contract.
- Completion JSON construction and schema validation.
- Completion collection and canonicalization.
- Process finalization and evidence sealing.
- Review and acceptance lifecycle mutation.
- Recovery/restart lineage.

## What may remain semantic

- Whether a criterion is satisfied.
- Evidence text explaining why a criterion is satisfied or not verified.
- Review findings and review disposition.
- Planner decisions that genuinely require model judgment.
- Ticket-specific result artifacts whose schema is owned by the prompt pack.

Semantic values still enter Agent-Workflow only through constrained operations;
they do not directly mutate administrative JSON.

## Implemented in this overlay

### 1. Deterministic worker completion API

Normal implementation/review workers now use:

```bash
agent criterion RUN CRITERION pass --evidence "..."
agent verify RUN -- <command> <args...>
agent complete RUN --result completed
agent completion-status RUN
```

Reviewers may additionally provide the finite `--review-disposition` choice.

Agent-Workflow 0.11 removes the legacy worker-facing `completion-validate`
and `task-complete` commands entirely. Generated completion evidence is now
the only worker terminal protocol surface.

### 2. Agent-Workflow-generated completion JSON

`agent complete` derives rather than accepts:

- `agent_run_id`
- `ticket_id`
- `pack_id`
- `base_revision`
- `head_revision`
- `changed_files`
- repository-closeout digest binding
- canonical schema shape

The worker supplies only the constrained completion result, optional review
disposition, unresolved semantic findings, previously recorded criterion
judgments, and verification intents.

### 3. Observed verification receipts

`agent verify` executes the command through Agent-Workflow's bounded process
layer. Exit code and argv are observed by code rather than reported by the
model. Re-running the same argv/cwd replaces the final completion receipt,
allowing a corrected verification run to supersede a prior failed final check.

### 4. Single-source finite protocol values

Completion results, criterion results, review dispositions and acknowledgement
outcomes have an authoritative Python vocabulary. CLI choices and deterministic
builders consume those values instead of scattering string literals across
worker-facing code.

### 5. Schema-governed mutable draft

The worker completion draft has its own JSON Schema. The draft is written only
by Agent-Workflow operations and is validated on every update. The final
`completion.json` continues to use the existing immutable completion schema.

### 6. Prior 0.10.2 runtime corrections retained

This overlay is cumulative with the previous 0.10.2 runtime overlay, including
pack/job normalization, model/role handling, retry preparation, linked-worktree
Git metadata access, review prerequisite behavior, finalization convergence and
dirty-baseline context.

## Existing design that is already aligned

`run_lifecycle.py` already uses an explicit transition table for execution
state and rejects illegal state transitions. That is the right pattern and
should be preserved rather than replaced with more branching.

The schema registry and immutable receipt verification are also aligned with
this direction: schemas remain the persisted contract while operations become
the only normal mutation path.

## Implemented in the continuation overlay

- **Review/acceptance operation table** — review, accept, and reject now resolve through named operation specs; acceptance revision is derived from sealed completion evidence rather than copied in by the operator.
- **Prerequisite policy table** — dependency requirements resolve through the closed `accepted` / `sealed_completed` policy set.
- **Assignment transition executor** — busy-to-closed completion uses one fixed transition function for direct and bridged paths.
- **Repository-local execution overlay discovery** — exact launch roots may provide `.agent-workflow-execution.toml`; only execution identity sections are accepted and host policy remains authoritative.
- **Non-gating environment limitations** — reviewers can persist sandbox/network/browser/listener constraints separately from acceptance criteria and bind host receipts by SHA-256.
- **Out-of-tree handoff storage** — new run protocol artifacts live under run state, eliminating Docker/build-context contamination while retaining read compatibility for legacy handoffs.

## Implemented in the final simplification slice

- **Shared terminal finalization pipeline** — normal runner completion and recovery now use one ordered executor for completion/task collection, post-run scope/command collection, provider evidence, budget policy, terminal outcome derivation, provenance, final status, sealing, projection, and evaluation artifacts. Exit-0 plus invalid/missing completion is deterministically failed in both paths.
- **Machine-readable criterion catalogs** — prompt-pack v1 tasks and native jobs may declare `criteria: [{id, description}]`. The catalog is validated for duplicate IDs, frozen into the immutable Agent Run contract, surfaced in the launch prompt/status, enforced by `agent criterion`, and required in full by `agent complete`. Newly scaffolded v1 packs emit IDs for their baseline acceptance criteria.
- **Out-of-tree handoff follow-through** — external delegation responses now derive the handoff directory from the immutable launch contract instead of reconstructing the retired worktree-local path; native-job disposable scope no longer authorizes an unused `.agent-workflow-handoff/` tree.

## Remaining compatibility retirement

Agent-Workflow 0.11 retires the worker-facing manual `completion.json`, `completion-validate`, and `task-complete` compatibility surfaces. Internal collection and external-host reconciliation still consume generated completion evidence, but workers no longer have a second protocol-authoring path.

## Non-goals

- Do not let workers call `seal`; sealing remains runner/host authority.
- Do not expose host credentials to workers to make external mutations easier.
- Do not weaken schema validation or dirty-source policy.
- Do not turn task-domain judgment into brittle deterministic heuristics.

## Success criteria

The architecture is moving in the intended direction when an invalid enum,
stale revision, invented exit code, skipped lifecycle phase, or premature seal
cannot be expressed through the normal worker interface. The remaining worker
errors should increasingly be semantic mistakes in the work itself, not mistakes
in Agent-Workflow's administrative protocol.
## 0.11 closeout

The 0.11 boundary completes the compatibility retirement and failure-diagnostic
work that was intentionally deferred from 0.10.2:

- legacy worker-facing `completion-validate` and `task-complete` commands are removed;
- child control intents are reduced to `progress` and `ack`; terminal assignment closure
  is performed by the shared host-owned terminal pipeline after valid completion evidence
  is collected;
- unexpected CLI exceptions are persisted as `agent-workflow/unexpected-failure/v1`
  diagnostics under the local state root. The terminal receives the correlation ID and
  diagnostic path, while the local record contains bounded/redacted argv, exception
  type/message/chain, traceback paths/lines/functions, and safe subprocess/OSError details;
- the stale comparative-eval adoption test is aligned to the current dependency-neutral
  runtime API instead of restoring retired TypeSafe compatibility shims.
