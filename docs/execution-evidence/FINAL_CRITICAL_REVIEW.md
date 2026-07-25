---
schema: agent-workflow/phase-gate/v1
pack_id: chatgpt-workflow-completion-next
phase: release-0.2.1-critical-repair
review_session: local-critical-repair-20260724
decision: accepted_with_follow_up
---

# Release 0.2.1 Critical Review

## Supersession notice

This report supersedes the 0.2.0 final critical review. The earlier conclusion that no known correctness or security defect remained was too optimistic. A fresh review reproduced and corrected material scheduler, replay, evidence-authority, and concurrent-sealing defects. The 0.2.0 gate remains in Git history and `WORKFLOW_BENCHMARK_PHASE_GATE.md` only as historical evidence.

## Review method

The delivered source archive was extracted independently at commit `4ece38c` and treated as an untrusted release candidate. The review traced workflow state from canonical files through replay, scheduling, projection, retry, sealing, trial extraction, and provider normalization; wrote regression tests before repairs; ran focused negative/tamper suites; audited documentation and release metadata; and repeated the cumulative suite outside the foreground tool timeout.

## Defects found and corrected

1. **Active-capacity oversubscription.** Existing `running` nodes did not consume `max_parallelism`. Planning now subtracts active nodes before selecting work.
2. **Circular child authority.** A historical workflow event or a callback result containing only `run_id` could prove a child existed. Running state now requires a matching regular provenance contract or verified final receipt in the canonical child run directory.
3. **Missing terminal reconciliation.** Restarted workflows did not automatically consume sealed child outcomes. Running children are now reconciled from final status, completion collection, and the verified final receipt.
4. **Retry replay contradiction.** The CLI allowed retry from `recoverable`, but event replay rejected the resulting binding. Replay and transition rules now agree.
5. **Permanently failed descendants.** Dependency-propagated failures did not reopen after a prerequisite retry. Those nodes return to `blocked`, then become eligible only after the prerequisite completes.
6. **Projection authority and staleness.** Start/status logic depended on `workflow-run.json`, and projections could be stale immediately after scheduling. The immutable snapshot and event journal establish a started workflow; mutable projections are regenerated after scheduling and on status reads.
7. **Snapshot and journal durability gaps.** Canonical snapshots remained writable, journal appends did not validate prior content under one lock, and directory entries were not always fsynced. Snapshots and workflow receipts are made read-only before their atomic rename; snapshots are descriptor-validated; journals reject symlink/non-regular substitutions, validate contiguous history before append, lock stable reads, and persist directory-entry changes.
8. **Concurrent sealing race.** Receipt construction could reconstruct one journal state and hash another while scheduling appended events. Scheduling, sealing, verification, and projection refresh now share a descriptor-safe workflow lock.
9. **Duplicate graph identifiers.** Duplicate dependency IDs and task session IDs were accepted. Normalization and JSON Schema now reject both.
10. **Mutable score verdict authority.** Trial extraction trusted `score-set.json` without validating the referenced scorer receipts. Extraction now validates content-addressed receipts, expected scorers, final-receipt binding, and the derived verdict.
11. **Provider usage undercount and false completeness.** Empty/conflicting terminal totals, non-finite values, regressing cumulative totals, incomplete currency/catalog metadata, and equal unidentified delta events could be accepted or silently deduplicated. These cases now fail closed; explicit event identities remain idempotent and distinct identified deltas count independently.
12. **Raw stream substitution.** Provider capture could follow symlinks or observe a file changing between parse and hash. Capture now requires one regular non-symlink descriptor, hashes the complete stream, bounds parsing, and rejects in-flight mutation.
13. **Receipt-root and final-seal races.** Lifecycle code resolved `receipts/` before testing for a symlink, and final-run seal creation/verification lacked a shared serialization boundary. Receipt roots and seal locks now reject symlinks/non-regular files, directory entries are fsynced, and final receipts/artifacts are read and hashed from stable descriptors.
14. **Split receipt verification and digest reads.** Several consumers verified `final-receipt.json` and then hashed its pathname in a second operation; aggregate workflow receipts used the same split read/stat/hash pattern. Verification now returns the digest of the exact final-receipt bytes read under `seal.lock`, and workflow receipts are parsed, mode-checked, and hashed from one non-symlink descriptor under `workflow.lock`.
15. **Mutable content-addressed scorer receipts.** Scorer receipts used content-derived filenames but were writable and could be read through symlinks. They are now atomically installed read-only, validated from regular non-symlink descriptors, and rejected if an existing content-addressed path is writable or disagrees with its object. Lifecycle review hashes the exact score-set bytes it validated.
16. **Post-verification sealed-artifact reopen.** Lifecycle review, approval gates, scheduler reconciliation, result binding, workflow receipt construction, and trial extraction verified a final seal and then reopened sealed JSON by pathname. Those authority paths now read the exact receipt-listed artifact through beneath-root, no-symlink descriptors and recheck size/hash before using it.
17. **Incomplete and unsafe read-only pass.** The optional `assignments/` evidence tree was omitted, and chmod could follow a symlink to an outside target. All sealed required/optional trees are now covered, symlinks are rejected, and chmod is descriptor-based. Seal creation and verification also reject intermediate symlink components even when they point back inside the run.
18. **Writable copied launch inputs.** Parent workflow binding snapshots were read-only, but the child copy and native-job binding artifacts remained writable until terminal sealing. Parent and child workflow inputs, native-job snapshots, and binding receipts are now made read-only before their atomic rename and before executor launch.
19. **Stale release evidence.** The feature ledger, MCP follow-on baseline, man pages, cleanup audit, phase-gate status, diagrams, backlog history, and version markers still represented 0.2.0 as current. Current surfaces now identify 0.2.1 and explicitly preserve 0.2.0 only as historical provenance.

## Verification evidence

| Gate | Result |
|---|---|
| Focused authority, evidence, receipt, launch, and immutable-input suites | 101 passed; 13 subtests passed |
| Cumulative suite excluding release-manifest tests | 235 passed; 1 optional integration skipped; 49 subtests passed in 43.74 seconds |
| Full repository suite with regenerated release manifest | 238 passed; 1 optional integration skipped; 49 subtests passed in 45.12 seconds |
| Schema, compilation, shell syntax, prompt-pack, and manifest checks | Passed |
| Source/release archive and wheel checks | Recorded in the final delivery summary after packaging |

## Boundary and simplification audit

- Canonical append-only records and sealed receipts remain authoritative; mutable status, run projections, logs, and terminal capture do not.
- No second scheduler, executor, daemon, broker, database, HTTP service, arbitrary shell/path surface, or MCP mutation implementation was added.
- The shared workflow lock is a local coordination primitive, not a new state store.
- Historical prompt packs and ticket reports remain for reproducibility but are labeled as history rather than active architecture or task tracking.
- No additional vendored dependency or removable runtime subsystem was found after the 0.2.0 SDK cleanup.

## Remaining follow-up

- `BKL-004` still requires a controlled real-provider cohort; no model or routing winner is claimed from fixtures.
- MCP mutation work remains `MCP-003`, ready but not implemented.
- No independent external Codex/Claude reviewer executable was available. This review therefore records local executable evidence and does not fabricate an external receipt.

## Decision

Accept release 0.2.1 with the external-review and real-provider-cohort follow-ups above. Unlike the superseded 0.2.0 report, this decision explicitly records the defects discovered after delivery and the regression boundaries added for each repair.
