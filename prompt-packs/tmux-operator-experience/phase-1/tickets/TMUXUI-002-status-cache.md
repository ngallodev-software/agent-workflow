# TMUXUI-002 — projection cache and status-line renderer

**Backlog:** [`TMUXUI-002`](../../../../docs/BACKLOG.md)  
**Dependencies:** TMUXUI-001

## Goal

Build a disposable, freshness-aware projection cache and a status-line renderer that performs no durable-state scan and no tmux inventory during redraw.

## Writable paths

- Focused cache/projection module and thin packaged renderer asset.
- Config/schema fields limited to cache TTL and rendering format.
- Status-line CLI wiring and package-data declarations.
- Cache safety tests and installed-product renderer journey.
- Implemented command/config/operations documentation.

Avoid popup, action dispatcher, dashboard, tmux hook installation, and layout code.

## Required behavior

- Compute counts from the TMUXUI-001 snapshot service.
- Write atomically under a safe XDG runtime/cache path with bounded mode, no-follow/symlink defense consistent with repository policy, and a version/freshness timestamp.
- Read fresh, stale, missing, malformed, and partial caches safely.
- Render compact and verbose deterministic text; stale output is visibly stale and never presented as current.
- The status-line read path must not import expensive state scanning or execute tmux.
- Do not set global `status-interval`, overwrite `status-right`, or mutate tmux during package install.

## Acceptance and tests

- Fresh/stale/missing/malformed/partial/symlink and concurrent-reader cases.
- Atomic replacement leaves readers with old or new complete content, never partial JSON.
- A command-spy test proves the renderer does not invoke tmux or durable-state scans.
- Built-wheel journey writes a projection then renders fresh and stale forms.
- Package-data test proves thin assets are present.

## Stop conditions

Stop if the cache becomes necessary for authoritative status or lifecycle decisions, or if safe path handling would be weaker than existing repository storage policy. Use `templates/TICKET_COMPLETION.md`.
