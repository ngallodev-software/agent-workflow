---
name: agent-workflow-orchestrator
description: Choose, launch, observe, control, recover, review, and accept durable agent-workflow delegations while preserving worktree isolation and sealed evidence.
---

# Agent-workflow orchestrator

Use this skill when deciding whether work needs a durable delegation or when operating an existing `agent-workflow` run. Use the repository CLI for lifecycle actions; do not substitute raw tmux commands or a host-native subagent call.

## Command contract

Use `agent-workflow commands --role orchestrator --format markdown` or the full JSON catalog instead of running `--help` before routine commands. A launched child receives the exact catalog and a role-scoped card through `AGENT_WORKFLOW_COMMAND_CATALOG` and `AGENT_WORKFLOW_COMMAND_CARD`; use `AGENT_WORKFLOW_CLI` as its canonical executable. Only fall back to `--help` after a catalog/version mismatch, a command absence, or an argument error.

## Decision table

| Situation | Action |
|---|---|
| Small, local, one-step change with no independent evidence need | Work directly. Do not create ceremonial delegation. |
| Bounded ticket requiring an isolated worktree, persistent evidence, independent review, or recovery | Use `agent-workflow` with a validated prompt pack. |
| Focused read-only investigation where a host-native subagent is explicitly preferred | Use the host-native mechanism and state that it is not an `agent-workflow` run. |
| User-visible child panes are required while the orchestrator is inside tmux | Invoke `agent-workflow launch`; never hand-create the tmux session or pane. |
| A running agent needs new guidance | Append `steer`; treat it as pending until a correlated executor acknowledgement exists. |

Select an agent class explicitly when the task differs from the configured
default. `exploratory` and `review` are non-interactive detached runs by
default. `implementation` starts interactive by default and must not be silently
downgraded. If the current tmux window is at capacity, let the application
report the count and explicitly offer closing idle panes, a structured
non-interactive fallback, or cancellation. Use the fallback only when the
operator chooses it; it becomes a structured evidence run. The application
validates the class against configured executor/model pairs and rejects no-go
models unless the caller supplies the explicit authorization flag.

Before every implementation launch, verify: current tmux window or dedicated
session context, configured pane capacity, idle reusable candidates, ticket and
pack identity, worktree, and whether the run needs structured post-run evidence.
The child must perform [`WORKTREE_PREFLIGHT.md`](../../docs/references/WORKTREE_PREFLIGHT.md)
as its first worktree action: verify the exact worktree, probe the optional
codebase-memory service once, and use its exact-worktree index when available.
If it is unavailable or permission-gated, the child records the limitation and
uses bounded RTK shell discovery without retrying. Launch, implementation,
review, and acceptance must never depend on MCP availability or silently
claim graph-backed analysis.

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

## Cross-run operational queries

Use the rebuildable SQLite projection for search and fleet analysis, never for authority:

```bash
agent-workflow index sync
agent-workflow index query runs --state possibly_stalled
agent-workflow index query incidents --category permission_wait
agent-workflow index query workflows --pack PACK_ID
agent-workflow index verify --full
```

A query result is a locator and summary. Reopen and verify the original run artifacts and receipts before interrupting, restarting, reviewing, accepting, merging, or changing policy. If index freshness or verification is not current, rebuild it; do not edit SQLite to repair source evidence.

## Review and acceptance

```bash
agent-workflow status project-p0-01 --capture 100
agent-workflow review project-p0-01 --actor reviewer --reason "Diff and gates independently checked"
agent-workflow accept project-p0-01 --actor reviewer --reason "Approved" --revision COMMIT_SHA
```

Terminal text is operational context, not sealed proof. Inspect the authoritative run evidence and receipts before review or acceptance. After integrating parallel tickets, apply the `release-drift-auditor` skill before phase acceptance or packaging.

## Canonical references

- [`docs/COMMAND_REFERENCE.md`](../../docs/COMMAND_REFERENCE.md)
- [`docs/OPERATIONS.md`](../../docs/OPERATIONS.md)
- [`docs/SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md`](../../docs/SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md)
- [`docs/PROMPT_PACKS.md`](../../docs/PROMPT_PACKS.md)
- [`docs/TESTING.md`](../../docs/TESTING.md)
- [`EXECUTION_PROTOCOL.md`](../../docs/references/EXECUTION_PROTOCOL.md)
- [`DELEGATION_RUNBOOK.md`](../../docs/references/DELEGATION_RUNBOOK.md)

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

An exported completion/final-receipt pair is not automatically a portable verified run: verify every receipt-listed artifact or record seal verification as unavailable. Keep completion validity, lifecycle sealing, evaluation artifacts, phase disposition, and cohort comparability separate.

A structured run is comparison-ready only when its bounded raw executor stream, provider evidence, metrics, completion, and final receipt are sealed and complete. Do not infer tokens or cost from prose/logs, add cached or reasoning details twice, or combine provider-billed and locally estimated cost.

The current `agent-workflow-mcp` adapter is local stdio and read-only. It exposes the live parser-derived command catalog, an explicit capability manifest, and verified run command context/cards; these are discovery and audit resources, not authorization. Do not claim planned MCP-003 mutation tools exist or derive tools dynamically from catalog entries. Any future MCP mutation must reuse shared services, durable idempotency, and the same launch service so MCP-launched children preserve launch-contract v2 command artifacts and digests.
