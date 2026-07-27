# PROC-GATE-001 — independent communication-reliability review

This is a gate task and claims no backlog ownership. Read every phase ticket,
the complete integrated diff, `docs/BACKLOG.md`, the release-drift audit, and
the phase-gate template.

Verify independently:

- live prerequisite dispositions and no stale-projection authority;
- progress/ack/steer correlation and append-only control evidence;
- silent-pane classification and evidence-preserving termination/retry;
- substantive completion validation and separate receipt/eval/ledger gates;
- writable scope, no prompt-only substitute controls, and documentation drift;
- `python3 scripts/audit-release-assets.py`, pack validation, focused journeys,
  and the shared release checks.

Write `templates/PHASE_GATE_REPORT.md` with exact commands and exit codes. The
decision must be `accepted`, `rejected`, or `accepted_with_follow_up`; do not
infer acceptance from green unit tests alone.

Stop and reject if any completion report is placeholder-only, any control
message lacks correlation evidence, any silent run was treated as healthy, or
any required command has no recorded exit code.
