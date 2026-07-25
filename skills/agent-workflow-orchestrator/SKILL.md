---
name: agent-workflow-orchestrator
description: Choose, launch, observe, control, recover, review, and accept durable agent-workflow delegations while preserving worktree isolation and sealed evidence.
---

# Agent-workflow orchestrator

Use this skill when deciding whether work needs a durable delegation or when operating an existing `agent-workflow` run. Use the repository CLI for lifecycle actions; do not substitute raw tmux commands or a host-native subagent call.

## Decision table

| Situation | Action |
|---|---|
| Small, local, one-step change with no independent evidence need | Work directly. Do not create ceremonial delegation. |
| Bounded ticket requiring an isolated worktree, persistent evidence, independent review, or recovery | Use `agent-workflow` with a validated prompt pack. |
| Focused read-only investigation where a host-native subagent is explicitly preferred | Use the host-native mechanism and state that it is not an `agent-workflow` run. |
| User-visible child panes are required while the orchestrator is inside tmux | Invoke `agent-workflow launch`; never hand-create the tmux session or pane. |

Select an agent class explicitly when the task differs from the configured
default. `exploratory` and `review` are normally non-interactive detached runs;
`implementation` is normally an interactive pane. The application validates
the class against configured executor/model pairs and rejects no-go models
unless the caller supplies the explicit authorization flag.
| A running agent needs new guidance | Append `steer`; treat it as pending until a correlated executor acknowledgement exists. |

A host-native subagent is not automatically durable, visible, resumable, or evidenced by this project. It becomes an `agent-workflow` run only when an explicit bridge invokes the CLI and records the required lifecycle evidence.

## Happy path

```bash
agent-workflow doctor
agent-workflow pack validate /path/to/prompt-pack
agent-workflow worktree create /path/to/repo P0-01 HEAD --dest /path/to/worktree
agent-workflow launch project-p0-01 /path/to/worktree /path/to/prompt-pack/phase-0/tickets/P0-01.md \
  --ticket P0-01 --pack /path/to/prompt-pack --executor codex
agent-workflow status project-p0-01 --capture 50
agent-workflow watch project-p0-01 --after 0 --timeout 300
```

When launched from a valid current tmux window, `agent-workflow launch` creates a visible pane in that window. Without a usable tmux context, it falls back to a detached named session. Always use the CLI so source baselines, prompts, commands, logs, and receipts are recorded.

## Control and recovery

```bash
agent-workflow steer project-p0-01 "Run the focused tests before editing." --actor orchestrator
agent-workflow progress project-p0-01 "Focused tests passed." --actor child
agent-workflow ack project-p0-01 MESSAGE_UUID "Applied at checkpoint." --actor child
agent-workflow interrupt project-p0-01
agent-workflow terminate project-p0-01 --grace-seconds 10
agent-workflow restart project-p0-01
```

`steer` persists a durable request. It does not prove that a one-shot executor consumed semantic input. Only a correlated acknowledgement from a supported executor adapter establishes delivery/application.

## Review and acceptance

```bash
agent-workflow status project-p0-01 --capture 100
agent-workflow review project-p0-01 --actor reviewer --reason "Diff and gates independently checked"
agent-workflow accept project-p0-01 --actor reviewer --reason "Approved" --revision COMMIT_SHA
```

Terminal text is operational context, not sealed proof. Inspect the authoritative run evidence and receipts before review or acceptance.

## Canonical references

- [`docs/COMMAND_REFERENCE.md`](../../docs/COMMAND_REFERENCE.md)
- [`docs/DELEGATION_LIFECYCLE.md`](../../docs/DELEGATION_LIFECYCLE.md)
- [`docs/PROMPT_PACK_STANDARD.md`](../../docs/PROMPT_PACK_STANDARD.md)
- [`EXECUTION_PROTOCOL.md`](../../EXECUTION_PROTOCOL.md)
- [`DELEGATION_RUNBOOK.md`](../../DELEGATION_RUNBOOK.md)

## Workflow graphs

```bash
agent-workflow workflow validate workflow.json
agent-workflow workflow start workflow-run workflow.json
agent-workflow workflow status workflow-run workflow.json
agent-workflow workflow resume workflow-run workflow.json
agent-workflow workflow seal workflow-run workflow.json
agent-workflow workflow verify workflow-run workflow.json
```

Use only the three authorized `workflow template` shapes. Treat the normalized snapshot and append-only workflow journal as authority. Approval gates require canonical immutable lifecycle receipts. Result bindings may consume only bounded JSON Pointer values from sealed ancestor results. Do not launch workflow children outside the scheduler's canonical session service.

## Provider and MCP boundaries

A structured run is comparison-ready only when its bounded raw executor stream, provider evidence, metrics, completion, and final receipt are sealed and complete. Do not infer tokens or cost from prose/logs, add cached or reasoning details twice, or combine provider-billed and locally estimated cost.

The current `agent-workflow-mcp` adapter is local stdio and read-only. Do not claim planned MCP-003 mutation tools exist. Any future MCP mutation must reuse shared services and durable idempotency.
