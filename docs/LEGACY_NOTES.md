# Legacy Notes

This file preserves the small amount of historical context still useful after the Agent-Workflow 0.8 rewrite. Detailed pre-0.8 planning, checkpoint, migration, and terminal-runtime documents are intentionally not retained in the active tree; Git history and release archives are the historical record.

## 0.8 architectural break

Agent-Workflow 0.8 replaced the old broad execution/session model with the durable **Agent Run** model:

```text
Workflow
  -> Task
     -> Agent Run
        -> Worker
```

The rewrite intentionally removed the terminal-multiplexer/runtime layer rather than hiding it behind another terminal abstraction. Agent-Workflow now owns durable workflow authority, worktree/source provenance, execution contracts, durable control messaging, evidence, evaluation, review/acceptance, supervision, indexing, and benchmark semantics. Interactive runtime presentation is outside core scope.

The rewrite also intentionally carries no compatibility implementation for the pre-0.8 terminal-era CLI, schemas, runtime modules, or execution identity. Historical artifacts should be recovered from source-control or release archives when needed rather than reintroduced into current runtime code.

## 0.8 simplification closeout

After the headless-core rewrite, an eight-phase simplification program removed remaining duplication without changing the durable Agent Run architecture. The completed program:

1. removed obsolete pre-0.8 compatibility paths and duplicate outputs;
2. consolidated append-only JSONL durability and locking mechanics into a shared journal primitive while leaving domain semantics with their owning modules;
3. made the Agent Run lifecycle journal the authority for active execution state, immutable terminal evidence authoritative after sealing, and `status.json` a rebuildable projection;
4. simplified Agent Run path, preparation, execution, and evidence responsibilities;
5. consolidated canonical serialization, digest, and sealing helpers without merging independent domain authorities;
6. unified prompt packs around one root `pack.yaml` workflow manifest and reserved `MANIFEST.json` for deterministic archive integrity;
7. deduplicated built-in benchmark storage into shared immutable layers plus thin suite overlays while preserving exported suite bytes and frozen identities; and
8. separated remaining Agent Run identity, runner evidence collection, and SQLite storage/integrity/review responsibilities only where they represented genuine independent change boundaries.

The simplification program intentionally stopped after Phase 8. Future structural refactoring should require a concrete duplication, authority conflict, obsolete compatibility surface, or change-boundary problem; file length or module count alone is not a reason to recombine or split the core. Detailed phase reports and the implementation plan were removed from the active documentation tree and remain available through source-control/release history.

## Current authoritative records

Use the current documentation set rather than implementation-era Phase 0–2 handoff material:

- `docs/ARCHITECTURE.md` — implemented 0.8 architecture and authority boundaries.
- `docs/OPERATIONS.md` — runtime operation, recovery, and evidence handling.
- `docs/TESTING.md` — permanent acceptance-first test and release-gate policy.
- `docs/BACKLOG.md` — the only unfinished-work register.
- `docs/PROMPT_PACKS.md` — current prompt-pack format and operating guidance.

The Phase 0–2 implementation report, remaining-work handoff, headless rewrite specification, acceptance evals, closeout prompt-pack specification, closeout evals, and their specs index were retired after the full 0.8 acceptance/release gates passed. Their durable architectural outcomes are now represented by current code, schemas, tests, ADRs, and the documents above; historical detail belongs in source-control/release history.

## Intentionally removed historical artifacts

The 0.8 cleanup removes several superseded artifacts from the active repository:

- the original repository audit that described the pre-rewrite terminal/tmux architecture;
- the pre-implementation Agent Run architecture planning document;
- the Phase 0–2 path-by-path removal manifest;
- the generated Phase 0–2 handoff file/hash manifest tied to the prior transfer baseline;
- the July 2026 two-way-messaging blocker inventory tied to version 0.2.5.

Those documents described work already incorporated into the 0.8 implementation or captured stale repository snapshots. Keeping them in the current documentation set created duplicate authority and stale backlinks.

## Terminology note

The word `session` may still appear where it belongs to a third-party provider or authentication protocol, for example a subscription-backed provider CLI session. It must not be used as Agent-Workflow's durable execution identity; that object is an **Agent Run**.
