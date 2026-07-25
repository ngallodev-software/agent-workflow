# ChatGPT implementation handoff

You are responsible for completing this repository’s remaining workflow and
benchmark tickets. Work until all listed tickets are completed or a genuine
external blocker is documented with reproducible evidence. Do not stop at a
plan, scaffold, or partial green test run.

## Source and authority

Read `SESSION_RESTORE.md`, `BACKLOG.md`, `FEATURE_TEST_LEDGER.md`, this pack’s
README, execution protocol, delegation runbook, and every referenced source
and research document before editing. Rebuild the codebase-memory index before
implementation if available. Preserve unrelated dirty changes. The
repository CLI, durable records, sealed receipts, and canonical backlog are
authoritative; terminal output is observational only.

## Tickets and order

Complete these exact tickets in order:

1. WF-10 — receipt-backed approval gates.
2. WF-11 — bounded JSON Pointer result binding.
3. WF-12 — aggregate workflow receipts.
4. WF-20 — the three authorized reusable graph templates.
5. WF-21 — deterministic explainable routing advice.
6. WF-22 — integration, security, documentation, release, and full-suite review.
7. BKL-003-RESEARCH — provider evidence/usage research and implementation design.
8. BKL-003 — sealed provider evidence and usage normalization.

Use the ticket dependencies and isolated worktrees. Each implementation must
have a separate independent review. Integrate only after a valid
`agent-workflow/completion/v1` handoff, scope check, focused gates, full-suite
gate, and release-audit result. If a review rejects a ticket, correct it and
repeat the review; do not waive the finding.

## Research and safety

Use primary official sources for unstable executor/provider facts and record
citations with access dates. Preserve append-only JSONL/control-log and receipt
authority. Never infer approval, steering delivery, usage, cost, or provider
behavior from logs, prose, tmux capture, or keystrokes. Keep MCP mutation work
behind its declared backlog gate. Do not introduce alternate launch paths,
hidden mutable authorities, destructive tools, or speculative abstractions.

## Mandatory final critical review and repair

After all eight tickets have been accepted, perform a fresh critical review of
the complete cumulative diff and current source. Check, at minimum:

- ticket scope, dependency order, and backlog/document consistency;
- workflow state/replay/restart invariants and approval receipt authenticity;
- JSON Pointer bounds, retry lineage, template expansion, and routing policy;
- MCP/CLI shared-service boundaries and no alternate executor path;
- executor-specific Claude/Codex commands, interactive defaults, model/no-go
  policy, tmux layout/capacity, naming, and permissions;
- durable messages, cursors, acknowledgements, receipts, provenance, and
  idempotency;
- raw usage evidence, delta/cumulative/terminal semantics, cost/null rules,
  retry accounting, comparison validity, and research citations;
- security, path traversal, redaction, schema compatibility, release
  manifest, packaging exclusions, documentation drift, and regressions.

Fix every error, drift, stale claim, failed test, or security weakness found
by that review. Rerun focused tests for each repair, the complete test suite,
release audit, pack validation, and available offline smoke checks. Repeat the
review/fix cycle until clean. Finish with a detailed phase-gate report listing
accepted commits, tests and exit codes, unavailable external checks, known
limitations, final version, and archive checksums.

## Required final deliverables

- all ticket source changes and tests;
- updated canonical backlog, status/history, architecture/research docs, and
  feature ledger;
- valid completion/review/acceptance evidence for every ticket;
- validated prompt pack and source archive checksums;
- a concise final handoff summarizing implementation, verification, and any
  explicitly unresolved external gates.
