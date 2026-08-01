# TMUXUI-001 — authoritative tmux operator snapshot

**Backlog:** [`TMUXUI-001`](../../../../docs/BACKLOG.md)  
**Priority/risk:** P1 / High  
**External prerequisite:** PROC-006 accepted with live-host and sealed pane-identity evidence.

## Goal

Create one bounded, transport-neutral operator snapshot that joins durable `agent-workflow` run/assignment/workflow state, observed state, inbox/acknowledgement/review state, and one tmux inventory by stable pane ID. This snapshot is the only data model consumed by later tmux UI renderers.

## Writable paths

- New focused tmux operator snapshot/model module(s) under `src/agent_workflow/`.
- Minimal bounded inventory helpers in `src/agent_workflow/tmux.py`.
- Public CLI wiring in `src/agent_workflow/cli.py` and related command catalog/schema only where required by current architecture.
- Optional versioned snapshot JSON Schema if public contract policy requires it.
- Focused invariant/unit and installed-product snapshot tests.
- `docs/TMUX_OPERATOR_EXPERIENCE.md` authority/contract foundation and command reference entries for implemented behavior.

Do not edit lifecycle transition implementations, pane-identity migration, layout creation, or prompt-pack infrastructure except for required compatible references.

## Required behavior

- Define explicit snapshot and row types with stable version identifier.
- Use existing durable services/state readers; do not create shell status files or a new database.
- Execute one bounded `tmux list-panes -a` inventory command per snapshot and parse stable `%pane_id`, role/run metadata, session/window identity, current/dead state, command/title, and geometry only as needed.
- Join managed rows by durable run binding and stable pane ID. Never rebind by pane index, title, PID, process ancestry, or location.
- Derive deterministic attention reason codes and rank centrally.
- Include truthful `tmux_available`, server reachability, pane alive/current, preview availability, and safe action identifiers.
- Return valid degraded JSON when tmux is missing, unreachable, slow, or malformed.
- Sanitize ANSI/OSC/control characters and bound every user-controlled string.
- Exclude prompts, secrets, environment contents, and unbounded logs.
- Provide machine JSON and a compact human rendering without duplicating business ranking.

## Acceptance and tests

- Deterministic rank and tie-break matrix covers needs-input, failed/unavailable, stalled, completed-pending-review, running, accepted/archiveable, and history.
- Existing pane-identity tests prove layout/index churn does not change target; a destroyed pane reports unavailable without rebinding.
- One mocked/fake tmux inventory invocation serves multiple run rows.
- No-tmux, no-server, dead pane, unknown role, malformed metadata, malicious control sequences, oversized labels, and concurrent state-change cases are covered.
- Installed-product journey executes the public snapshot command from a built wheel and validates bounded JSON fields and exit code.
- Existing full focused tmux/session slices remain green.

## Non-targets

No popup, dashboard, cache, hooks, background worker, lifecycle action, external pane discovery, or embedded sidebar.

## Stop conditions

Stop if PROC-006 is not accepted, if the required join would use mutable pane position, or if current source provides no authoritative read path without rewriting lifecycle authority. Record the conflict rather than adding a second model. Use `templates/TICKET_COMPLETION.md`.
