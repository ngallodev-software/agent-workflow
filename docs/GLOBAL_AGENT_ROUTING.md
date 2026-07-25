# Global agent routing and enforcement

## Decision

Use global agent instructions and the installed `agent-workflow-orchestrator`
skill to route work by intent. Add host hooks only as narrow, opt-in enforcement
for recognizable direct delegation commands. Do not claim that a hook can infer
whether every prompt should become a durable workflow run.

The durable boundary remains `agent-workflow launch`. A raw host-native subagent,
`tmux split-window`, `claude`, or `codex` process is not an agent-workflow run and
does not gain its worktree, receipts, message log, class/model policy, or review
gates.

## Host behavior

| Host | Semantic routing | Enforceable boundary |
|---|---|---|
| Codex | Global `AGENTS.md` plus the installed orchestration skill | Codex has no repository-supported semantic hook API. Rules may constrain exact command prefixes, but must not replace task classification. |
| Claude Code | Global instructions plus the installed orchestration skill | An opt-in `PreToolUse` hook may reject known raw delegation shell patterns and direct the caller to `agent-workflow launch`. Existing hooks must be preserved. |

## Required hook properties

- installer-managed and opt-in; uninstall removes only files and settings it owns;
- idempotent merge with existing host configuration;
- fail closed only for exact direct-delegation patterns, never broad shell use;
- emit a concise replacement command and preserve a local audit record;
- allow an explicit, recorded break-glass bypass;
- test Codex and Claude configuration independently using their actual nouns and
  flags;
- never rewrite native host subagent APIs transparently, because they do not
  provide an agent-workflow worktree or durable evidence contract.

Until that adapter is implemented and tested, the supported enforcement is the
orchestration skill plus application-level executor, model, permission, agent
name, and agent-class validation.
