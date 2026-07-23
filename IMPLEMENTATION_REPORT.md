# Orchestrator Messaging and Evals Implementation Report

## Critical review corrections

A second independent pass found and resolved defects that were not adequately covered in the first delivery:

- `IMPLEMENTATION.patch` omitted all newly added files and was not reproducible. It has been regenerated from the original 0.1.3 baseline and now includes added source, schemas, documentation, fixtures, mutations, and tests.
- acknowledgement correlation and duplicate checks occurred before the append lock, allowing two concurrent acknowledgements to race and both persist;
- the low-level message API accepted invalid kind/direction combinations, acknowledgements without correlations, correlations on non-ack records, mixed session IDs, and duplicate IDs in a replayed log;
- optional sealed evidence such as metrics and control events was not made read-only after sealing;
- metrics/control artifacts were sealed without explicit pre-seal schema validation;
- control-event output used a direct truncating write rather than atomic replace;
- normalized metrics emitted only a `total` stage rather than explicit orchestrator, child, verification, and total stages;
- negative token/cost facts and naive timestamps were accepted as usable normalized facts;
- the deterministic fixture lacked mutation, hidden-contract, oracle-leak, and repeat-stability tests;
- one pre-existing session-launch test assumed a real `codex` executable was on `PATH` despite mocking the surrounding executor interactions.

All of those issues are corrected in this archive.

## Implemented behavior

### Phase 0 — local control contract

- Added `docs/MESSAGING_PRIOR_ART_REPORT.md` with the selected local filesystem authority, replay, ordering, acknowledgement, retention, recovery, and threat model contract.

### Phase 1 — durable messaging

- Durable append/replay/wait behavior remains filesystem-authoritative with `flock`, contiguous sequence allocation, flush, and `fsync`.
- Message records now enforce semantic kind/direction and correlation rules at the lowest-level API.
- Replay rejects mixed sessions, duplicate message IDs, invalid acknowledgement ordering, duplicate acknowledgements, malformed records, and corrupt tails.
- New acknowledgements are validated against existing steers while holding the same exclusive lock used for append, closing the concurrent duplicate-ack race.
- Symlink/non-regular run and log targets remain rejected.

### Phase 2 — sealed metrics and deterministic eval

- Added provider-neutral nullable usage normalization without converting missing facts to zero.
- Added explicit `orchestrator`, zero-or-more `child:<actor>`, `verification`, and `total` metric stages. Unobserved stage facts remain `null`; child activity is created only from explicit child-to-parent records.
- Added atomic `control-events.jsonl` output and `execution-metrics.json`.
- Added JSON schemas and explicit pre-seal validation for both artifacts.
- Added sealing, verification, report visibility, and read-only handling for optional evidence.
- Added deterministic fixture tests covering known behavior, hidden-contract cases, three failing mutations, oracle-canary leakage, input mutation, and repeated-score stability.

### Phase 3 — blocked correctly

The required pinned browser image digest, pinned font manifest, and verified pre-seal browser/Inspect evidence bridge are still absent. The implementation therefore retains the blocked gate report and fixture protocol rather than claiming nondeterministic browser evidence.

## Validation

Passed against the corrected archive:

- 106 repository tests, plus 19 unittest subtests and fixture subtests, run in bounded groups;
- all 11 runner-generation and sealing tests;
- release asset audit with regenerated `MANIFEST.sha256`;
- Python compilation for `src` and `tests`.

The source's embedded prompt-pack copy still lacks its own `MANIFEST.sha256`; the separately supplied prompt-pack archive contains it. That prompt-pack copy remains outside the implementation ticket writable paths.

## Patch scope

`IMPLEMENTATION.patch` is generated from the original attached 0.1.3 source and includes all functional source, schema, documentation, fixture, mutation, and test changes. It intentionally excludes generated release bookkeeping (`MANIFEST.sha256`) and the implementation report/patch themselves to avoid self-referential checksums.
