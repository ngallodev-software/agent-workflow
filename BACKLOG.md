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
| BKL-006 | P0 | ready | Make `agent-workflow` operationally discoverable to agents: add an orchestration skill, connect existing skills to CLI/runbooks/protocols, define native-agent versus durable-run boundaries, and install/test supported discovery roots. | [P0 task breakdown](docs/AGENT_WORKFLOW_SKILL_INTEGRATION_P0.md) |
| BKL-002 | P0 | ready | Define and implement an executor-specific late-steering adapter for at least one supported executor. It must expose request accepted, delivered/applied, rejected, and terminal states through durable receipts; no terminal keystroke inference. | [messaging delivery boundary](docs/ORCHESTRATOR_MESSAGING_AND_EVALS_PLAN.md#delivery-boundary) |
| BKL-003 | P1 | ready | Seal bounded raw executor stream evidence before normalization and add provider adapters that explicitly label usage as `delta`, `cumulative`, or `terminal`. Calibrate cached-token, reasoning-token, retry, and cost behavior against each supported executor. | [research: evidence principles and usage envelope](docs/Durable_Orchestration_Delivery_Benchmarks.md#evidence-principles) |
| BKL-004 | P1 | ready | Run a controlled real-executor deterministic cohort. Pin executor/model/environment/tool policy, record capability calibration, retain raw and sealed evidence, publish an explicit baseline/candidate manifest with exclusions, and run `agent-workflow eval compare`. | [research: cohort protocol](docs/Durable_Orchestration_Delivery_Benchmarks.md#real-executor-cohort-protocol) |
| BKL-005 | P1 | ready | Extend trial evidence only where a sealed provider receipt proves it: source digests, retry/re-steer/error accounting, provider-billed versus locally estimated cost, currency rules, and incomplete-trial rejection. Add schema and comparison tests for every new field. | [research: immutable trial evidence and cost rules](docs/Durable_Orchestration_Delivery_Benchmarks.md#immutable-trial-evidence-schema) |

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
- [Implementation report](IMPLEMENTATION_REPORT.md): historical archive-overlay review and validation evidence.
