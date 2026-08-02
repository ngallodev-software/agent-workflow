# REL-004 — public security-hardening preview gate

**Backlog:** [`REL-004`](../../../../docs/BACKLOG.md)  
**Priority:** P1 / Critical  
**Assessment:** [F13-F14 and F94-F96](../../../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#8-public-release-direction) and the [hardening plan](../../../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md)

## Goal

Issue an independent, evidence-backed go/no-go decision for a public security-hardening preview after all technical and governance prerequisites are complete. This is a gate, not a feature phase.

## Current risk

A repository can accumulate release-shaped files while license, vulnerability reporting, compatibility, signing, isolation, identity, or drift controls remain unresolved. A public label must be tied to explicit evidence and an honest support boundary.

## Required implementation

- Verify every P0 HARD item and HARD-010 is accepted and integrated. Confirm REL-001 license, REL-002 monitored security channel, and REL-003 support matrix are complete; missing external decisions produce an explicit no-go.
- Apply `phase-gate-review` and `release-drift-auditor` with an independent principal under HARD-007 policy.
- Build source and wheel from a clean revision, verify SBOM/provenance/signature, inspect artifact inventories, install the base profile and each claimed optional profile into clean environments, run the acceptance/invariant gate, run declared live compatibility, and uninstall. Fail if Jenkins/GitHub workflow assets appear in a wheel or runtime bundle.
- Review the threat model for same-user malicious agents, untrusted repositories/packs, provider compromise, release-channel replacement, and future MCP mutation. Confirm every public claim states current boundaries and residual risks.
- Confirm active prompt packs do not collide: MCP-003 remains separately owned and blocked/ready according to HARD-004/HARD-005/HARD-007, while deferred DEC/ARC items remain out of release scope.
- Produce a signed/immutable gate report with explicit decision, supported matrix, artifact digests, unresolved risks, and rollback/advisory process.

## Writable paths

- narrow release-blocking fixes; release metadata, reports, manifests, and public docs
- no broad runtime feature paths unless correcting a reproduced gate defect

Do not broaden this scope without a recorded stop-and-escalate decision. Changes to shared documentation, schemas, tests, or manifests are allowed only when required by the implemented behavior.

## Parallel execution and dependencies

Depends on HARD-007, HARD-009, HARD-010, and REL-003 in this pack, plus external completion of all P0 HARD work, REL-001, and REL-002. This ticket runs last and acts as the independent release gate.

Use a dedicated worktree and session. Do not share a writable checkout with another ticket.

## Acceptance-first evidence

- Clean source/wheel build, install, default tests, release audit, pack validation, live matrix, and uninstall all pass from delivered artifacts.
- Artifact signatures/attestations and provenance verify through the approved identity/channel.
- License and vulnerability reporting are real and monitored, not placeholders.
- Public docs do not claim MCP mutation, remote execution, multi-host support, full sandbox coverage, or authenticated review beyond implemented evidence.
- The final report records go or no-go; it never converts skipped/missing evidence into pass.

A low-level test is permitted only for a compact parameterized security/replay matrix that the installed-product journey cannot exercise exhaustively. Do not restore parser-shape, mock-call, prose-wording, exact-dictionary, or broad snapshot tests.

## Security acceptance

- The gate reviewer is independent under HARD-007 and reviews exact artifact digests.
- No release credential is exposed to untrusted code or included in evidence.
- Rollback/security advisory ownership is named and operational.

## Non-targets

- Do not implement new MCP, workflow, routing, evaluation, UI, remote, or multi-host features.
- Do not invent a license, security contact, signing identity, or external adopter.
- Do not lower acceptance requirements to meet a date.

## Stop conditions

- Any prerequisite is incomplete or unverifiable.
- The release audit or clean-host gate is flaky/non-reproducible.
- A public claim cannot be supported by current code and evidence.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the exact revision, changed paths, acceptance commands and exit codes, retained invariant matrices with justification, unresolved risks, and all documentation/diagram/help/schema/skill/manifest updates. Run `python3 scripts/audit-release-assets.py` before claiming completion.
