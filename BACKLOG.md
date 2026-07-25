# agent-workflow Backlog

This is the authoritative register for unfinished repository work. Create,
prioritize, close, or defer tasks here; detailed design, acceptance criteria,
and prior-art evidence live in the linked reference documents. Historical
plans and implementation reports are not parallel task trackers.

## Operating rules

- Every active task has a stable ID, state, priority, owner type, and exit
  evidence. New work starts here before it is delegated.
- A task is `done` only after its stated evidence exists; move it to the
  completed history rather than leaving completed checkboxes in design docs.
- `blocked` tasks name the missing external input. They are not implementation
  authorization until that input is supplied.
- `decision` items require an explicit maintainer choice; do not turn them
  into infrastructure by default.
- Link here from a deep design document instead of copying its instructions.

## Now

| ID | Priority | State | Work and exit evidence | Reference |
|---|---|---|---|---|
| BKL-001 | P0 | ready | Add durable per-consumer control-log cursors and idempotent handling/disposition. Prove restart recovery, duplicate delivery safety, and cursor advancement only after handling succeeds. | [research: Stage A and Priority 2](docs/Durable_Orchestration_Delivery_Benchmarks.md#stage-a--single-host-tmux) |
| BKL-006 | P0 | done | Make `agent-workflow` operationally discoverable to agents: add an orchestration skill, connect existing skills to CLI/runbooks/protocols, define native-agent versus durable-run boundaries, and install/test supported discovery roots. | [P0 task breakdown](docs/AGENT_WORKFLOW_SKILL_INTEGRATION_P0.md) |
| BKL-002 | P0 | ready | Research, define, and implement executor-specific late steering for detached/non-interactive runs, starting with Codex and documenting the equivalent Claude capability boundary. A running agent must consume a post-launch steer (including a progress request) without restart, then emit correlated accepted, delivered, applied or rejected, and terminal evidence. Prove replay/idempotency and unavailable-adapter behavior; never infer delivery from logs, prose, tmux state, or terminal keystrokes. | [late-steering implementation ticket](docs/ORCHESTRATOR_MESSAGING_AND_EVALS_PLAN.md#late-steering-adapter-implementation-ticket) |
| BKL-003 | P1 | ready | Seal bounded raw executor stream evidence before normalization and add provider adapters that explicitly label usage as `delta`, `cumulative`, or `terminal`. Calibrate cached-token, reasoning-token, retry, and cost behavior against each supported executor. | [research: evidence principles and usage envelope](docs/Durable_Orchestration_Delivery_Benchmarks.md#evidence-principles) |
| BKL-004 | P1 | ready | Run a controlled real-executor deterministic cohort. Pin executor/model/environment/tool policy, record capability calibration, retain raw and sealed evidence, publish an explicit baseline/candidate manifest with exclusions, and run `agent-workflow eval compare`. | [research: cohort protocol](docs/Durable_Orchestration_Delivery_Benchmarks.md#real-executor-cohort-protocol) |
| BKL-005 | P1 | ready | Extend trial evidence only where a sealed provider receipt proves it: source digests, retry/re-steer/error accounting, provider-billed versus locally estimated cost, currency rules, and incomplete-trial rejection. Add schema and comparison tests for every new field. | [research: immutable trial evidence and cost rules](docs/Durable_Orchestration_Delivery_Benchmarks.md#immutable-trial-evidence-schema) |
| BKL-007 | P1 | ready | Add opt-in, installer-owned host routing enforcement: preserve existing hooks, block only exact raw delegation launch patterns, provide an audited break-glass path, and test Codex rules/instructions separately from Claude Code `PreToolUse` hooks. | [global routing decision](docs/GLOBAL_AGENT_ROUTING.md) |
| BKL-008 | P1 | done | Track bounded durable context and assignment history for interactive agents; require explicit completion, rank same-worktree candidates, and restrict automatic reuse to exact ticket/retry lineage with correlated acknowledgement. | [interactive reuse](README.md#reusing-an-interactive-agent) |

### Workflow foundations (must complete before remaining MCP mutation work)

The scoped architecture and explicit non-targets are defined in [Workflow Foundations Plan](docs/WORKFLOW_FOUNDATIONS_PLAN.md). Remaining implementation is executable through [workflow-foundations-next](prompt-packs/workflow-foundations-next/README.md). The exact prompt-pack ticket IDs below are canonical backlog tasks.

| ID | Priority | State | Depends on | Work and exit evidence | Reference |
|---|---|---|---|---|---|
| WF-001 | P0 | done | — | Make prompt-pack dependencies a validated cross-phase DAG: reject malformed, unknown, self, and cyclic dependencies. | [implemented foundation](docs/WORKFLOW_FOUNDATIONS_PLAN.md#dependency-graph-validation) |
| WF-002 | P0 | done | WF-001 | Add optional ticket-specific JSON result contracts, bounded handoff collection, schema validation, sealed result artifacts, and collection receipts. | [implemented foundation](docs/WORKFLOW_FOUNDATIONS_PLAN.md#structured-task-result-contracts) |
| WF-00 | P0 | done | WF-002 | Define the minimal workflow snapshot, event, node-state, retry-lineage, and service contracts. Exit with versioned schemas/contracts and focused validation tests. | [ticket](prompt-packs/workflow-foundations-next/phase-0/tickets/WF-00-contract-and-state.md) |
| WF-01 | P0 | done | WF-00 | Implement restart-safe dependency scheduling over the existing launch service with bounded parallelism and no alternate executor path. Exit with scheduler service tests covering dependency eligibility, failures, retries, and concurrency bounds. | [ticket](prompt-packs/workflow-foundations-next/phase-0/tickets/WF-01-scheduler-service.md) |
| WF-02 | P0 | done | WF-01 | Add workflow CLI/status/resume behavior and prove restart reconstruction from durable records. Exit with CLI, recovery, and interrupted-run tests. | [ticket](prompt-packs/workflow-foundations-next/phase-0/tickets/WF-02-restart-and-cli.md) |
| WF-10 | P1 | ready | WF-02 | Add receipt-backed approval gates that unblock only after a valid immutable review disposition for the expected revision. | [ticket](prompt-packs/workflow-foundations-next/phase-1/tickets/WF-10-approval-gates.md) |
| WF-11 | P1 | ready | WF-10 | Add bounded JSON Pointer result binding from validated child results, with type/size limits and no arbitrary file reads. | [ticket](prompt-packs/workflow-foundations-next/phase-1/tickets/WF-11-result-binding.md) |
| WF-12 | P1 | ready | WF-11 | Seal aggregate workflow receipts that commit to the workflow snapshot, event stream, node bindings, child final receipts, approvals, and terminal disposition. | [ticket](prompt-packs/workflow-foundations-next/phase-1/tickets/WF-12-workflow-receipt.md) |
| WF-20 | P1 | ready | WF-12 | Add only the three authorized reusable graph templates: pipeline, bounded parallel review with fan-in, and implementation followed by independent review. | [ticket](prompt-packs/workflow-foundations-next/phase-2/tickets/WF-20-templates.md) |
| WF-21 | P1 | ready | WF-20 | Add deterministic, explainable routing advice that remains subordinate to existing class, executor, model, and no-go policy enforcement. | [ticket](prompt-packs/workflow-foundations-next/phase-2/tickets/WF-21-routing-advice.md) |
| WF-22 | P1 | ready | WF-21 | Perform the integration, security, documentation, release-asset, and full-suite review for the complete workflow foundation. | [ticket](prompt-packs/workflow-foundations-next/phase-2/tickets/WF-22-integration-review.md) |
| WF-006 | P2 | deferred | BKL-003, BKL-004, BKL-005 | Consider evidence-derived routing recommendations only after sealed, comparable executor cohorts exist. No online learning or vector-memory dependency. | [routing boundary](docs/WORKFLOW_FOUNDATIONS_PLAN.md#5-explainable-routing-advice) |

### MCP server work (remaining mutation work follows WF-22)

The read-only local stdio MCP adapter is already implemented and remains valid. Do not implement the remaining mutation surface until `WF-22` is complete; MCP must wrap stable workflow and lifecycle services rather than create parallel orchestration semantics.

| ID | Priority | State | Depends on | Work and exit evidence | Reference |
|---|---|---|---|---|---|
| MCP-001 | P1 | done | — | Audit reusable domain seams and define typed MCP request/result contracts without changing CLI lifecycle semantics. MCP and CLI invoke shared service functions. | [implementation report](docs/MCP_SERVER_IMPLEMENTATION_REPORT.md) |
| MCP-002 | P1 | done | MCP-001 | Add the optional pinned official Python SDK dependency and local stdio server with bounded read-only run/pack resources, traversal/redaction controls, capability negotiation, and tests. | [implementation report](docs/MCP_SERVER_IMPLEMENTATION_REPORT.md) |
| MCP-003 | P1 | blocked | WF-22 | Add validated `pack_validate`, `worktree_create`, single-run `launch`, workflow validate/launch/status/resume, `progress`, `ack`, and `steer` tools through existing services. Require idempotency and durable evidence mapping; steering remains `pending` without correlated acknowledgement. | [MCP pack Phase 3](prompt-packs/mcp-server-next/phase-3/README.md) |
| MCP-004 | P2 | deferred | MCP-003 | Add policy-gated interrupt/terminate and review/accept/reject tools, then run representative-host and security evaluation. Workflow approvals must reuse workflow review receipts. | [MCP decision: MCP-3 and MCP-4](docs/MCP_SERVER_DECISION.md#phased-implementation-plan) |
| MCP-005 | P2 | decision | MCP-004 | Authorize or reject Streamable HTTP only after local stdio adoption and security evidence; require a separate authorization ADR before implementation. | [MCP decision: MCP-5](docs/MCP_SERVER_DECISION.md#conditional-http-evolution) |

## Blocked on supplied prerequisites

| ID | Priority | State | Missing input and exit evidence | Reference |
|---|---|---|---|---|
| BKL-010 | P1 | blocked | Provide a pinned browser-image digest, font manifest, and a verified pre-seal browser/Inspect evidence bridge. Then implement the priority-picker Playwright fixture with DOM, keyboard, ARIA, screenshot, and explicit child-lifecycle telemetry gates. | [blocked-gate report](docs/PHASE_3_BLOCKED_GATE_REPORT.md) |

## Decisions required before implementation

| ID | Priority | State | Decision required | Reference |
|---|---|---|---|---|
| DEC-001 | P0 | needs-decision | Set the durable-control service objective: storage location/failure model, ordering scope, producer model, exactly-once external-effect requirements, and maximum no-wakeup steering latency. Record the decision before changing journal topology. | [research: open questions 1-6](docs/Durable_Orchestration_Delivery_Benchmarks.md#open-questions) |
| DEC-002 | P1 | needs-decision | Set benchmark policy: required first executors, billing meaning, warm-cache role, replicate count/effect threshold, and handling of interrupted or human-assisted trials. | [research: open questions 9-14](docs/Durable_Orchestration_Delivery_Benchmarks.md#open-questions) |
| DEC-003 | P2 | deferred | Authorize multi-host orchestration only when a concrete cross-host consumer or local wakeup/scan service objective fails. If authorized, choose JetStream first unless an existing Redis dependency is mandated; retain the canonical durable record envelope and idempotency requirements. | [research: Stages B-D and Priorities 6-7](docs/Durable_Orchestration_Delivery_Benchmarks.md#recommended-staged-architecture) |
| DEC-MCP-001 | P1 | decided | MCP is optional and Python is the implementation language. | [MCP decision: approved decisions](docs/MCP_SERVER_DECISION.md#approved-maintainer-decisions) |
| DEC-MCP-002 | P1 | decided | Start with MCP Inspector/local stdio, protocol `2025-11-25`, and SDK `mcp==1.28.1`. | [MCP decision: approved decisions](docs/MCP_SERVER_DECISION.md#approved-maintainer-decisions) |
| DEC-MCP-003 | P1 | decided | Restrict access to configured repository, pack, worktree, and state roots. | [MCP decision: approved decisions](docs/MCP_SERVER_DECISION.md#approved-maintainer-decisions) |
| DEC-MCP-004 | P1 | decided | Omit destructive tools until MCP-3; force kill remains excluded. | [MCP decision: approved decisions](docs/MCP_SERVER_DECISION.md#approved-maintainer-decisions) |
| DEC-MCP-005 | P1 | decided | Use `mcp-stdio:<server-instance-id>` for local actor identity. | [MCP decision: approved decisions](docs/MCP_SERVER_DECISION.md#approved-maintainer-decisions) |
| DEC-MCP-006 | P1 | decided | Use optional `mcp` extra and `agent-workflow-mcp` entry point with public SDK APIs. | [MCP decision: approved decisions](docs/MCP_SERVER_DECISION.md#approved-maintainer-decisions) |
| DEC-MCP-007 | P1 | decided | Exclude raw terminal capture initially; any future view is bounded and observational. | [MCP decision: approved decisions](docs/MCP_SERVER_DECISION.md#approved-maintainer-decisions) |
| DEC-MCP-008 | P1 | decided | Require a separate authorization ADR before non-stdio transport. | [MCP decision: approved decisions](docs/MCP_SERVER_DECISION.md#approved-maintainer-decisions) |

## Deferred architecture

| ID | Priority | State | Work and trigger | Reference |
|---|---|---|---|---|
| ARC-001 | P2 | deferred | Add a transport-neutral advisory notifier interface with tmux and filesystem-watch adapters only after a latency/operability need is measured. Replay plus bounded reconciliation remains mandatory. | [research: Stage B](docs/Durable_Orchestration_Delivery_Benchmarks.md#stage-b--transport-neutral-notifier-interface) |
| ARC-002 | P3 | deferred | Add a reconstructable SQLite materialized index only when JSONL replay/scan cost is measured as a problem; never make two stores independently authoritative. | [research: Stage C](docs/Durable_Orchestration_Delivery_Benchmarks.md#stage-c--durable-record-indexing) |
| ARC-003 | P3 | deferred | Add a multi-host broker adapter, shared-artifact record references or canonical envelope replication, and cross-trust signing only after DEC-003. | [research: Stage D and open questions 7-8](docs/Durable_Orchestration_Delivery_Benchmarks.md#stage-d--optional-multi-host-broker) |

## Completed history

| ID | Completed in | Result | Evidence |
|---|---|---|---|
| HIST-001 | 0.1.5 | Durable fsynced control records, best-effort tmux wakeups, visible same-window panes, usage accumulation, verifier timing, and immutable `eval collect`/`eval compare` landed. | [implementation completion plan](docs/DURABLE_WAKEUP_AND_EVIDENCE_COMPLETION_PLAN.md), commit `6b61cbb` |
| HIST-002 | 0.1.6 | Global editable installer now installs core Python dependencies and retains its pip-managed launcher. | [installation guide](docs/INSTALLATION.md), commit `306c6f5` |

## Reference map

- [Durable orchestration and benchmark research](docs/Durable_Orchestration_Delivery_Benchmarks.md): prior art, recommended stages, evidence envelope, cost rules, cohort protocol, and open questions.
- [Messaging and regression-eval status](docs/ORCHESTRATOR_MESSAGING_AND_EVALS_PLAN.md): contracts and implemented/blocked status.
- [Wakeup and evidence completion plan](docs/DURABLE_WAKEUP_AND_EVIDENCE_COMPLETION_PLAN.md): completed implementation plan and acceptance history.
- [Visual-eval blocked gate](docs/PHASE_3_BLOCKED_GATE_REPORT.md): exact external prerequisites.
