# Changed-files delivery

Relative to the previous `agent-workflow-0.1.8-mcp-server-next-completed-source.tar.zst` delivery.

Changed or added files: 67
Removed files: 0

## Changed or added

- `BACKLOG.md`
- `CHANGED_FILES.md`
- `CHANGELOG.md`
- `MANIFEST.sha256`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/MCP_SERVER_DECISION.md`
- `docs/MCP_SERVER_IMPLEMENTATION_REPORT.md`
- `docs/WORKFLOW_FOUNDATIONS_PLAN.md`
- `prompt-packs/mcp-server-next/CHATGPT_HANDOFF_PROMPT.md`
- `prompt-packs/mcp-server-next/MANIFEST.sha256`
- `prompt-packs/mcp-server-next/README.md`
- `prompt-packs/mcp-server-next/phase-0/task-manifest.yaml`
- `prompt-packs/mcp-server-next/phase-1/task-manifest.yaml`
- `prompt-packs/mcp-server-next/phase-2/task-manifest.yaml`
- `prompt-packs/mcp-server-next/phase-3/MASTER_IMPLEMENTATION_PROMPT.md`
- `prompt-packs/mcp-server-next/phase-3/README.md`
- `prompt-packs/mcp-server-next/phase-3/task-manifest.yaml`
- `prompt-packs/mcp-server-next/phase-3/tickets/P3-00-workflow-baseline.md`
- `prompt-packs/mcp-server-next/phase-3/tickets/P3-01-workflow-aware-tools.md`
- `prompt-packs/mcp-server-next/phase-3/tickets/P3-02-independent-review.md`
- `prompt-packs/workflow-foundations-next/CHATGPT_HANDOFF_PROMPT.md`
- `prompt-packs/workflow-foundations-next/DELEGATION_RUNBOOK.md`
- `prompt-packs/workflow-foundations-next/EXECUTION_PROTOCOL.md`
- `prompt-packs/workflow-foundations-next/MANIFEST.sha256`
- `prompt-packs/workflow-foundations-next/README.md`
- `prompt-packs/workflow-foundations-next/contracts/workflow-node-result.schema.json`
- `prompt-packs/workflow-foundations-next/pack.yaml`
- `prompt-packs/workflow-foundations-next/phase-0/MASTER_IMPLEMENTATION_PROMPT.md`
- `prompt-packs/workflow-foundations-next/phase-0/README.md`
- `prompt-packs/workflow-foundations-next/phase-0/task-manifest.yaml`
- `prompt-packs/workflow-foundations-next/phase-0/tickets/WF-00-contract-and-state.md`
- `prompt-packs/workflow-foundations-next/phase-0/tickets/WF-01-scheduler-service.md`
- `prompt-packs/workflow-foundations-next/phase-0/tickets/WF-02-restart-and-cli.md`
- `prompt-packs/workflow-foundations-next/phase-1/MASTER_IMPLEMENTATION_PROMPT.md`
- `prompt-packs/workflow-foundations-next/phase-1/README.md`
- `prompt-packs/workflow-foundations-next/phase-1/task-manifest.yaml`
- `prompt-packs/workflow-foundations-next/phase-1/tickets/WF-10-approval-gates.md`
- `prompt-packs/workflow-foundations-next/phase-1/tickets/WF-11-result-binding.md`
- `prompt-packs/workflow-foundations-next/phase-1/tickets/WF-12-workflow-receipt.md`
- `prompt-packs/workflow-foundations-next/phase-2/MASTER_IMPLEMENTATION_PROMPT.md`
- `prompt-packs/workflow-foundations-next/phase-2/README.md`
- `prompt-packs/workflow-foundations-next/phase-2/task-manifest.yaml`
- `prompt-packs/workflow-foundations-next/phase-2/tickets/WF-20-templates.md`
- `prompt-packs/workflow-foundations-next/phase-2/tickets/WF-21-routing-advice.md`
- `prompt-packs/workflow-foundations-next/phase-2/tickets/WF-22-integration-review.md`
- `prompt-packs/workflow-foundations-next/references/README.md`
- `prompt-packs/workflow-foundations-next/scripts/archive-prompt-pack.sh`
- `prompt-packs/workflow-foundations-next/scripts/check-delegation.sh`
- `prompt-packs/workflow-foundations-next/scripts/create-ticket-worktree.sh`
- `prompt-packs/workflow-foundations-next/scripts/foreground-delegation.sh`
- `prompt-packs/workflow-foundations-next/scripts/launch-delegation.sh`
- `prompt-packs/workflow-foundations-next/scripts/restart-delegation.sh`
- `prompt-packs/workflow-foundations-next/scripts/stop-delegation.sh`
- `prompt-packs/workflow-foundations-next/scripts/validate-prompt-pack.sh`
- `prompt-packs/workflow-foundations-next/templates/PHASE_GATE_REPORT.md`
- `prompt-packs/workflow-foundations-next/templates/TICKET_COMPLETION.md`
- `prompt-packs/workflow-foundations-next/templates/source-baseline.example.json`
- `schemas/task-manifest.schema.json`
- `schemas/task-result-collection.schema.json`
- `schemas/task-result.schema.json`
- `src/agent_workflow/manifests.py`
- `src/agent_workflow/receipts.py`
- `src/agent_workflow/runner.py`
- `src/agent_workflow/sessions.py`
- `tests/test_manifest_validation.py`
- `tests/test_runner_generation.py`

## Removed

None.

## Verification scope

- Revalidated the implemented dependency-DAG and structured-result foundations.
- Revalidated both prompt packs after explicit cross-phase dependency updates.
- Reordered remaining MCP mutation work behind completion of `WF-22`.
- Regenerated prompt-pack and repository release manifests.
