# P0: Agent-Workflow Skill and Orchestrator Integration

## Problem

`agent-workflow` has a complete CLI, durable run evidence, lifecycle runbooks,
and tmux behavior, but agents are not given an operational path to use them.
The installed skills describe ticket implementation, pack construction, and
phase review without naming the executable, command sequence, trigger rules,
or the boundary between native subagents and an `agent-workflow` run.

Consequently, an agent can read documentation yet still delegate through a
host-native subagent API, bypassing worktrees, durable receipts, control
records, and visible tmux panes. The current same-window tmux feature only
applies after an actor invokes `agent-workflow launch`; it cannot intercept a
native subagent spawn.

## Required outcome

Create one discoverable orchestration skill and make existing workflow skills
invoke it consistently. An agent must be able to answer, without guessing:

1. whether this work should be a direct edit, native subagent, or durable
   `agent-workflow` delegation;
2. how to create/validate a pack, worktree, and named run;
3. how to observe, steer, acknowledge, interrupt, review, and accept the run;
4. when a tmux pane will be visible; and
5. what `steer` does not prove for one-shot executor stdin.

## Scope

### New orchestration skill

Add a repo-owned `agent-workflow-orchestrator` skill with a precise discovery
description and this decision table:

| Situation | Required action |
|---|---|
| Small, local, one-step change with no independent evidence need | Work directly; do not create ceremonial delegation. |
| Bounded implementation ticket requiring an isolated worktree, persistent evidence, review, or recovery | Use `agent-workflow` and a validated prompt pack. |
| Read-only focused investigation where host-native subagents are explicitly preferred | Use the host-native mechanism; state that it is not an `agent-workflow` run. |
| Work requiring user-visible child panes while the orchestrator is inside tmux | Invoke `agent-workflow launch`; do not hand-create tmux sessions. |
| Need to alter a running agent | Append a durable `steer`; do not claim delivery until the executor adapter produces a correlated acknowledgement. |

The skill must give exact command patterns for `doctor`, `pack validate`,
`worktree create`, `launch`, `status`, `watch`, `steer`, `progress`, `ack`,
`interrupt`, `terminate`, `review`, and `accept`. It should link rather than
copy the detailed [command reference](COMMAND_REFERENCE.md),
[delegation lifecycle](DELEGATION_LIFECYCLE.md), and runbook/protocol.

### Update existing skills

- `prompt-pack-builder`: state when a pack is required and require its
  generated README/runbook to name `agent-workflow` invocation and the tmux
  visibility rule.
- `delegated-implementation`: state that the ticket should already be launched
  through the CLI, require durable `progress`/`ack` where the executor adapter
  supports them, and prohibit spawning a replacement agent from inside a
  ticket session.
- `phase-gate-review`: require evidence inspection through the CLI and
  distinguish sealed receipts from terminal output.

### Installation and discovery

Make the installer expose the complete skill set to every supported discovery
root, based on an explicit, tested policy. Do not assume that a host-native
skill discovery root and `~/.agents/skills` are equivalent. Verify the actual
Codex, Claude, and shared-agent roots on the target host; avoid duplicate-name
conflicts and preserve unrelated user-owned paths.

## tmux and native-agent contract

`agent-workflow launch` resolves a valid current tmux window and splits a
visible pane there. With no usable tmux context it retains the named detached
session fallback. Skills must direct agents to this command, never to raw
`tmux new-session`/`split-window` calls.

Host-native agent APIs are an independent control plane. They are not made
durable or visible by this repository unless a future host integration invokes
the CLI and translates lifecycle events. Do not imply that this P0 task solves
that integration automatically.

## Acceptance criteria

- A fresh supported agent can discover the orchestration skill and choose the
  CLI for a qualifying bounded delegation.
- The skill gives an executable happy-path command sequence and a concise
  recovery/control sequence.
- It states the tmux current-window behavior and detached fallback accurately.
- Existing skills cross-link consistently and do not duplicate conflicting
  policy.
- Installer tests cover every intended skill root, idempotence, and refusal to
  replace an unrelated file/symlink.
- Documentation tests verify the canonical links/commands; full release checks
  pass.

## Explicit non-goals

- Do not make a generic host-native `spawn_agent` API transparently become an
  `agent-workflow` run.
- Do not add terminal keystroke injection as a steering transport.
- Do not add MCP transport, a daemon, a broker, or a database in this ticket.
- Do not claim that an acknowledgement exists when the executor cannot receive
  late semantic input.

## References

- [Command reference](COMMAND_REFERENCE.md)
- [Delegation lifecycle](DELEGATION_LIFECYCLE.md)
- [Prompt-pack standard](PROMPT_PACK_STANDARD.md)
- [Current durable-control/evidence research](Durable_Orchestration_Delivery_Benchmarks.md)
- [Canonical backlog](../BACKLOG.md)
