# HARD-001 — bounded subprocess execution substrate

**Backlog:** [`HARD-001`](../../../../docs/BACKLOG.md)  
**Priority:** P0 / Critical  
**Assessment:** [F04-F06, F18-F20, and F71](../../../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#4-feature-and-component-inventory) and the [hardening plan](../../../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md)

## Goal

Create one transport-neutral process execution substrate and migrate every repository-owned subprocess call that can hang, capture unbounded output, inherit sensitive environment, or expose secret-bearing argv.

## Current risk

The current call sites use several direct `subprocess.run` patterns without uniform timeout, process-group ownership, cancellation, output limits, environment policy, executable evidence, or redaction. A noisy or hung child can exhaust memory or block orchestration, while errors can disclose credentials embedded in argv.

## Required implementation

- Define one structured request/result contract for argv-only execution. It must support timeout, process-group creation, graceful cancellation then bounded escalation, maximum captured bytes per stream, optional spool files, truncation flags, duration, exit/signal outcome, and stable error categories.
- Build environments from an explicit policy: controlled `PATH`, fixed locale, no inherited shell functions, and configurable allowlisted variables. Callers may add named values but may not pass an ambient environment wholesale without an explicit unsafe policy.
- Record resolved executable path, reported version when probed, and optional digest in provenance without reading arbitrary large binaries into memory.
- Redact configured secret values and secret-bearing argument positions from errors, logs, JSON output, completion reports, and diagnostics. Preserve a digest when correlation is needed.
- Migrate `process.py`, doctor probes, Git helpers, runner/executor launch, pack archiving, installer probes where applicable, and evaluation/acceptance command collection. Inventory direct subprocess uses and document any deliberately exempt interactive tmux boundary.
- Keep shell invocation disabled by default. Explicit command launch remains argv-based and is labeled unclassified rather than a governed named adapter.

## Writable paths

- src/agent_workflow/process.py and a narrowly named shared process module if separation is necessary
- repository-owned subprocess call sites in `src/agent_workflow/**` and `scripts/**`
- installed-product acceptance journeys and one compact process outcome matrix
- docs/OPERATIONS.md, docs/ARCHITECTURE.md, SECURITY.md, help/man pages only where behavior changes

Do not broaden this scope without a recorded stop-and-escalate decision. Changes to shared documentation, schemas, tests, or manifests are allowed only when required by the implemented behavior.

## Parallel execution and dependencies

No incoming dependency. Run in parallel with HARD-002. It is a prerequisite for HARD-004, HARD-008, HARD-003, and HARD-006.

Use a dedicated worktree and session. Do not share a writable checkout with another ticket.

## Acceptance-first evidence

- An installed CLI journey launches a fixture that hangs; the command times out, owns and terminates its process group, returns a stable outcome, and leaves durable evidence.
- A fixture emits output beyond both caps; memory remains bounded, truncation/spool metadata is accurate, and retained output never exceeds policy.
- A synthetic secret in argv/environment is absent from stdout, stderr, JSON, logs, status, receipts, and failure messages while the redacted command remains diagnosable.
- Doctor and Git/worktree journeys still succeed through the shared substrate.
- A repository scan proves no unauthorized direct capture-without-timeout call sites remain.

A low-level test is permitted only for a compact parameterized security/replay matrix that the installed-product journey cannot exercise exhaustively. Do not restore parser-shape, mock-call, prose-wording, exact-dictionary, or broad snapshot tests.

## Security acceptance

- No `shell=True` or command-string fallback.
- Timeout/cancel applies to the complete child process group, not only the immediate process.
- Output and error paths are bounded even when decoding fails or a child emits binary data.
- Environment defaults remove credential-agent variables unless an explicitly configured adapter policy requires them.

## Non-targets

- Do not implement the OS sandbox owned by HARD-003.
- Do not redesign tmux topology, workflow scheduling, executor routing, or provider event schemas.
- Do not add a daemon or background worker.

## Stop conditions

- A required interactive boundary cannot use the substrate without breaking terminal ownership; document the exact exemption and stop.
- A call site needs ambient credentials or network but has no explicit policy contract.
- The change would silently alter public exit codes or evidence formats without a migration plan.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the exact revision, changed paths, acceptance commands and exit codes, retained invariant matrices with justification, unresolved risks, and all documentation/diagram/help/schema/skill/manifest updates. Run `python3 scripts/audit-release-assets.py` before claiming completion.
