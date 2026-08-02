# MAINT-006 — historical host-index evidence recovery

## Goal

Make `agent-workflow index verify --full` distinguish historical,
non-authoritative/obsolete run artifacts from corruption that must block a
current review, without weakening source-artifact safety or sealed-run checks.

## Defect

An independent MAINT-005 review completed with valid current evidence but the
host-wide full index verifier rejected historical directories with obsolete
schemas, missing retired metrics fields, and absent old collections. That
unrelated state prevents every otherwise valid review gate from completing.

## Required behavior

- Classify historical artifacts that cannot satisfy the current schema without
  treating them as current/valid evidence.
- Preserve fail-closed behavior for unsafe paths, tampered current artifacts,
  malformed current schemas, and any run claimed by an active/reviewed gate.
- Make full verification report the classification and a deterministic repair
  or quarantine outcome, then prove it against representative legacy and
  current sealed-run fixtures.
- Do not delete user evidence or mutate authority artifacts merely to make a
  verifier green.

## Writable paths

Index source discovery/verification, evidence classification/quarantine,
focused fixtures/tests, this manifest, and directly related operator
documentation only.

## Acceptance evidence

- Focused invariants cover current corruption rejection and historical artifact
  classification.
- An installed product journey proves a host with historical artifacts can
  complete full verification without misreporting them as current valid runs.
- Pack validation and release-drift audit pass.

## Stop conditions

Stop if the only way to pass is deletion, silently ignoring unsafe source
paths, downgrading a current integrity error, or changing immutable receipts.
