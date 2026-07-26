# HARD-003 — preventative execution sandbox

**Backlog:** [`HARD-003`](../../../../docs/BACKLOG.md)  
**Priority:** P0 / Critical  
**Assessment:** [F39-F42 and F69-F73](../../../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#5-guidance-that-should-become-deterministic-enforcement) and the [hardening plan](../../../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md)

## Goal

Prevent unauthorized writes, credential access, uncontrolled network, and resource exhaustion during native jobs and evaluation/acceptance commands. Keep post-run scope comparison as evidence, not the barrier.

## Current risk

Current writable-path and scope rules are largely checked after execution. A malicious or compromised agent/command can read ambient credentials, exfiltrate data, alter files outside scope, or consume host resources before the violation is recorded.

## Required implementation

- Define a Linux-first sandbox contract with explicit allowed read roots, allowed write roots, temporary HOME/XDG roots, network policy, environment allowlist, CPU/memory/process/time/output limits, and observable backend/version.
- Select the smallest maintainable backend available on supported hosts (for example bubblewrap, Landlock, or a locked container). Fail closed for governed native-job/evaluation execution when no required backend is available; do not pretend post-run detection is equivalent.
- Run native jobs, baseline/post acceptance commands, oracle/scorer helpers, and optional model-based evaluators through HARD-001 inside the sandbox contract. Keep interactive external coding-agent policy explicit if a backend cannot yet cover it.
- Remove ambient SSH agent, cloud/provider tokens, user home mounts, shell startup files, and network by default. Add per-adapter/per-evaluation opt-ins that are recorded in immutable provenance.
- Mount or expose oracle material read-only and outside delegated worktrees. Enforce no-follow/digest checks from HARD-002.
- Retain pre/post scope inventory and record sandbox policy/backend/outcome in sealed evidence. A denied write is a deterministic failure, not a warning.

## Writable paths

- src/agent_workflow/native_jobs.py, eval/runtime/commands/scope/oracle adapters, process integration, config policy
- sandbox policy schema and packaged backend helpers
- installed-product malicious-command journeys plus one compact backend policy matrix
- docs/ARCHITECTURE.md, OPERATIONS.md, EVIDENCE_AND_EVALUATION.md, SECURITY.md, TESTING.md

Do not broaden this scope without a recorded stop-and-escalate decision. Changes to shared documentation, schemas, tests, or manifests are allowed only when required by the implemented behavior.

## Parallel execution and dependencies

Depends on HARD-008 within this pack and the accepted foundation pack externally. Run in parallel with HARD-006 after HARD-008.

Use a dedicated worktree and session. Do not share a writable checkout with another ticket.

## Acceptance-first evidence

- A native-job/evaluation fixture cannot write outside its allowed root, read a synthetic credential outside mounted roots, connect to a local network listener under default policy, or fork/emit output beyond limits.
- A valid bounded command completes and its evidence records backend, policy digest, resources, network mode, and denied operations.
- When the required backend is absent, governed execution fails with actionable doctor output; it does not silently run unsandboxed.
- Post-run scope evidence still detects unexpected changes within visible roots and matches the preventative policy.
- Optional live adapters use explicit isolated profiles and never become default-suite dependencies.

A low-level test is permitted only for a compact parameterized security/replay matrix that the installed-product journey cannot exercise exhaustively. Do not restore parser-shape, mock-call, prose-wording, exact-dictionary, or broad snapshot tests.

## Security acceptance

- Default deny for network and ambient credentials.
- Allowed write roots are component-wise no-follow and cannot be widened by child-created symlinks.
- Resource limits apply to the process tree.
- Sandbox escape or unavailable enforcement is a hard failure for governed evaluation/native jobs.

## Non-targets

- Do not claim full interactive-agent containment if the selected backend does not enforce it.
- Do not add Kubernetes, remote workers, a daemon, or multi-host execution.
- Do not replace sealed scope/evidence with sandbox logs alone.

## Stop conditions

- HARD-001, HARD-002, HARD-008, or FOUND-GATE-01 is not accepted.
- No supported backend can enforce the documented boundary on the declared host matrix; produce a decision record instead of an advisory wrapper.
- The implementation requires mounting real user credentials into default tests.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the exact revision, changed paths, acceptance commands and exit codes, retained invariant matrices with justification, unresolved risks, and all documentation/diagram/help/schema/skill/manifest updates. Run `python3 scripts/audit-release-assets.py` before claiming completion.
