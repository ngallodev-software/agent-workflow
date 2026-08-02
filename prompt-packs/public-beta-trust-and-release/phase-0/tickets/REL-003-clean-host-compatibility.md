# REL-003 — supported clean-host and executor compatibility

**Backlog:** [`REL-003`](../../../../docs/BACKLOG.md)  
**Priority:** P0 / High  
**Assessment:** [F14, F20, and F92](../../../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#47-testing-documentation-and-governance) and the [hardening plan](../../../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md)

## Goal

Define the first supported Linux/Python/tmux/executor matrix and collect bounded opt-in live evidence on representative clean hosts outside the development checkout.

## Current risk

Unit and installed-product fixture journeys cannot establish real tmux/provider CLI compatibility. Without a declared matrix and clean-host evidence, public support claims would be guesses and changing external adapters could break silently.

## Required implementation

- Propose the smallest support matrix with separate base and optional `mcp` install profiles: Linux distribution/kernel class, Python versions, tmux versions, archive tools, Git, and explicitly supported Codex/Claude CLI versions. Maintainer approval is required before calling it supported.
- Provision disposable clean hosts or containers/VMs that do not mount the development checkout or user credentials. Install from the candidate wheel/source artifact.
- Run install/doctor/uninstall, one bounded delegation per supported adapter, restart/recovery, workflow pipeline, receipt verification, and local stdio MCP read smoke. Use synthetic repositories and prompts.
- Record executable versions, config/sandbox policy, environment class, network mode, cost/spend ceiling, logs retention, and sealed evidence digests.
- Classify unsupported combinations clearly. Flakes or unavailable paid executors remain visible; do not turn them into mocked passes.
- Publish the approved matrix in installation/testing/support docs and make doctor report compatibility status.

## Writable paths

- tests/live/**, clean-host scripts/workflows, compatibility data and doctor reporting
- docs/INSTALLATION.md, TESTING.md, SUPPORT.md, PUBLIC_RELEASE_READINESS.md
- scrubbed external evidence attachment references, not permanent raw provider logs

Do not broaden this scope without a recorded stop-and-escalate decision. Changes to shared documentation, schemas, tests, or manifests are allowed only when required by the implemented behavior.

## Parallel execution and dependencies

External prerequisites: HARD-008 and ISO-GATE-01 accepted. Run in parallel with HARD-007, HARD-009, and HARD-010.

Use a dedicated worktree and session. Do not share a writable checkout with another ticket.

## Acceptance-first evidence

- Each declared supported combination completes the bounded live journey from a clean install.
- An unsupported version produces a clear warning/failure consistent with HARD-008 policy.
- No real credentials, proprietary repository data, or unbounded provider spend appears in evidence.
- Install/uninstall leaves no undeclared files and works without the source checkout.
- Results are reproducible enough to distinguish compatibility from one-off operator intervention.

A low-level test is permitted only for a compact parameterized security/replay matrix that the installed-product journey cannot exercise exhaustively. Do not restore parser-shape, mock-call, prose-wording, exact-dictionary, or broad snapshot tests.

## Security acceptance

- Use least-privilege disposable credentials and strict spend/time bounds.
- Scrub evidence before archiving; retain only fields allowed by HARD-006.
- CI/live hosts must not expose release secrets to untrusted code.

## Non-targets

- Do not expand support merely because a combination started once.
- Do not make paid/live tests part of the default offline suite.
- Do not implement MCP mutation, remote execution, or multi-host orchestration.

## Stop conditions

- HARD-008 and ISO-GATE-01 are not accepted.
- Maintainers have not approved the candidate support matrix.
- A live provider requires unsafe credential exposure or unbounded cost.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the exact revision, changed paths, acceptance commands and exit codes, retained invariant matrices with justification, unresolved risks, and all documentation/diagram/help/schema/skill/manifest updates. Run `python3 scripts/audit-release-assets.py` before claiming completion.
