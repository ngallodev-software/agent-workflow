# Agent-Workflow completion handoff and name-lease incident — 2026-08-30

## Scope and disposition

This records an observed Agent-Workflow product incident while running three
low-tier OSINT Suite simplification tasks. It does not accept, merge, or claim
the delegated work complete. The underlying Agent Runs remain the authority for
execution state and receipts.

The incident has two independent product gaps:

1. Two workers finished useful scoped changes and passing focused tests but
   produced a completion sidecar whose criterion values were schema-invalid.
   The resulting status/failure reporting was not consistently actionable.
2. Old external `prepared` runs with no live worker retained preferred names.
   The public external-worker controls could neither retire the run nor release
   its name, forcing an operator to replace the configured pool.

The active remediation register is [`../BACKLOG.md`](../BACKLOG.md):
`COMP-001` and `LEASE-001`.

## Evidence inventory

All paths below are local, durable evidence paths on the observing host. SHA-256
values bind this report to the observed bytes; the paths are not part of the
Agent-Workflow source tree and must not be copied into release artifacts.

| Run | Observed terminal state | Evidence path | SHA-256 |
|---|---|---|---|
| `osint-s017-generated-r4` | `completed`; handoff valid | `~/.local/state/agent-workflow/runs/osint-s017-generated-r4/final-receipt.json` | `62b66eb209a186b64a45cfe89997f7e4e0ff2befc985516140501fc217c195f0` |
| `osint-s018-docs-r4` | `failed`; completion invalid | `~/.local/state/agent-workflow/runs/osint-s018-docs-r4/execution-metrics.json` | `02de3aea64d9e1fbd4d15f2505c453aedca5c2ed22d2bf71064df8e3835c6fec` |
| `osint-s018-docs-r4` | source sidecar, invalid enum | `~/.local/share/agent-workflow/worktrees/osint-suite/s018-doc-authority/.agent-workflow-handoff/osint-s018-docs-r4/completion.json` | `0b9f2ce54bc9e1f515c739ffa661334c75e7a927143a27dc03cae821e47f4fb3` |
| `osint-s019-installer-r3` | `failed`; completion invalid | `~/.local/state/agent-workflow/runs/osint-s019-installer-r3/collections/completion.json` | `399a3ee8fff0e64f53e5b7ac6fb83ba1553ee4cc5702c755c8a19f808b839e5d` |
| `osint-s019-installer-r3` | source sidecar, invalid enum | `~/.local/share/agent-workflow/worktrees/osint-suite/s019-installer-authority/.agent-workflow-handoff/osint-s019-installer-r3/completion.json` | `56bcd073531cc698dfa3e4988ce317d04fb6fff82e70e7debb016db838198fdd` |

The valid S-017 run establishes that the same launcher, Luna model, and
worktree pattern can finish successfully; it does not validate either failed
run's unreviewed source changes.

## What happened

| Run | Reported scoped result | Validation evidence | Formal outcome |
|---|---|---|---|
| S-017 | generated-artifact cleanup | 12 package artifacts built, 4 focused release tests, package-integrity, and `git diff --check` passed | valid completion; still requires review/acceptance/integration |
| S-018 | root documentation authority plus nested compatibility pointers | 19 focused documentation/suite-contract tests passed | sidecar used `criteria[0].result: "verified"`; schema rejected it |
| S-019 | nested installer reduced to a root-path-resolving wrapper | 7 installer integration tests and `bash -n` passed | three criteria used `result: "verified"`; schema rejected each |

The completion schema deliberately permits only `pass`, `fail`, and
`not_verified` for criterion results
([`schemas/completion.schema.json`](../../schemas/completion.schema.json)).
The semantic completion validator likewise requires `pass` for every criterion
on a completed implementation
([`src/agent_workflow/completion.py`](../../src/agent_workflow/completion.py)).

The workers therefore supplied evidence with an intuitive but invalid synonym,
not a valid completion record. The system correctly withheld completion. The
operator-facing diagnosis was inconsistent: S-018 was classified
`command_not_found` even though its recorded detail is a completion-schema
error; S-019 was classified `completion_invalid`. The diagnostic rules currently
match broad text patterns before the completion-specific rule
([`src/agent_workflow/diagnostics.py`](../../src/agent_workflow/diagnostics.py)).

## External prepared-run name retention

Before the current workers were launched, nine external runs were still
authoritatively `prepared`; they had no live worker and included completed work
from the preceding simplification audit. Their names occupied the configured
preferred-name pool. `agent-run terminate` correctly reported that external
worker lifecycle control was unavailable, but it left each run `prepared`.

This is a lifecycle retirement gap, not evidence that a worker process exists.
The existing `status_agent_active()` intentionally treats a `prepared` run as
active, and `claim_agent_name()` uses that result to reserve names
([`src/agent_workflow/agent_identity.py`](../../src/agent_workflow/agent_identity.py)).
The replacement `luna-*` name pool was an operational workaround, not a
product fix.

The related external-start boundary is documented in
[`AGENT_WORKFLOW_DELEGATION_EXTERNAL_LIFECYCLE_DIAGNOSIS_20260829.md`](AGENT_WORKFLOW_DELEGATION_EXTERNAL_LIFECYCLE_DIAGNOSIS_20260829.md).
Do not solve this issue by making `prepared` automatically terminal after a
time limit: an external host may legitimately wait for operator launch. The
retirement action must be explicit, durable, and auditable.

## Remediation requirements

### COMP-001 — completion sidecar preflight and diagnostic precision

1. Provide one authoritative completion-sidecar validator usable by workers
   before `task-complete`, returning field-level errors and accepted enum
   values.
2. Preserve strict schema semantics; do not silently rewrite evidence after a
   worker has submitted it. If convenience normalization is added, it must
   occur before submission and show the exact transformed bytes to the worker.
3. Classify schema-invalid sidecars as `completion_invalid` (or a more specific
   `completion_schema_invalid`), never as a missing executable merely because
   an error string contains a path-like phrase.
4. Permit a bounded handoff-only correction path while the run is still alive
   or before finalization; retain the rejected sidecar and reason as evidence.
5. Test `verified` rejection/repair, a valid `pass` record, and classification
   precedence.

### LEASE-001 — explicit retirement for unlaunched external runs

1. Add an operator-facing, idempotent abandonment/retirement action only for
   an external run that remains `prepared` and has no active external binding
   or worker observation.
2. Append lifecycle authority explaining actor, reason, and observed binding
   generation; refresh the mutable status only from that authority.
3. Release the preferred name only after the terminal retirement evidence is
   durable. Never delete or edit historical leases/status files by hand.
4. Reject retirement of a bound/current external worker and all non-prepared
   execution states.
5. Test name reuse after retirement, refusal for active/bound runs, and exact
   preservation of the historical run record.

## Verification and integration boundary

No remediation is implemented by this report. S-018 and S-019 must be
relaunched or have their completion evidence corrected and independently
reviewed before source changes are integrated. S-017 has valid completion
evidence but likewise remains outside acceptance and integration gates.
