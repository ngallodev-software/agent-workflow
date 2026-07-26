# ISO-GATE-01 — independent isolation and disclosure review

**Task type:** independent gate; no backlog ownership  
**Assessment:** [feature determinism and security assessment](../../../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md) and [hardening plan](../../../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md)

## Goal

Independently review the integrated phase after all prerequisite implementation tickets are complete. This ticket may correct a narrowly reproducible defect discovered during review, but it may not add planned feature scope.

## Prerequisites

- `HARD-008` accepted and integrated.
- `HARD-003` accepted and integrated.
- `HARD-006` accepted and integrated.

## Required review

- Apply the `phase-gate-review` skill.
- Apply the `release-drift-auditor` skill.
- Inspect complete integrated diffs, not only ticket reports.
- Rerun shared installed-product journeys after merge.
- Run `python3 scripts/audit-release-assets.py` and validate every active prompt pack.
- Attempt writes outside allowed roots, child-created symlink escapes, credential reads, network access, fork/resource exhaustion, and unavailable-backend fallback.
- Inject synthetic secrets through every supported ingestion surface and inspect CLI, MCP, logs, reports, telemetry fixtures, and archives.
- Verify retention removes only eligible content and preserves authority/digests.
- Confirm config/executable identity in provenance matches the actual process launched.

## Writable paths

- Narrow fixes required to resolve a reproduced phase defect.
- Phase-gate report and deterministic manifests.

Unrelated cleanup, new feature work, and broad refactoring are prohibited.

## Acceptance evidence

- Every prerequisite ticket has a completion report and independently rerun gates.
- Backlog IDs and active prompt-pack ownership are collision-free.
- Security claims distinguish preventative enforcement, post-run detection, and guidance.
- README, architecture, operations, testing, MCP, security, diagrams, skills, help, man pages, schemas, and release metadata agree with the integrated code.
- The report issues an explicit accept or reject decision with unresolved blockers.

## Stop conditions

Stop and reject the phase when a prerequisite is missing, an authority still depends on mutable projection, a claimed preventative control is only detective, a pack collides with another backlog owner, or the full acceptance gate is not reproducible.
