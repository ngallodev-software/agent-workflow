# HARD-002 — artifact, path, and schema integrity

**Backlog:** [`HARD-002`](../../../../BACKLOG.md)  
**Priority:** P0 / Critical  
**Assessment:** [F11, F34-F38, F87, and source observations](../../../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#10-source-observations-supporting-the-highest-priority-findings) and the [hardening plan](../../../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md)

## Goal

Make every accepted prompt-pack, native-job, schema, and configured-root path deterministic, content-complete, and resistant to symlink or special-file ambiguity.

## Current risk

Prompt-pack archives can preserve symlinks that are omitted from checksum coverage; native-job and MCP path checks resolve before some symlink decisions; and schema lookup searches multiple roots where the first matching ID wins. These gaps let accepted behavior depend on filesystem entries that are not unambiguously manifested.

## Required implementation

- Adopt the minimal rule: repository-owned prompt packs and native-job inputs contain regular files and directories only. Reject symlinks, hard-link surprises where detectable, sockets, devices, FIFOs, and entries that change type during validation/archive.
- Validate archive inputs with component-wise no-follow traversal. Generate the archive from the exact validated entry inventory, and include file type, normalized relative path, size, mode policy, and digest in a canonical manifest or equivalently ban every unmanifested type.
- Open bounded files through descriptor-safe readers and compare identity/size/digest from the same bytes used by the consumer. Avoid validate-then-resolve or verify-then-reopen patterns.
- Make packaged schemas the authoritative runtime source. Fail on duplicate `$id`, conflicting copies, missing packaged assets, or source/install ambiguity; document supported migration lookup separately.
- Apply the same no-follow/regular-file rules to native-job JSON, prompt paths, pack roots, MCP pack validation, and configured repository/state roots where these utilities are shared.
- Preserve deterministic archives and update pack validation errors so users can identify the rejected entry without leaking unrelated host paths.

## Writable paths

- src/agent_workflow/pack.py, manifests.py, contracts.py, util/path helpers, native_jobs.py, and shared MCP path helpers
- prompt-pack archive/validation journeys and compact path-entry matrices
- schemas or manifest schema only when a versioned contract is required
- docs/PROMPT_PACKS.md, docs/ARCHITECTURE.md, SECURITY.md, and release audit

Do not broaden this scope without a recorded stop-and-escalate decision. Changes to shared documentation, schemas, tests, or manifests are allowed only when required by the implemented behavior.

## Parallel execution and dependencies

No incoming dependency. Run in parallel with HARD-001. It is a prerequisite for HARD-004, HARD-005, and HARD-003.

Use a dedicated worktree and session. Do not share a writable checkout with another ticket.

## Acceptance-first evidence

- A public pack-validate/archive journey rejects final and intermediate symlinks, FIFO/device/socket entries, and a file replaced between inventory and archive.
- A valid regular-file pack archives reproducibly and every accepted entry is represented by the canonical manifest policy.
- An installed native-job journey rejects a symlinked job or prompt component even when the resolved target remains inside the allowed root.
- Schema loading succeeds from packaged assets and fails deterministically on duplicate IDs or shadow copies.
- Existing source and wheel pack validation journeys remain green.

A low-level test is permitted only for a compact parameterized security/replay matrix that the installed-product journey cannot exercise exhaustively. Do not restore parser-shape, mock-call, prose-wording, exact-dictionary, or broad snapshot tests.

## Security acceptance

- Never follow a path merely to decide whether following it was allowed.
- Reject irregular entries fail-closed rather than silently skipping them.
- Normalize paths before comparison, but retain the unresolved component chain for no-follow checks.
- Do not weaken content checks to maintain compatibility with an unsafe archived pack.

## Non-targets

- Do not add pack signatures; HARD-010 owns authenticated release/signing work.
- Do not implement execution sandboxing or MCP mutation tools.
- Do not add a second schema registry or database.

## Stop conditions

- A retained compatibility format requires symlinks or special files; escalate for an explicit format decision rather than supporting them implicitly.
- Schema migration would require rewriting sealed evidence.
- The change cannot guarantee archive bytes come from the validated inventory.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the exact revision, changed paths, acceptance commands and exit codes, retained invariant matrices with justification, unresolved risks, and all documentation/diagram/help/schema/skill/manifest updates. Run `python3 scripts/audit-release-assets.py` before claiming completion.
