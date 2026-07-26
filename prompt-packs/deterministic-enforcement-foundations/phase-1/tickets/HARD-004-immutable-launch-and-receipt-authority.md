# HARD-004 — immutable launch and final-receipt authority

**Backlog:** [`HARD-004`](../../../../BACKLOG.md)  
**Priority:** P0 / Critical  
**Assessment:** [F17, F24, F68, and source observations](../../../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#10-source-observations-supporting-the-highest-priority-findings) and the [hardening plan](../../../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md)

## Goal

Create one immutable launch contract consumed by the runner and collectors, and remove the remaining cases where mutable `status.json` selects or supplies authoritative evidence.

## Current risk

Runner collectors still obtain launch paths and identifiers from a projection, and evaluation verification can obtain the expected receipt digest from that same mutable status. Even when receipts are strong, a mutable projection must not choose which authority is verified.

## Required implementation

- Write `launch-contract.json` before executor launch using an atomic, fsynced, read-only write. Bind session identity, ticket/pack, worktree, prompt and prompt digest, command plan, handoff paths, schema IDs/digests, runtime/evaluation policy, source baseline, and expected output locations.
- Have generated runners and collectors consume only the immutable contract plus append-only events/sealed receipts. Status remains a reconstructable projection.
- Define versioning and migration behavior for pre-contract runs. Existing sealed runs remain verifiable; repair/rebuild may regenerate projections but may not rewrite authority.
- Change receipt verification APIs to return the digest of the exact descriptor-verified bytes. Evaluation score/report/export and lifecycle decisions consume that returned digest or an immutable authority, never `_recorded_receipt_hash` from status.
- Remove duplicated mutable fields where safe, or label them explicitly as projections. Add a projection repair journey that reconstructs status from authority.
- Use the bounded process and path readers from HARD-001/HARD-002; do not create new local variants.

## Writable paths

- src/agent_workflow/sessions.py, runner.py, lifecycle.py, receipts.py, cli.py, evaluation verification services, state/migrations
- launch-contract JSON Schema and packaged asset
- installed-product launch/restart/eval journeys plus projection-tamper matrix
- architecture, evidence, operations, schema and migration documentation

Do not broaden this scope without a recorded stop-and-escalate decision. Changes to shared documentation, schemas, tests, or manifests are allowed only when required by the implemented behavior.

## Parallel execution and dependencies

Depends on HARD-001 and HARD-002. It may run in parallel with HARD-005 after both prerequisites are accepted.

Use a dedicated worktree and session. Do not share a writable checkout with another ticket.

## Acceptance-first evidence

- A public launch journey creates the contract before the child starts; mutating status afterward cannot redirect handoff, schema, command, or receipt selection.
- Restart/replay reads the same immutable contract and does not produce a timestamp or byte drift.
- Evaluation score/report/export verifies one stable receipt and uses the digest returned from those exact bytes.
- Deleting or corrupting status permits documented projection repair when authority is intact; changing status cannot change a lifecycle decision.
- Pre-contract fixture migration is explicit and never rewrites a sealed receipt.

A low-level test is permitted only for a compact parameterized security/replay matrix that the installed-product journey cannot exercise exhaustively. Do not restore parser-shape, mock-call, prose-wording, exact-dictionary, or broad snapshot tests.

## Security acceptance

- The contract is read-only before untrusted execution begins.
- All contract paths are root-contained and no-follow validated.
- No verify-then-reopen gap remains for fields used in authority decisions.
- Repair commands are deterministic projections and cannot accept or seal work.

## Non-targets

- Do not redesign workflow snapshots or journals that already satisfy immutable authority.
- Do not add actor authentication; HARD-007 owns principals.
- Do not use a database or mutable index as the new authority.

## Stop conditions

- HARD-001 or HARD-002 is not accepted.
- A migration requires modifying sealed evidence.
- A consumer still needs mutable status because the immutable contract is missing required data; extend/version the contract rather than preserving the authority leak.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the exact revision, changed paths, acceptance commands and exit codes, retained invariant matrices with justification, unresolved risks, and all documentation/diagram/help/schema/skill/manifest updates. Run `python3 scripts/audit-release-assets.py` before claiming completion.
