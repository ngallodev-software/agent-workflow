# HARD-010 — supply-chain integrity and authenticated release artifacts

**Backlog:** [`HARD-010`](../../../../BACKLOG.md)  
**Priority:** P1 / High  
**Assessment:** [F13-F14](../../../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#41-entry-points-configuration-host-integration-and-release-tooling) and the [hardening plan](../../../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md)

## Goal

Produce dependency locks, an SBOM, build provenance, independently reproducible wheel/source artifacts, and authenticated release attestations suitable for a public preview.

## Current risk

SHA-256 manifests detect accidental corruption but not malicious replacement at the publication point. Optional dependencies are not locked as a reviewed release set, CI actions may drift, and current reproducibility evidence is local rather than authenticated.

## Required implementation

- Choose and document a lock strategy covering core and each supported optional extra without forcing every optional dependency into core installation.
- Generate a standard SBOM for wheel and source release contents, including direct/transitive versions and hashes where available.
- Build wheel and source archive in two clean isolated environments from the same revision; compare normalized contents and document unavoidable metadata.
- Generate provenance tying revision, source manifest, build commands, toolchain versions, dependency lock, wheel/sdist digests, and test/release-gate results.
- Pin CI actions by immutable commit and minimize token permissions. Do not run secret-bearing release jobs on untrusted fork code.
- Implement an authenticated signing/attestation path approved by maintainers (for example Sigstore or an equivalent). If signing identity/publication is unavailable, produce the design and leave REL-004 blocked rather than simulating trust.

## Writable paths

- pyproject/dependency lock and release metadata
- CI/release workflows, scripts/release-check.sh, audit/build scripts
- SBOM/provenance schemas or templates and release tests
- docs/INSTALLATION.md, PUBLIC_RELEASE_READINESS.md, SECURITY.md, CONTRIBUTING.md

Do not broaden this scope without a recorded stop-and-escalate decision. Changes to shared documentation, schemas, tests, or manifests are allowed only when required by the implemented behavior.

## Parallel execution and dependencies

No technical dependency on another HARD ticket, but execute in the final pack so outputs reflect the hardened tree. Run in parallel with HARD-007, HARD-009, and REL-003.

Use a dedicated worktree and session. Do not share a writable checkout with another ticket.

## Acceptance-first evidence

- Core and supported-extra lock files resolve in clean environments and wheel install journeys remain isolated from the source checkout.
- Two clean builds produce equivalent normalized source/wheel contents and identical payload digests.
- SBOM and provenance reference exactly the delivered artifacts and pass offline verification.
- A modified artifact or mismatched provenance fails verification.
- Signing verification succeeds through the approved public identity/channel, or the ticket stops with a documented external blocker.

A low-level test is permitted only for a compact parameterized security/replay matrix that the installed-product journey cannot exercise exhaustively. Do not restore parser-shape, mock-call, prose-wording, exact-dictionary, or broad snapshot tests.

## Security acceptance

- No release secret is available to untrusted pull-request jobs.
- Checksums and signatures cover the artifacts users actually download.
- Provenance does not leak local paths, usernames, environment secrets, or proprietary source.

## Non-targets

- Do not publish a package or public release without maintainer authorization.
- Do not add a custom package registry, update service, or dependency proxy.
- Do not claim authenticated signing from a locally generated unaudited key.

## Stop conditions

- REL-001 license/distribution decision makes packaging metadata ambiguous.
- No monitored release owner or signing identity exists; complete non-signing work and leave the gate blocked.
- A dependency cannot be pinned/reproduced under the declared support policy.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the exact revision, changed paths, acceptance commands and exit codes, retained invariant matrices with justification, unresolved risks, and all documentation/diagram/help/schema/skill/manifest updates. Run `python3 scripts/audit-release-assets.py` before claiming completion.
