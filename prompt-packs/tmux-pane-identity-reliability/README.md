# tmux-pane-identity-reliability

## Purpose

Fix the shared-window lifecycle identity bug in `agent-workflow`. The current
implementation persists `session:window.pane_index` as `tmux_target`; adding or
removing another pane can renumber that index and make a live executor appear
orphaned to `task-complete`, status, steering, interrupt, terminate, kill, or
reusable-agent discovery.

The implementation must bind each shared-window pane to the application run
identity, use tmux's stable pane ID for the pane lifetime, preserve a clear
real-orphan outcome when tmux actually destroys the pane, and provide a safe
compatibility path for pre-fix status records.

## Source baseline

The pack was prepared from the `agent-workflow` repository at the clean master
revision produced with this pack. The checked-out source remains authoritative
when it differs from included references. Read `references/pane-identity.md`
before editing.

## Phase map

| Phase | Objective | Complexity | Exit dependency |
|---|---|---|---|
| 0 | Durable shared-window pane identity | A / critical | none; independent implementation followed by a separate gate |

## Universal delegation rules

- Execute every ticket in a fresh named terminal session.
- Use an isolated worktree unless the ticket is explicitly read-only.
- Read required references and current source before editing.
- Follow writable-path restrictions.
- Do not add tests without naming the contract or failure they protect.
- Stop when source contradicts the ticket in a way that could overwrite newer architecture.
- Produce a ticket completion report and preserve all command output.
- Implementation starts in an interactive pane by default. If the configured
  pane limit is full, report the count and idle candidates and obtain an
  explicit choice of close-idle, structured non-interactive fallback, or
  cancellation.

## How to execute

Use `agent-workflow pack validate` before launch. Create the isolated worktree
with `agent-workflow worktree create`, then launch the implementation through
`agent-workflow launch`. A valid current tmux context produces a visible pane;
an unusable context falls back to a detached named session. Native host
subagents are not durable workflow runs unless explicitly bridged through the
CLI. See `EXECUTION_PROTOCOL.md`, `DELEGATION_RUNBOOK.md`, and the phase README.
