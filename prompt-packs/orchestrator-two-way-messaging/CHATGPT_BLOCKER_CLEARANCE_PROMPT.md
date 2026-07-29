# ChatGPT handoff — clear prerequisites for two-way messaging

Use this as the initial prompt for ChatGPT when preparing the repository for the
`orchestrator-two-way-messaging` implementation. This document is a handoff
prompt, not a new backlog owner or implementation pack. Existing pack ownership
and `docs/BACKLOG.md` remain authoritative.

## Mission

Work in `/lump/apps/agent-workflow` and clear the verified prerequisites that
currently block durable two-way messaging between child agents and the
orchestrator. Do not claim the messaging feature is complete until the
dependency chain, installed-product journeys, sealed evidence, independent
review, and lifecycle dispositions are complete.

The desired end state is an accepted foundation for:

```text
child event/message -> durable per-session journal
                   -> aggregate orchestrator inbox
                   -> single-writer supervisor and wake hint
                   -> fixed-format orchestrator resume
                   -> correlated delivery/application/action evidence
                   -> restart-safe replay and installed-product acceptance
```

Tmux is only a wake hint. JSONL journals, verified identities, immutable
contracts, append-only events, receipts, and lifecycle evidence are authority.

## Current repository truth

Read these files before changing anything:

- `docs/BACKLOG.md` — only unfinished-work register;
- `docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md`;
- `prompt-packs/orchestrator-two-way-messaging/pack.yaml` and its phase manifests;
- `prompt-packs/orchestrator-two-way-messaging/EXECUTION_PROTOCOL.md`;
- `prompt-packs/orchestrator-two-way-messaging/DELEGATION_RUNBOOK.md`;
- the ticket files named below;
- current source, schemas, tests, skills, and sealed evidence.

As of the handoff:

| Item | State | Meaning for this mission |
|---|---|---|
| `DEC-001` | decided | Local append-only JSONL authority, per-consumer FIFO, at-least-once append, digest-bound idempotency, rebuildable cursors, and a two-second normal replay objective. |
| `BKL-001` | completed | Durable consumer cursor/idempotent handling work was accepted with sealed evidence. Do not redo it; verify and reuse it. |
| `HARD-001` | completed individually | Accepted bounded process foundation; the aggregate foundation gate is separate. |
| `HARD-002` | completed individually | Accepted path/schema foundation; preserve its documented filesystem-socket host limitation. |
| `HARD-004` | in-review | Immutable launch/receipt implementation is integrated, but the shared foundation gate and independent sealed disposition remain open. |
| `HARD-005` | in-review | MCP read-boundary implementation is integrated, but its installed-stdio acceptance/disposition must be verified and accepted. |
| `HARD-008` | blocked | Configuration/executor trust; required before later supervisor/content work. |
| `HARD-006` | blocked | Sensitive-content classification/redaction/retention; requires accepted `HARD-005`, `HARD-008`, and foundations. |
| `HARD-007` | blocked | Authenticated principals and reviewer independence; requires accepted `HARD-004` and the applicable foundation/isolation gates. |
| `BKL-002` | ready but gated | Post-launch steering; its ticket requires accepted `HARD-001`, `HARD-004`, `HARD-007`, and `HARD-008`. |
| `MSG-001` through `MSG-007` | blocked | Messaging implementation chain; follow the manifest dependencies and ticket prerequisites exactly. |

The old `docs/BLOCKERS_20260727.md` is historical context. Reconcile it with
the current canonical backlog and current evidence; do not revive resolved
environment or BKL-001 claims as active blockers.

## Operating rules

1. Probe codebase-memory-mcp once for structural discovery and use it when
   available, then use literal search for docs/configuration. If unavailable or
   permission-gated, record `codebase_memory: unavailable` and continue with
   bounded RTK discovery without retrying. Record final status honestly.
2. Run `python3 scripts/audit-release-assets.py` and validate the existing
   packs before scheduling work.
3. Implementation work starts interactively by default in a dedicated
   worktree and durable agent-workflow session. Review, exploration, and
   evidence inspection may be non-interactive.
4. If the tmux window is at its pane limit, report the pane count and idle
   panes. Offer closing idle sessions, a structured non-interactive fallback,
   or cancellation. Never silently downgrade implementation work.
5. A structured provider stream is required for post-run evaluation; native
   TUI output alone is not evaluation evidence.
6. Every delegated implementation uses a stable ticket/pack identity,
   writable-scope declaration, acceptance plan, completion handoff, sealed
   receipt, evaluation result/collection, ledger row, and lifecycle disposition.
7. Close agent-workflow sessions through the framework after completion and
   verify their tmux panes/sessions are gone.
8. Preserve unrelated user changes. Never copy an external `BACKLOG.md`
   wholesale and never change a ticket to completed from prose or terminal
   output.

## Required execution order

### 0. Baseline and gate inventory

Produce a short machine-readable inventory of the current states, prerequisites,
commits, receipts, missing evidence, and writable scopes. Validate:

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate prompt-packs/deterministic-enforcement-foundations
agent-workflow pack validate prompt-packs/execution-isolation-and-secrets
agent-workflow pack validate prompt-packs/public-beta-trust-and-release
agent-workflow pack validate prompt-packs/orchestrator-two-way-messaging
```

Do not start `MSG-001` while `HARD-004` remains unaccepted.

### 1. Close the foundation review blockers

Handle these as separate review/evidence lanes unless source fixes are needed:

- `HARD-004`: inspect the integrated authority implementation, rerun its
  installed launch/restart/evaluation/projection-tamper journeys, obtain the
  independent sealed disposition, and rerun the shared `FOUND-GATE-01`.
  If code changes are necessary, start an interactive implementation session
  in a dedicated worktree. Verify that mutable status cannot select launch,
  receipt, evaluation, or lifecycle authority.
- `HARD-005`: verify current installed-wheel stdio MCP coverage for bounded
  metadata-only reads, no-follow paths, stable errors, receipt summaries, and
  secret/path non-disclosure. If the evidence is incomplete, make only the
  necessary interactive implementation changes, then obtain an independent
  disposition.

Do not mark either ticket accepted merely because focused tests pass. Require
completion handoff, final receipt, evaluation collection/report, ledger entry,
writable-scope check, and lifecycle acceptance.

### 2. Clear hardening prerequisites in parallel where legal

After the applicable foundation gates are accepted, use separate worktrees for:

- `HARD-008`: implement and verify config/executor trust, unknown-key rejection,
  ownership/mode checks, executable identity/provenance, sanitized Git/executor
  environments, compatibility data, and safe doctor/dry-run output.
- `HARD-007`: only after `HARD-004` and the required foundation/isolation gate;
  implement authenticated principal evidence, self-review separation, stable
  authorization errors, and historical legacy-receipt classification.

Then run:

- `HARD-006` after accepted `HARD-005` and `HARD-008`; implement classification,
  redaction, retention, export refusal, and synthetic-secret acceptance without
  deleting authority or sending content to an external classifier.

Do not implement `HARD-003` as an unrequested substitute for these tickets,
and do not claim `HARD-007` is complete until the minimum assurance decision and
immutable principal evidence are actually present.

### 3. Complete the messaging-specific prerequisite

Run `BKL-002` after `BKL-001`, `HARD-001`, `HARD-004`, `HARD-007`, and `HARD-008`
are accepted. Prove that a detached executor consumes post-launch steering
without restart and emits correlated `delivered`, `applied`, `rejected`,
`unsupported`, or `expired` evidence. Terminal text and process liveness are
not proof.

### 4. Resume the messaging pack

Follow `prompt-packs/orchestrator-two-way-messaging/pack.yaml` exactly:

1. `MSG-001` — immutable orchestrator registry and append-only aggregate inbox
   after `DEC-001`, `HARD-002`, and accepted `HARD-004`.
2. `MSG-002` — foregroundable single-writer supervisor, hashed wake channel,
   replay fallback, fairness, and cursor-after-commit fan-in after `BKL-001`,
   `MSG-001`, `HARD-001`, and accepted `HARD-008`.
3. `MSG-003` — fixed-format wake/resume adapters carrying opaque event IDs only
   after `MSG-002`, `HARD-004`, `HARD-006`, `HARD-007`, and `HARD-008`.
4. `MSG-005` — restart/missed/duplicate/corrupt-cursor reconstruction after
   `BKL-001`, `MSG-001`, and `MSG-002`. It may run alongside `MSG-003` when all
   ticket-specific prerequisites are accepted.
5. `MSG-004` — delivery/application/action acknowledgement semantics after
   `MSG-002`, `MSG-003`, `MSG-005`, and `HARD-007`.
6. `MSG-006` — adversarial identity, bounds, redaction, no-follow, duplicate,
   prompt-injection, resource, and supervisor-ownership hardening after the
   integrated messaging implementation and all named hardening tickets.
7. `MSG-007` — installed-wheel completion/wakeup/restart/action journeys and
   opt-in tmux/executor compatibility after `MSG-001` through `MSG-005` and
   `BKL-002`.
8. Delegate `MSG-GATE-01` to an independent reviewer using
   `phase-gate-review` and `release-drift-auditor`.

## Acceptance and closeout

For every ticket, require the installed-product journey first, then only the
compact invariant matrices needed for replay, security, identity, accounting,
or no-follow boundaries. Before changing its backlog state, verify:

- exact commit and changed paths are inside the declared scope;
- completion handoff is substantive and schema-valid;
- sealed final receipt and lifecycle receipt are present and non-blocked;
- evaluation score/report/collection exists when required;
- ledger row binds the same run, ticket, pack, source, and evidence digests;
- independent review is actually independent;
- `python3 scripts/audit-release-assets.py`, pack validation, build, and the
  relevant installed-product tests pass.

At the end, update only the canonical backlog with evidence-backed states and
return a concise table of accepted, still blocked, and deferred items. Do not
claim that two-way messaging is ready for production until `MSG-GATE-01` and
the final installed-product/restart/wakeup evidence pass.

## Required ChatGPT handoff

Return:

1. the blocker graph before and after;
2. delegated session IDs, worktree paths, models, interactive/non-interactive
   mode, and pane closeout evidence;
3. commits and changed-path summaries for each accepted ticket;
4. test, build, audit, sealed receipt, evaluation, ledger, and lifecycle
   evidence paths;
5. exact reasons for any remaining blocker;
6. the next executable messaging phase, if and only if its prerequisites are
   accepted.
