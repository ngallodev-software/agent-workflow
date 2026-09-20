# Delegation Runbook

## Preflight

```bash
agent-workflow doctor
agent-workflow config show
python3 scripts/audit-release-assets.py
agent-workflow pack validate /path/to/prompt-pack
agent-workflow worktree create /path/to/repository TICKET-ID HEAD
```

Confirm the ticket's `backlog_id` is owned by exactly one active prompt pack and that all external prerequisites are complete before preparing an Agent Run.

Apply `docs/references/WORKTREE_PREFLIGHT.md` to the exact worktree. Optional discovery/indexing services remain operator conveniences and must not become runtime dependencies.

## Prepare and start Agent Runs

Tasks with no dependency edge may run concurrently in separate worktrees. Never place two workers in the same writable worktree.

Review dependencies are deliberately different from implementation dependencies. A normal implementation prerequisite must be host-accepted. An independent `review` run may start from a cryptographically verified, sealed, successfully completed prerequisite before host acceptance; otherwise review-before-acceptance would be circular. A prior explicit rejection still blocks that prerequisite.

`agent-run restart` is prepare-first. Use `--context-file corrective.md` to add immutable operator correction/context to the lineage retry and inspect the prepared run before `agent-run start RETRY`. Use `--start` only when no pre-start intervention is needed.

For Codex in a linked worktree, Agent-Workflow grants the sandbox both the per-worktree Git administrative directory and the repository common Git directory. This is required for commits because linked worktrees share objects and refs with the main repository; it does not grant unrelated repository paths.

Completion criterion results are exact parser choices: `pass`, `fail`, or `not_verified`. Prefer declaring every ticket criterion in root `pack.yaml` as `criteria: [{id, description}]` (or in a native job). Agent-Workflow freezes that catalog into the launch contract, rejects undeclared criterion IDs, and refuses terminal completion until every declared ID has an outcome. Workers do not write `completion.json`; they use `agent criterion`, `agent verify`, optional `agent limitation`, and `agent complete`, and Agent-Workflow atomically generates the schema-valid handoff. A dirty launch accepted with `--allow-dirty` is an operator-approved baseline; overlapping pre-existing drift alone is not a blocker, but unrelated drift must be preserved.

If an exact launch root contains `.agent-workflow-execution.toml`, Agent-Workflow auto-discovers it for `agent-run prepare` and `delegate` when `--config` is not supplied. The repo-local file is an execution overlay only: it may define agents/classes/executors/roles/runtime aliases, but cannot override host security, state paths, plugins, or other administrative policy.

New run handoffs live under Agent-Workflow state rather than inside the source checkout. This keeps `0700` runtime evidence out of Docker/build contexts and removes the need for repository-specific `.dockerignore` exclusions.

Controlled workers do not inherit the host's authenticated GitHub/service
credentials. Tickets that require privileged external mutation should produce
the exact requested mutation and local evidence, then let the authenticated
host perform the scoped action and record before/after evidence. Do not solve
this by mounting or copying host credential stores into the worker sandbox.

`--pack` may be the pack root path or its stable `pack_id`. `--job` may be a native JSON job path or a task ID from root `pack.yaml`; v1 Markdown packs should use the task ID form when they need an explicit job selector. A dirty checkout is never inferred to be safe: use `--allow-dirty` when pre-existing drift is deliberately part of the work and must be captured in the launch baseline.

For an Agent-Workflow-owned headless worker:

```bash
agent-workflow agent-run prepare project-ticket-a /path/to/worktree-a /path/to/pack/phase-0/tickets/TICKET-A.md \
  --ticket TICKET-A --pack /path/to/pack --role implementation --worker-mode headless
agent-workflow agent-run start project-ticket-a
```

For a future external interactive host, prepare only:

```bash
agent-workflow agent-run prepare project-ticket-b /path/to/worktree-b /path/to/pack/phase-0/tickets/TICKET-B.md \
  --ticket TICKET-B --pack /path/to/pack --role implementation --worker-mode external
```

The external host owns presentation and live interaction. Agent-Workflow remains authoritative for the Agent Run, durable messages, evidence, completion, evaluation, and review.

## Observe

```bash
agent-workflow agent-run list
agent-workflow agent-run status AGENT-RUN-ID
agent-workflow agent-run tail AGENT-RUN-ID
```

`possibly_stalled` is advisory. It means the worker is still observed as running while durable/log progress has not advanced during the configured threshold. Inspect evidence before interrupting it.

## Durable communication

Persist workflow instructions before attempting any live delivery:

```bash
agent-workflow agent-run steer AGENT-RUN-ID "Re-run the integration suite"
agent-workflow agent-run progress AGENT-RUN-ID --message "Integration suite running"
agent-workflow agent-run ack AGENT-RUN-ID MESSAGE-ID
```

Delivery by an external host is not an acknowledgement. The worker records the acknowledgement through Agent-Workflow.

## Retire verified runs

`agent-workflow agent-run list` is the active Agent Run view. Retire completed work only through the recoverable archive command; never delete a run directory by hand:

```bash
agent-workflow archive --all-verified --dry-run --json
agent-workflow archive AGENT-RUN-ID --verified --reason "accepted and no longer active"
```

The command rechecks durable evidence and accepted lifecycle state before moving the Agent Run from the active root to archive storage.

## Stall handling

1. Inspect `status` and `tail`.
2. Classify input wait, package/network wait, test deadlock, model loop, or legitimate long operation.
3. Interrupt without deleting evidence.
4. Correct the prompt or environment.
5. Restart into a new Agent Run so lineage remains explicit.

## Lifecycle controls

Only the workflow authority should issue semantic lifecycle controls:

```bash
agent-workflow agent-run interrupt AGENT-RUN-ID
agent-workflow agent-run terminate AGENT-RUN-ID --grace-seconds 8
agent-workflow agent-run restart AGENT-RUN-ID
agent-workflow agent-run start AGENT-RUN-ID-retry1
```

For headless workers, Agent-Workflow signals its owned process group. For externally hosted workers, Agent-Workflow records the requested semantic action for the host to reconcile. Controls preserve durable evidence.
The packaged `restart-delegation.sh` helper intentionally passes `--start` to
retain its historical one-shot remediation behavior; direct CLI restarts remain
prepare-first.

## Completion, integration, and review

Require a structured completion report. Integrate parallel tickets only after inspecting each complete diff and resolving overlap intentionally. Rerun shared acceptance journeys after integration.

Before the phase gate:

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate /path/to/prompt-pack
pytest
```

A high-risk implementer must not be the only reviewer. Actor labels alone do not prove reviewer independence.

## Deterministic worker completion

Normal implementation and review workers do not write protocol JSON. The worker
records semantic judgments and verification intent through constrained commands:

```bash
agent criterion RUN CRITERION pass --evidence "evidence"
agent criterion RUN HOST-RECEIPT pass --evidence-file GITHUB_PROMOTION_RECEIPT.md
agent limitation RUN live-github-fetch --evidence "controlled DNS unavailable"
agent verify RUN -- pytest -q
agent complete RUN --result completed
```

The executable owns enum validation, observed command exit status, identity,
Git revisions, changed-file derivation, schema construction, and terminal
handoff validation. The runner—not the worker—owns final collection and sealing.
Normal runner and recovery finalization invoke the same fixed terminal pipeline,
so recovery cannot reinterpret exit/completion/policy evidence differently.
A limitation is always recorded as `not_verified` and is non-gating; use it only for environment/harness constraints, never to hide a failed acceptance criterion. A reviewer may therefore approve receipt-backed evidence while separately preserving that a controlled live fetch, browser, listener, or sandbox command was unavailable.

Agent-Workflow 0.11 removes the legacy worker-facing `completion-validate` and `task-complete` commands. Workers use only `criterion`, `limitation`, `verify`, `complete`, and `completion-status`; `completion.json` is generated atomically by Agent-Workflow.
