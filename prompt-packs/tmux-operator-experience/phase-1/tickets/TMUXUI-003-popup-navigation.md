# TMUXUI-003 — popup navigation, stable focus, and safe preview

**Backlog:** [`TMUXUI-003`](../../../../docs/BACKLOG.md)  
**Dependencies:** TMUXUI-001

## Goal

Provide the default operator interface: an attention-sorted popup/selector that focuses a run by stable pane ID and previews bounded escaped output without changing managed pane layout.

## Writable paths

- Popup/navigation presentation module and thin tmux/shell launcher assets.
- Minimal focus/capture primitives in `tmux.py` if not already sufficient.
- CLI/config fields for view, key, preview lines/bytes, and fallback behavior.
- Focused selector/preview tests and installed-product journey.
- Implemented command/help docs.

Do not add lifecycle mutations, hooks/background workers, dashboard panes, or embedded sidebar/layout changes.

## Required behavior

- Consume only the TMUXUI-001 snapshot contract.
- Support attention, flat runs, and bounded hierarchy views.
- Filter across ticket/run/agent/executor/model/branch/worktree/status/reason.
- Highlight the row bound to the current stable pane.
- Resolve focus immediately before `select-pane`; unavailable/stale bindings report clearly and never fall back to location matching.
- Fetch preview only for selected row; enforce line and byte limits; strip/escape control sequences; label unavailable/dead panes.
- Use `fzf` when available and a deterministic plain selector/print fallback when absent.
- Handle tmux popup/version/terminal-width limitations explicitly.
- Opening and closing the interface must not split, resize, kill, or recount managed panes.

## Acceptance and tests

- Layout and pane-index churn still focuses the original `%pane_id`.
- Pane destruction reports unavailable rather than selecting a replacement.
- Malicious titles/output cannot emit terminal-control side effects.
- Width/preview toggles, cancellation, no `fzf`, no popup support, and outside-tmux cases.
- Installed-product journey with deterministic selector stub proves row selection, focus target, preview bounds, and unchanged pane inventory.

## Stop conditions

Stop if the design requires copying the prior-art shell event loop, global tmux mutation, process-heuristic identity, or mutable pane indexes. Use `templates/TICKET_COMPLETION.md`.
