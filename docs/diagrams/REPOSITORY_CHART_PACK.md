# agent-workflow repository chart pack

**Release:** 0.2.2
**Purpose:** current-state architecture, data/evidence model, execution flows, security boundaries, and planned MCP evolution.

Mermaid sources for the highest-value diagrams are also stored as individual `.mmd` files in this directory.

## 1. System context

```mermaid
flowchart LR
  Operator[Operator / orchestrator] --> CLI[agent-workflow CLI]
  AgentHost[Codex / Claude host] --> Skills[Installed workflow skills]
  Skills --> CLI
  CLI --> Core[Application services]
  Core --> Git[Git repositories + isolated worktrees]
  Core --> Tmux[tmux sessions/panes]
  Tmux --> Executors[Codex / Claude executors]
  Executors --> Artifacts[Run artifacts + JSONL evidence]
  Core --> Artifacts
  Core --> Workflow[Workflow graph scheduler]
  Workflow --> Core
  Reviewer[Independent reviewer] --> CLI
  CLI --> Receipts[Immutable receipts + lifecycle decisions]
  MCPHost[MCP host] --> MCP[Read-only stdio MCP adapter]
  MCP --> Core
```

## 2. Package/component map

```mermaid
flowchart TB
  cli[cli.py] --> config[config.py]
  cli --> sessions[sessions.py]
  cli --> workflow_service[workflow_service.py]
  cli --> lifecycle[lifecycle.py]
  cli --> messages[messages.py]
  cli --> evalpkg[eval/*]
  cli --> pack[pack.py/manifests.py]
  sessions --> executors[executors.py]
  sessions --> runner[runner.py]
  sessions --> tmux[tmux.py]
  sessions --> state[state.py]
  runner --> metrics[metrics.py]
  runner --> provider[provider_evidence.py]
  runner --> receipts[receipts.py]
  workflow_service --> scheduler[scheduler.py]
  scheduler --> workflow[workflow.py]
  scheduler --> routing[routing.py]
  scheduler --> bindings[bindings.py]
  scheduler --> approval[approval.py]
  workflow_service --> wf_receipt[workflow_receipt.py]
  approval --> lifecycle
  bindings --> receipts
  wf_receipt --> receipts
  evalpkg --> provider
  mcp[mcp/server.py] --> mcp_services[mcp/services.py]
  mcp_services --> state
  mcp_services --> messages
  mcp_services --> receipts
  contracts[contracts.py + schemas/] --> cli
  contracts --> sessions
  contracts --> workflow
  contracts --> evalpkg
```

## 3. Authority hierarchy

```mermaid
flowchart TB
  subgraph Authoritative
    Snapshot[Normalized workflow snapshot]
    Events[Append-only workflow events.jsonl]
    Control[Append-only control/messages JSONL]
    Raw[Bounded raw executor events]
    Final[Read-only final-receipt.json]
    Life[Read-only lifecycle receipt chain]
    WFR[Read-only workflow-receipt.json]
  end
  subgraph Derived
    Status[status.json]
    WFStatus[workflow-status.json]
    WFRun[workflow-run.json]
    Metrics[execution-metrics.json]
    Provider[provider-evidence.json]
    Trial[trial-evidence.json]
    Terminal[tmux capture / logs]
  end
  Snapshot --> WFStatus
  Events --> WFStatus
  Snapshot --> WFRun
  Events --> WFRun
  Raw --> Provider
  Provider --> Trial
  Final --> Trial
  Life --> WFStatus
  Final --> WFR
  Life --> WFR
  Snapshot --> WFR
  Events --> WFR
  Control --> Status
  Terminal -. observational only .-> Status
```

## 4. Session run artifact tree

```mermaid
flowchart TB
  Run[run/&lt;session-id&gt;]
  Run --> Prompt[prompt.md / launch-prompt.md]
  Run --> Command[command.json]
  Run --> Baseline[source-baseline.json]
  Run --> Provenance[run-provenance.json]
  Run --> Events[executor-events.jsonl]
  Run --> Logs[output.log / executor-stderr.log]
  Run --> Completion[completion.md + completion.json]
  Run --> Collections[collections/*]
  Run --> Result[result.json + task-result collection]
  Run --> Controls[control-events.jsonl / assignments.jsonl]
  Run --> Metrics[execution-metrics.json]
  Run --> Provider[provider-evidence.json]
  Run --> Status[status.json + final-status.json]
  Run --> Patch[patch.diff]
  Run --> Final[final-receipt.json]
  Run --> Scores[scores/*]
  Run --> Lifecycle[receipts/000001-reviewed.json ...]
  Final -->|hashes| Prompt
  Final -->|hashes| Command
  Final -->|hashes| Provenance
  Final -->|hashes| Events
  Final -->|hashes| Completion
  Final -->|hashes| Provider
```

## 5. Delegated run lifecycle

```mermaid
stateDiagram-v2
  [*] --> prepared
  prepared --> running: launch
  running --> completed: executor exit 0 + collection + seal
  running --> failed: nonzero/error/budget
  running --> interrupted: interrupt
  running --> killed: terminate/kill
  interrupted --> retry_prepared: restart
  failed --> retry_prepared: restart
  killed --> retry_prepared: restart
  retry_prepared --> running: new run ID, retry_of lineage
  completed --> reviewed: lifecycle receipt
  reviewed --> accepted: exact revision + valid evidence
  reviewed --> rejected: lifecycle receipt
  completed --> rejected: lifecycle receipt
  accepted --> [*]
  rejected --> [*]
```

## 6. Executor/runner evidence flow

```mermaid
sequenceDiagram
  participant S as Session service
  participant T as tmux/process
  participant E as Executor CLI
  participant R as Runner
  participant D as Run directory
  S->>D: write prompt, command, baseline, provenance
  S->>T: launch canonical runner command
  T->>E: configured argv + model/permissions
  E-->>R: stdout JSONL/text + stderr
  R->>D: append bounded executor-events.jsonl
  R->>D: write logs/completion/collections/patch
  R->>D: derive provider-evidence.json
  R->>D: derive execution-metrics.json
  R->>D: write final-status.json
  R->>D: under seal.lock, atomically install read-only final-receipt.json
  R-->>S: terminal result
```

## 7. Durable control/message flow

```mermaid
sequenceDiagram
  participant P as Parent/orchestrator
  participant J as fsynced message JSONL
  participant W as tmux wait-for hint
  participant C as Child/adapter
  P->>J: append steer(message_id) + fsync
  P->>W: best-effort wakeup
  C->>J: replay after cursor
  C->>J: append progress/ack(correlation_id) + fsync
  C->>W: best-effort wakeup
  P->>J: replay after cursor
  Note over P,C: Lost/coalesced wakeups do not lose records; journals are authoritative.
```

## 8. Workflow scheduler and replay

```mermaid
flowchart TD
  Load[Load read-only normalized snapshot] --> Replay[Shared-lock replay of contiguous workflow events]
  Replay --> Project[Reconstruct node/workflow state]
  Project --> Reconcile[Verify running child provenance or sealed terminal evidence]
  Reconcile --> RetryDeps[Reopen dependency-failed descendants when prerequisite retry changes state]
  RetryDeps --> FailDeps[Propagate current dependency failures]
  FailDeps --> Capacity[Subtract existing running nodes from parallelism budget]
  Capacity --> Eligible{Eligible pending nodes within capacity?}
  Eligible -->|approval node| Approval[Verify canonical lifecycle evidence]
  Eligible -->|task node| Inputs[Resolve sealed predecessor bindings]
  Approval --> Transition[Append node transition + fsync]
  Inputs --> Route[Compute advisory routing]
  Route --> Launch[Canonical session launch service]
  Launch --> Footprint{Matching durable child footprint exists?}
  Footprint -->|yes| Bind[Append running transition]
  Footprint -->|no| Recoverable[Append recoverable transition and fail closed]
  Bind --> Project
  Recoverable --> Project
  Transition --> Project
  Eligible -->|none| Terminal{All nodes terminal?}
  Terminal -->|no| Projection[Refresh workflow status/run projections]
  Terminal -->|yes| Seal[Seal aggregate workflow receipt]
```

## 9. Approval gate

```mermaid
flowchart LR
  Subject[Completed child run] --> Final[Canonical read-only final receipt]
  Subject --> Completion[Sealed completion + exact head revision]
  Subject --> Scores[Sealed score set when required]
  Final --> Review[000001-reviewed.json]
  Scores --> Review
  Review --> Accept[000002-accepted.json]
  Completion --> Accept
  Accept --> Chain[Reconstruct canonical contiguous lifecycle chain]
  Chain --> Gate{Digest, revision, score, independence valid?}
  Gate -->|yes| Open[Approval node completed]
  Gate -->|no| Closed[Approval node failed closed]
  Mutable[status.json state/tier/executor/digest/pointer] -. projection only .-> Chain
```

## 10. Result binding

```mermaid
flowchart LR
  Source[Completed predecessor node] --> Child[Bound child run]
  Child --> Receipt[Verify canonical final receipt]
  Receipt --> Result[Verify sealed result.json + collection digest]
  Result --> Pointer[Resolve strict RFC 6901 JSON Pointer]
  Pointer --> Bounds{Ancestor, required, per-value and total bounds valid?}
  Bounds -->|no| Fail[Fail closed; child not launched]
  Bounds -->|yes| Snapshot[Atomically install read-only parent binding snapshot]
  Snapshot --> Provenance[Atomically install read-only child workflow-inputs.json and bind digest in provenance]
  Provenance --> Launch[Launch child through canonical session service]
```

## 11. Workflow aggregate receipt

```mermaid
flowchart TB
  Snap[workflow-snapshot.json] --> Receipt[workflow-receipt.json]
  Journal[workflow-events.jsonl] --> Receipt
  Nodes[Exact node list/state/reason] --> Receipt
  History[Attempts/retry/binding history] --> Receipt
  Inputs[Input-binding digests] --> Receipt
  Child[Child final-receipt + completion digests] --> Receipt
  Approvals[Approval receipt digests] --> Receipt
  Receipt --> Verify[Rebuild from durable evidence and compare exactly]
  Verify --> ReadOnly[Atomically installed read-only under workflow.lock]
```

## 12. Authorized graph templates

```mermaid
flowchart TB
  subgraph Pipeline
    P1[step-1] --> P2[step-2] --> P3[step-3]
  end
  subgraph ParallelReviewFanIn
    I[implementation] --> R1[review-1]
    I --> R2[review-2]
    R1 --> F[fan-in]
    R2 --> F
  end
  subgraph ImplementationIndependentReview
    A[implementation] --> B[independent review]
    B --> G[approval gate]
  end
```

## 13. Deterministic routing advice

```mermaid
flowchart TD
  Node[Workflow node metadata] --> Classify{Keywords/risk/explicit class}
  Classify -->|research/discovery/spike| Exploratory[recommend exploratory]
  Classify -->|review/audit/security| Review[recommend review]
  Classify -->|otherwise| Implementation[recommend implementation]
  Exploratory --> Policy[Existing configured class/executor/model policy]
  Review --> Policy
  Implementation --> Policy
  Policy --> NoGo{No-go model?}
  NoGo -->|unauthorized| Reject[Reject]
  NoGo -->|allowed/none| Enforced[Record recommendation, enforced selection, explanation codes, disagreements]
```

## 14. Provider usage normalization

```mermaid
flowchart LR
  Raw[Stable regular non-symlink executor-events.jsonl] --> Hash[Bounded parse + complete raw SHA-256]
  Hash --> Identity[Provider event identity or duplicate ambiguity]
  Identity --> Classify{Provider/event boundary}
  Classify --> Delta[delta]
  Classify --> Cumulative[cumulative]
  Classify --> Terminal[terminal]
  Delta --> Merge[Merge rules]
  Cumulative --> Merge
  Terminal --> Merge
  Merge --> Complete{Consistent, finite, monotonic, identified, untruncated?}
  Complete -->|yes| Evidence[provider-evidence.json]
  Complete -->|no| Incomplete[Evidence with incomplete reasons]
  Evidence --> Seal[final-receipt.json]
  Seal --> Trial[trial-evidence/v2]
  Incomplete --> Reject[Trial extraction rejects]
```

## 15. Evaluation/cohort flow

```mermaid
flowchart TD
  Run[Sealed run] --> Extract[extract_trial]
  Extract --> Checks[Verify final seal + complete provider evidence + content-addressed score receipts]
  Checks --> Trial[Immutable trial record]
  Trial --> Baseline[Baseline cohort]
  Trial --> Candidate[Candidate cohort]
  Baseline --> Compare[eval compare]
  Candidate --> Compare
  Compare --> Validity{Same fixture/policy/currency/catalog?}
  Validity -->|yes| Stats[paired metrics, deltas, confidence/effect output]
  Validity -->|no| Exclusions[explicit excluded comparisons/reasons]
```

## 16. Prompt-pack execution model

```mermaid
flowchart LR
  Pack[pack.yaml + phase manifests] --> Validate[DAG/schema/checksum validation]
  Validate --> Phase[Ordered phase]
  Phase --> Ticket[Bounded ticket + writable paths + acceptance]
  Ticket --> Worktree[Isolated worktree]
  Worktree --> Run[Delegated run]
  Run --> Result[Structured task result + completion]
  Result --> Review[Independent review]
  Review --> Accept{Accepted?}
  Accept -->|no| Repair[Correction ticket/run]
  Repair --> Review
  Accept -->|yes| Gate[Phase gate + integration]
```

## 17. tmux topology and capacity

```mermaid
flowchart TB
  Window[Orchestrator tmux window]
  Window --> Left[Orchestrator pane]
  Window --> C1[Agent column 1]
  Window --> C2[Agent column 2]
  C1 --> A1[agent slot 1]
  C1 --> A2[agent slot 2]
  C1 --> A3[agent slot 3]
  C2 --> A4[agent slot 4]
  C2 --> A5[agent slot 5]
  C2 --> A6[agent slot 6]
  Detached[Non-interactive run] --> Dedicated[Dedicated detached session]
  Cap{Pane cap reached} --> Prompt[close explicit idle / detached / cancel]
```

## 18. CLI dispatch

```mermaid
flowchart LR
  Parser[argparse live parser] --> Doctor[doctor/config]
  Parser --> Worktree[worktree]
  Parser --> Launch[launch/list/status/attach/tail/restart/control]
  Parser --> Agent[agent reuse/context]
  Parser --> Workflow[workflow validate/start/status/resume/seal/verify/template]
  Parser --> Lifecycle[review/accept/reject]
  Parser --> Eval[eval collect/score/compare/report]
  Parser --> Pack[pack scaffold/validate/checksums/archive]
  Parser --> Completion[shell completion]
```

## 19. Release/install flow

```mermaid
flowchart LR
  Source[Git source checkout] --> Audit[audit-release-assets.py]
  Audit --> Manifest[MANIFEST.sha256]
  Source --> Tests[installed-wheel acceptance + invariant matrices]
  Source --> Static[release/schema/shell/compile checks]
  Manifest --> ReleaseCheck[scripts/release-check.sh]
  Tests --> ReleaseCheck
  Static --> ReleaseCheck
  ReleaseCheck --> Archive[deterministic tar.zst + SHA-256]
  Source --> Install[install.sh editable install]
  Install --> Launcher[~/.local/bin/agent-workflow]
  Install --> SkillLinks[shared/Codex/Claude skill symlinks]
```

## 20. Current and target MCP boundary

```mermaid
flowchart TB
  Host[MCP host]
  Host --> Stdio[Local stdio FastMCP]
  Stdio --> Current[Current: bounded read-only resources + pack_validate]
  Current --> Shared[Existing shared read services]
  Future[MCP-003 planned safe mutations] --> Idem[Durable idempotency journal]
  Idem --> SharedMut[Existing worktree/session/workflow/message services]
  Destructive[MCP-004 review/control] -. separately gated .-> SharedMut
  HTTP[MCP-005 Streamable HTTP] -. ADR required .-> Auth[OAuth/audience/origin/rate-limit boundary]
  Auth -. after decision .-> SharedMut
```

## 21. Evidence-oriented ERD

```mermaid
erDiagram
  PROMPT_PACK ||--o{ PHASE : contains
  PHASE ||--o{ TICKET : contains
  TICKET ||--o{ SESSION_RUN : executes_as
  SESSION_RUN o|--o| SESSION_RUN : retries
  SESSION_RUN ||--|| RUN_PROVENANCE : records
  SESSION_RUN ||--o{ EXECUTOR_EVENT : emits
  SESSION_RUN ||--o{ CONTROL_MESSAGE : exchanges
  SESSION_RUN ||--|| COMPLETION : produces
  SESSION_RUN ||--o| TASK_RESULT : produces
  SESSION_RUN ||--o| PROVIDER_EVIDENCE : normalizes
  SESSION_RUN ||--|| FINAL_RECEIPT : seals
  FINAL_RECEIPT ||--o{ LIFECYCLE_RECEIPT : reviewed_by
  WORKFLOW ||--|| WORKFLOW_SNAPSHOT : defined_by
  WORKFLOW ||--o{ WORKFLOW_NODE : contains
  WORKFLOW ||--o{ WORKFLOW_EVENT : records
  WORKFLOW_NODE o|--o| SESSION_RUN : binds
  WORKFLOW_NODE o{--o{ INPUT_BINDING : consumes
  WORKFLOW_NODE o|--o| LIFECYCLE_RECEIPT : gated_by
  WORKFLOW ||--o| WORKFLOW_RECEIPT : seals
  FINAL_RECEIPT ||--o{ TRIAL_EVIDENCE : supports
  PROVIDER_EVIDENCE ||--o{ TRIAL_EVIDENCE : supports
  TRIAL_EVIDENCE }o--|| COHORT : grouped_in
  COHORT }o--o{ COMPARISON : compared_by

  SESSION_RUN {
    string session_id PK
    string retry_of FK
    string status
    string worktree
  }
  WORKFLOW {
    string workflow_id PK
    string snapshot_sha256
    string state
  }
  WORKFLOW_NODE {
    string node_id PK
    string kind
    string state
    int attempt
  }
  FINAL_RECEIPT {
    string sha256 PK
    string session_id FK
    datetime sealed_at
  }
  WORKFLOW_RECEIPT {
    string sha256 PK
    string workflow_id FK
    string workflow_state
  }
```

## 22. Security trust boundaries

```mermaid
flowchart TB
  UserInput[Prompts/config/tool inputs] --> Validation[Schema + bounds + ID validation]
  Validation --> Policy[Configured roots + class/model/no-go policy]
  Policy --> Services[Application services]
  Services --> GitBoundary[Git/worktree boundary]
  Services --> ProcessBoundary[tmux/executor boundary]
  Services --> StateBoundary[Durable state boundary]
  ProcessBoundary --> Raw[Untrusted executor output]
  Raw --> Collector[Bounded collectors]
  Collector --> Seals[Immutable digests/receipts]
  StateBoundary --> Seals
  Seals --> Review[Independent review/acceptance]
```

## 23. Acceptance-first test architecture

```mermaid
flowchart TB
  Source[Clean source copy] --> Wheel[Build wheel]
  Wheel --> Venv[Install isolated virtualenv]
  Venv --> CLI[Invoke installed executables]
  CLI --> Journeys[Acceptance journeys]
  Journeys --> Git[Real Git/worktrees]
  Journeys --> Proc[External tmux/executor shims]
  Journeys --> State[Durable state and receipts]
  Invariants[Compact invariant matrices] --> Security[Path/seal/symlink rules]
  Invariants --> Replay[Message/workflow replay]
  Invariants --> Accounting[Provider/cohort accounting]
  Future[Strict xfail future journeys] --> Backlog[Approved backlog outcomes]
  Live[Opt-in live compatibility] --> RealHost[Real tmux/providers/MCP host]
  Release[Release checks] --> Distribution[schemas/help/shell/manifest]
```

## 24. Public release path

```mermaid
flowchart LR
  Core[Core CLI/workflow/evidence] --> Acceptance[Acceptance-first suite]
  Acceptance --> CI[Supported Python CI]
  CI --> Host[Clean-host live compatibility]
  Host --> Governance[License + security contact + ownership]
  Governance --> Metadata[Package/repository metadata]
  Metadata --> RC[Signed reproducible release candidate]
  RC --> Public[Supported public release]
  MCPMutation[MCP mutation] -. not a prerequisite .-> Public
  MultiHost[Multi-host orchestration] -. not a prerequisite .-> Public
```

## Diagram maintenance rule

Update this chart pack whenever a release changes a durable authority, package boundary, workflow state, public CLI family, MCP capability, evidence schema, or release/install flow. Historical plans may retain old diagrams only when clearly labeled as historical.
