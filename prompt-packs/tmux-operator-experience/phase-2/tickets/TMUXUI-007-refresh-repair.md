# TMUXUI-007 — event-hint refresh, debounce, and repair

**Backlog:** [`TMUXUI-007`](../../../../docs/BACKLOG.md)  
**Dependencies:** TMUXUI-002, TMUXUI-004

## Goal

Keep the status cache and active UI responsive using non-authoritative event hints, bounded coalescing, lazy refresh, and low-frequency repair.

## Writable paths

- Refresh coordinator/worker and namespaced hook assets.
- Integration points after existing lifecycle/message/review commits where architecturally appropriate.
- Config for debounce/repair intervals and worker enablement.
- Concurrency/hook lifecycle/recovery tests and installed journey.
- Operations/troubleshooting docs.

Do not replace durable replay, add a new message transport, or reproduce an aggressive 250 ms polling loop.

## Required behavior

- Refresh immediately after successful relevant application commits without making refresh failure roll back durable state.
- Append namespaced tmux hooks without clobbering existing arrays.
- Coalesce bursts under a short bounded debounce and single-writer lock.
- Refresh lazily on popup/dashboard open.
- Run low-frequency repair only while integration is enabled/active.
- Rebuild after missing cache, missed hook, server restart, or worker restart.
- Exit cleanly; prevent duplicate/orphan workers and busy loops.
- Treat every wakeup as a hint; source records remain authoritative.

## Acceptance and tests

- Existing hooks remain and execute in expected order/semantics.
- Bursts coalesce; a missed hook is repaired; cache deletion and tmux restart recover.
- Concurrent lifecycle mutation and refresh yields coherent complete snapshots.
- Disabled integration runs no worker/polling.
- Installed journey verifies install, event refresh, repair, uninstall, and process cleanup.

## Stop conditions

Stop if refresh hints become required for state delivery, if polling is high-frequency by default, or if worker ownership cannot be made deterministic and removable. Use `templates/TICKET_COMPLETION.md`.
