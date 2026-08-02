# MAINT-007 — host-index integrity remediation

## Goal

Resolve the remaining non-compatible host evidence failures without modifying
sealed evidence or falsely classifying corruption as historical compatibility.

## Known finite census

- one sealed `executor-events.jsonl` size mismatch;
- four unsealed legacy launch contracts missing `ticket_identity`;
- two unsealed stale command catalogs missing `plugins`;
- ten sealed/dispositioned provenance envelopes containing `external_snapshots`.

## Required behavior

- Define durable, append-only incident/disposition authority outside source run
  artifacts, with exact session/artifact/error identity and a human decision
  boundary.
- Keep global `index verify --full` false for unresolved integrity incidents.
- Add a review-scoped verification mode that proves the reviewed sealed run and
  its direct gate evidence are valid without silently ignoring global incidents.
- Preserve source safety, receipt digest/size checks, and active/reviewed-gate
  rejection. No deletion or rewrite of host evidence.

## Writable paths

Index verification/disposition source, focused fixtures/tests, this ticket,
and directly related operator documentation only.

## Evidence

- Focused corruption/disposition invariants and an installed review journey.
- Host rebuild and full verification report exact unresolved incident counts.
- Pack validation and release-drift audit pass.

## Stop conditions

Stop if the proposed path deletes or edits source evidence, allows unresolved
incidents to pass global verification, or lets review scope conceal an invalid
reviewed run or its direct gate evidence.
