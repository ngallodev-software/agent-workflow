# MCP tool, resource, and prompt catalog

This catalog defines the proposed public surface. `Current` means implemented in the read-only stdio adapter; `MCP-003` and later rows are plans, not present capabilities.

## Tools

| Name | Phase | Mutating | Confirmation | Authority/service | Result state |
|---|---|---:|---:|---|---|
| `pack_validate` | Current | no | no | pack validator | completed/failed |
| `worktree_create` | MCP-003 | yes | yes | worktree service | completed/replayed/failed |
| `run_launch` | MCP-003 | yes | yes | canonical session launch | accepted/completed/replayed/failed |
| `workflow_validate` | MCP-003 | no | no | `WorkflowService.validate` | completed/failed |
| `workflow_start` | MCP-003 | yes | yes | `WorkflowService.start` | accepted/completed/replayed/failed |
| `workflow_status` | MCP-003 | no | no | workflow replay | completed/failed |
| `workflow_resume` | MCP-003 | yes | yes | `WorkflowService.resume` | completed/replayed/failed |
| `workflow_seal` | MCP-003 | yes | yes | aggregate receipt service | completed/replayed/failed |
| `workflow_verify` | MCP-003 | no | no | aggregate receipt verifier | completed/failed |
| `run_progress` | MCP-003 | yes | no | durable messages | completed/replayed/failed |
| `run_ack` | MCP-003 | yes | no | durable messages | completed/replayed/failed |
| `run_steer` | MCP-003 | yes | yes | durable messages | pending/replayed/failed |
| `run_interrupt` | MCP-004 | yes | yes | session control | completed/replayed/failed |
| `run_terminate` | MCP-004 | yes | yes | session control | completed/replayed/failed |
| `run_review` | MCP-004 | yes | yes | lifecycle service | completed/replayed/failed |
| `run_accept` | MCP-004 | yes | yes | lifecycle service | completed/replayed/failed |
| `run_reject` | MCP-004 | yes | yes | lifecycle service | completed/replayed/failed |

Excluded: raw shell, arbitrary command execution, arbitrary file read/write, force kill, merge, raw terminal capture, direct tmux APIs, model-policy bypass, and HTTP administration.

## Resources

| URI | Status | Bound |
|---|---|---|
| `agent-workflow://runs` | Current | paginated allowlisted summaries |
| `agent-workflow://runs/{run_id}/status` | Current | redacted typed status |
| `agent-workflow://runs/{run_id}/messages` | Current | sequence cursor and limit |
| `agent-workflow://runs/{run_id}/receipt` | Current | final receipt metadata, not arbitrary artifacts |
| `agent-workflow://workflows/{workflow_id}/status` | MCP-003 | replayed projection |
| `agent-workflow://workflows/{workflow_id}/receipt` | MCP-003 | aggregate receipt metadata |
| `agent-workflow://packs/{pack_id}/manifest` | MCP-003 | configured pack root only |
| `agent-workflow://requests/{request_id}` | MCP-003 | durable idempotency/result projection |

## Prompts

| Prompt | Phase | Purpose |
|---|---|---|
| `prepare_delegation` | MCP-003 optional | Produce a validated draft launch request; never launches implicitly. |
| `prepare_workflow` | MCP-003 optional | Produce one authorized template specification/canonical snapshot draft. |
| `review_run_evidence` | MCP-004 optional | Guide inspection of receipts, scope, commands, scores, and lifecycle evidence; never accepts implicitly. |

## Shared input rules

- IDs use the repository ID validator and bounded lengths.
- Text inputs are UTF-8, non-empty where required, and capped.
- Paths are configured-root logical references; traversal and symlinks are rejected.
- Unknown fields are rejected.
- Mutations require an idempotency key.
- Executor/model/class fields pass through canonical policy enforcement.
- Review/accept fields require actor, reason, and exact revision as applicable.

## Stable result envelope

```json
{
  "schema": "agent-workflow/mcp-result/v1",
  "request_id": "uuid",
  "action": "run_steer",
  "state": "pending",
  "replayed": false,
  "result_id": "message-uuid",
  "evidence": [{"kind": "message", "id": "message-uuid", "sha256": "…"}],
  "error": null
}
```
