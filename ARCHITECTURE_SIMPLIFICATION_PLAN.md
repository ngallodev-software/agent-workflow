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

The normal worker command catalog no longer advertises manual
`completion-validate` or `task-complete` flows. Those remain compatibility
surfaces for older/external integrations.

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

## Next simplification candidates

These should be separate changes after the worker protocol proves stable:

1. **Review/acceptance operation table** — encode review disposition transitions
   and prerequisites as declarative operation specifications rather than
   duplicating condition trees across approval paths.
2. **Prerequisite policy table** — represent `accepted`, `sealed_completed`, and
   future dependency requirements as named policies with fixed evidence gates.
3. **Finalization operation pipeline** — express collect -> evaluate -> status ->
   seal -> projection as an explicit ordered pipeline whose steps are reusable
   by normal and recovery finalization.
4. **Assignment state transitions** — move assignment `busy -> closed` semantics
   to a small transition table parallel to execution lifecycle.
5. **Generated command/schema bindings** — add machine-readable criterion IDs to
   prompt-pack manifests/native jobs. Once available, `agent criterion` can
   reject unknown criterion IDs instead of validating only the result enum.
6. **Deprecate manual completion JSON** — after one compatibility window, remove
   manual worker authorship entirely and reserve sidecar writing to the
   deterministic builder.

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
