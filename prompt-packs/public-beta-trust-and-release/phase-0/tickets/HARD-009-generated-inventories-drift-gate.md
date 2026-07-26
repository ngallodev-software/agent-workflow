# HARD-009 — generated inventories and deterministic drift gate

**Backlog:** [`HARD-009`](../../../../BACKLOG.md)  
**Priority:** P1 / High  
**Assessment:** [F01-F02, F09-F10, and F90-F96](../../../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#8-public-release-direction) and the [hardening plan](../../../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md)

## Goal

Replace manual cross-document comparison with generated command/schema/service inventories and a deterministic release gate for backlog, prompt-pack, skill, documentation, diagram, test, and release drift.

## Current risk

The current release audit catches many static problems, and this delivery adds initial backlog-to-pack ownership checks plus the `release-drift-auditor` skill. It still relies on handwritten command/man/schema inventories and human discovery of some security-policy drift.

## Required implementation

- Generate a canonical public command/option inventory from the live parser and use it to validate or generate command reference, man-page option sections, and completion metadata.
- Generate schema ID/version inventory from packaged schemas, service/tool/resource inventory from registered CLI/MCP services, and skill/active-pack inventory from the repository.
- Extend the release audit to fail on unknown/duplicate backlog ownership, task-ID collisions, completed/blocked pack mislabeling, stale future-test IDs, duplicate schema IDs, undocumented active packs, missing skill mirrors, and generated-inventory drift.
- Add explicit security-claim annotations or a machine-readable inventory distinguishing enforced, detective, advisory, and human controls; use it to flag docs that overstate guidance as enforcement.
- Update the chart pack from generated inventories where feasible and keep only semantic explanations handwritten.
- Keep the audit fast, deterministic, offline, and usable from a source archive without Git history.

## Writable paths

- scripts/audit-release-assets.py and narrow generation helpers/assets
- docs/COMMAND_REFERENCE.md, docs/man/**, docs/diagrams/**, docs/PROMPT_PACKS.md, skills/** where generated references apply
- release tests and small drift failure fixtures
- templates/scaffold assets only where the canonical generated contract changes

Do not broaden this scope without a recorded stop-and-escalate decision. Changes to shared documentation, schemas, tests, or manifests are allowed only when required by the implemented behavior.

## Parallel execution and dependencies

External prerequisites: FOUND-GATE-01 and ISO-GATE-01 accepted. Run in parallel with HARD-007, HARD-010, and REL-003. The initial drift skill and ownership audit in this planning delivery are a baseline, not completion of HARD-009.

Use a dedicated worktree and session. Do not share a writable checkout with another ticket.

## Acceptance-first evidence

- Changing a parser command/option without updating generated references fails the release gate.
- A fixture with duplicate task IDs, unknown `backlog_id`, or two packs owning one backlog item fails deterministically.
- A stale strict future test referencing a nonexistent/completed backlog item fails.
- Duplicate schema IDs or a registered MCP/CLI service missing from the generated inventory fails.
- All canonical docs and diagrams pass after regeneration, and no host-specific paths or timestamps make outputs nondeterministic.

A low-level test is permitted only for a compact parameterized security/replay matrix that the installed-product journey cannot exercise exhaustively. Do not restore parser-shape, mock-call, prose-wording, exact-dictionary, or broad snapshot tests.

## Security acceptance

- Generated files are derived from source and marked as such.
- The audit does not execute untrusted repository commands or import optional provider SDKs with side effects.
- Errors identify repository-relative paths without dumping sensitive content.

## Non-targets

- Do not create a general documentation generator, static-site framework, or custom linter platform.
- Do not reintroduce completed prompt packs or historical ledgers as source-of-truth docs.
- Do not make prose wording snapshots part of the behavioral suite.

## Stop conditions

- Prior hardening packs are not accepted, making generated security claims unstable.
- Generation requires network access or nondeterministic external tools.
- A generated artifact would erase necessary semantic/security explanation.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the exact revision, changed paths, acceptance commands and exit codes, retained invariant matrices with justification, unresolved risks, and all documentation/diagram/help/schema/skill/manifest updates. Run `python3 scripts/audit-release-assets.py` before claiming completion.
