# TMUXUI-GATE-001 — independent core tmux operator experience review

This is a gate task and claims no backlog ownership. It may not implement missing scope.

## Writable paths

Only the phase-gate report and narrowly permitted review evidence. Do not edit product implementation.

## Review scope

Read all TMUXUI-001 through TMUXUI-007 and TMUXUI-009 tickets, completion records, integrated diff, canonical backlog, recommendation, pane-identity acceptance, installed/live evidence, release audit, and package contents.

## Acceptance review

Verify independently:

- PROC-006 is accepted and every focus/preview path uses stable pane ID without rebinding;
- one authoritative derived snapshot and no shell-owned status authority;
- deterministic attention ranking and safe bounded rendering;
- status line reads only a freshness-aware disposable cache;
- popup and dashboard do not affect agent capacity or managed work-window geometry;
- destructive actions revalidate state and route through existing services with confirmations/evidence;
- hooks are namespaced/non-clobbering, refresh is non-authoritative, and no worker/busy loop remains after uninstall;
- clean-wheel installed journeys and opt-in real tmux/fzf journey have exact commands/exit codes and cleanup;
- adversarial control-sequence, stale-selection, cache path, conflicting config, and concurrency cases pass;
- docs/help/config/changelog are current and make no REL-003-wide support claim;
- release-drift audit, pack validation, focused/full tests, and sealed receipts pass.

## Test and evidence requirements

Re-run the highest-value installed journeys and inspect wheel contents. Run `python3 scripts/audit-release-assets.py` and pack validation. Record exact commands and exits in `templates/PHASE_GATE_REPORT.md`.

## Stop/reject conditions

Reject if any managed action directly kills a pane before application lifecycle evidence, any cache/wakeup is treated as authority, any focus can rebind by location, installation mutates tmux implicitly, dashboard changes capacity/layout, live evidence is missing, or uninstall leaves active integration artifacts.
