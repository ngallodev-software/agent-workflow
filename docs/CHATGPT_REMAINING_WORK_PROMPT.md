# Prompt: complete the remaining agent-workflow integration work

You are continuing implementation in the `agent-workflow` repository. Work
directly in the current checkout. Do not discard existing changes, rewrite
history, or introduce network services.

## Starting state

- Current release target: `0.1.3`.
- `master` contains completed and tested prompt-pack integration Phases A-C.
- Phase A: executor writes only a worktree-local handoff; the collector
  validates, hashes, and seals native completion evidence.
- Phase B: JSON-only native jobs are validated before launch, bound immutably,
  and enforce scope and controlled argv-vector command receipts.
- Phase C: the Tax Machine adapter validates only contained pack-local schemas,
  snapshots external evidence, and seals it without allowing it to become
  canonical completion or acceptance.
- The authoritative plan is
  `docs/PROMPT_PACK_RUNTIME_INTEGRATION_PLAN.md`; read it in full before edits.

## Objective

Finish only Phase D **if** the source pack provides the concrete contracts
required below. Preserve the central invariant:

> Executor exit, agent prose, external completion success, review prose, or a
> ledger event alone never means a ticket is accepted or green.

Implement an evidence-only ledger bridge and bound reviewer lifecycle only when
they can be verified against explicit versioned contracts. Keep legacy no-job
launches and existing `ledger`, `review`, and `accept` behavior compatible.

## Mandatory discovery gate

Before writing runtime code, locate the actual source-pack ledger/reviewer
definitions and write `docs/PHASE_D_DISCOVERY_REPORT.md` with exact paths,
hashes, schemas, and conclusions. You may proceed only if all are available:

1. A versioned append-only ledger event schema, including idempotency identity.
2. The ledger's authoritative root/repository binding and write/concurrency
   semantics (revision/CAS or equivalent).
3. A versioned reviewer-receipt schema or sufficient source-pack specification
   for one: implementation receipt hash, exact revision, reviewer
   identity/model/role, checklist hash, required gates, outcome, and
   independence rule.
4. A job policy that declares when independent review is required.

If any item is absent, do **not** invent a generic JSON ledger, queue, broker,
or reviewer protocol. Record the missing contract and a minimal proposed schema
in the discovery report, run the existing release gate, and stop with a clear
`BLOCKED` result. That is a correct outcome.

## Allowed Phase-D implementation

Only after the discovery gate passes, implement these bounded tickets in order.

### D1: append-only ledger bridge

Add an explicit `agent-workflow ledger sync` operation for the adapter that owns
the declared external ledger contract. It must:

- verify the run's final receipt against the recorded hash;
- verify immutable job binding, session/job/ticket/run/repository-root identity,
  valid completion collection, and canonical completion revision;
- validate the complete source ledger before mutation;
- append one event containing session, job, ticket, run, root identity, final
  receipt hash, completion status, disposition, accepted revision, and relevant
  lifecycle/review hashes;
- be idempotent for the same event and reject conflicts;
- write through a sibling temporary file, fsync, and atomic replace; failures
  must leave the original ledger byte-for-byte unchanged;
- never grant the executor ledger write access.

Do not change the current read-only `agent-workflow ledger PACK` view.

### D2: reviewer binding and receipt

Add an additive reviewer workflow; do not reinterpret the existing human
`review SESSION --actor --reason` command. A reviewer binding/receipt must
include and validate:

- implementation session ID, implementation final-receipt SHA-256, and exact
  implementation revision;
- reviewer identity, role, model, checklist path/hash, and declared
  independence policy;
- hashes/paths for completion collection, score set, scope reports, controlled
  command receipts, and patch/source-baseline evidence;
- reviewer outcome, gate results, rationale, and timestamp.

Reject a reviewer receipt if sealed implementation evidence has changed,
completion collection is invalid, required receipts/gates are missing or fail,
or declared reviewer independence is violated. A reviewer receipt is downstream
lifecycle evidence; it must not amend a sealed agent receipt.

### D3: job-declared acceptance enforcement

When an immutable job binding requires independent review or named gates,
`accept` must require a valid bound reviewer receipt whose implementation hash
and revision exactly match current sealed evidence and canonical completion.
Retain existing score, completion, tier, and exact-revision checks. Legacy
non-job sessions must remain compatible.

## Security constraints

- Never add external pack roots to `contracts._schema_roots()`.
- Never accept arbitrary shell command strings; use the existing validated argv
  command model.
- Never auto-merge, auto-kill, mutate a manifest implicitly, or add a daemon,
  remote transport, scheduler, database, message bus, or generic plugin system.
- Resolve paths before authorization; reject traversal, symlinks, and root
  disagreement.
- Keep external Tax Machine completion non-canonical unless a newer external
  schema supplies exact revisions, native criterion facts, and references to
  sealed controlled command receipts.

## Required tests

Add focused offline tests for every new contract and failure path. At minimum:

- valid ledger sync, idempotent retry, malformed ledger, mismatched run/root,
  tampered seal, invalid completion, conflicting revision, and no-mutation on
  failure;
- reviewer binding snapshots exact implementation evidence; stale/tampered
  evidence, missing receipts, failed gates, and self-review are rejected;
- job-required review blocks acceptance without a matching reviewer receipt;
- legacy no-job lifecycle remains unchanged;
- all new schemas are packaged and included in the final receipt where
  applicable.

Run:

```bash
./scripts/release-check.sh
python3 -m build --wheel
```

Regenerate `MANIFEST.sha256` with the project auditor after intended release
files change. Report exact test output, changed files, contract decisions, and
any remaining blocker. Commit only cohesive, validated work; do not claim D is
complete if the discovery gate is blocked.
