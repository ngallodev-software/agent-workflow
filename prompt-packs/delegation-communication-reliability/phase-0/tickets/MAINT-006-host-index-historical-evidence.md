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

The current host census is bounded and must be addressed deliberately: 109
legacy `launch-contract.json` envelopes lack `ticket_identity`, 30 legacy
`command.json` envelopes lack `classification`, 10 legacy
`run-provenance.json` envelopes contain an earlier allowed-property shape, and
seven sealed receipts predate `collections/completion.json`. One separately
sealed `executor-events.jsonl` size mismatch remains an integrity failure, not
compatibility evidence. Do not replace these finite observed categories with a
generic "old artifact" rule.

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
- Reproduce the actual host state before claiming closure: record the
  `error_count`, `quarantined_count`, and representative errors from
  `agent-workflow --json index rebuild` followed by
  `agent-workflow --json index verify --full`. Fixture-only success is not
  closure while the host verifier remains incomplete.
- Where a sealed historical receipt predates a current required collection,
  derive compatibility from the receipt's own immutable format/evidence and
  repository migration history. Continue to verify every artifact actually
  listed by that receipt (including path, hash, and size); never use a blanket
  bypass for missing modern collections or artifact integrity failures.
- Pack validation and release-drift audit pass.

## Stop conditions

Stop if the only way to pass is deletion, silently ignoring unsafe source
paths, downgrading a current integrity error, or changing immutable receipts.
