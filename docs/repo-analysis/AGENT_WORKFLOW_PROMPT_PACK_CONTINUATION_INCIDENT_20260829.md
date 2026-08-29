# Agent-Workflow prompt-pack continuation incident — 2026-08-29

## Scope

This report records the attempted continuation of OSINT Suite prompt-pack task
`TASK-001` after its first external implementation run completed with
uncommitted changes. It is an incident record, not an acceptance decision.

Affected prompt pack:

```text
/lump/apps/osint-suite/implementation-output/repo-simplification-20260829/prompt-pack
```

Affected worktree:

```text
/lump/worktrees/osint-simplification-task-001
```

Original Agent Run:

```text
specgen-e77d7d5fc8268e78
```

Continuation Agent Run:

```text
specgen-e77d7d5fc8268e78-retry-01
```

## Executive result

The original run published a schema-valid completion record, but it did not
produce revision-bound implementation evidence: its four reported changed
files remained uncommitted and its `head_revision` equalled its launch
`base_revision`. A direct steering request was correctly rejected because the
run was terminal. The supported lineage-restart command then failed because
the recorded `bridge` profile cannot use an explicit command.

A fresh external run could be prepared against the dirty worktree only with
`--allow-dirty`. Its corrective instruction was durably queued, but the
generated `run.sh` was not executable in either mode it generated:

- without a terminal it failed with `Error: stdin is not a terminal`;
- with a terminal it passed an unsupported `--interactive` argument to
  `agent_workflow.runner`.

The continuation worker never acknowledged the steering instruction and did
not run. The continuation run is terminally failed with
`failure_category: command_not_found` and
`completion_validation_status: missing`.

## Expected lifecycle

```text
prepare external run
  -> persist steering
  -> launch returned external contract
  -> worker acknowledges steering
  -> worker commits scoped changes
  -> worker publishes revision-bound completion
  -> evaluation
  -> independent review
  -> authorized acceptance
```

## Observed lifecycle

```text
original external run completed
  -> uncommitted worktree remained
  -> terminal run rejected steering                         [expected]
  -> restart lineage rejected by bridge profile             [defect]
  -> fresh dirty-worktree run prepared with --allow-dirty
  -> steering persisted, delivery queued
  -> generated launcher failed without TTY                  [defect]
  -> generated launcher failed with TTY                     [defect]
  -> no acknowledgement, no worker execution, failed run
```

## Evidence

### 1. Prompt-pack validity and original run state

The prompt pack validated successfully:

```text
phases: 3; tasks: 7; valid: True
```

`TASK-001` was dependency-free and assigned to
`specgen-e77d7d5fc8268e78` in external worker mode. Its durable final status
was:

```text
status: completed
observed_state: completed
completion_validation_status: valid
final_receipt_sha256: a7f038b830a521cdfa6ec481ec878cc4ba19ac8e2376f850af3bf00e6b44fcca
```

The public run summary correctly showed that completion is not acceptance:

```text
completion: {"head_revision": "af7cd1ce...", "present": true,
             "result": "completed", "validation_status": "valid"}
evaluation: {"passed": null, "present": false, "state": "not_planned"}
review: {"state": null}
policy_result: not_evaluated
```

### 2. Completion evidence was not revision-bound

The original completion sidecar claimed these changes:

```json
"changed_files": [
  ".gitignore",
  "apps/pipeline/.gitignore",
  "apps/suite/.gitignore",
  "apps/wayback-osint/.gitignore"
]
```

It nevertheless recorded the same SHA for both revisions:

```json
"base_revision": "af7cd1ce6c79b0017fa3c14554807716e9e53feb",
"head_revision": "af7cd1ce6c79b0017fa3c14554807716e9e53feb"
```

At the same time, the assigned worktree reported those exact four paths as
modified and uncommitted:

```text
 M .gitignore
 M apps/pipeline/.gitignore
 M apps/suite/.gitignore
 M apps/wayback-osint/.gitignore
```

This conflicts with the generated completion guidance, which says an
implementation agent must commit source changes before publishing a
`completed` sidecar and must bind `head_revision` to that commit. Completion
validation accepted it anyway.

Impact: a completion gate can report `valid` even though it does not identify
the revision containing the claimed implementation. Review and acceptance must
remain blocked.

### 3. Direct steering of the terminal run was correctly refused

The attempted durable steering command was:

```text
agent-workflow agent-run steer specgen-e77d7d5fc8268e78 "Continue TASK-001 ..." --actor parent
```

Observed result:

```text
error: cannot send a control message to a terminal Agent Run
```

This behavior is correct. Terminal execution evidence must not be rewritten;
continuation requires a lineage restart or a new run.

### 4. The documented restart path fails for the persisted profile

The documented restart form was attempted with a new run ID:

```text
agent-workflow agent-run restart specgen-e77d7d5fc8268e78 \
  --new-agent-run-id specgen-e77d7d5fc8268e78-retry-01
```

Observed result:

```text
error: agent profile 'bridge' cannot use an explicit command
```

Impact: a terminal external run with this recorded profile cannot use the
public recovery command advertised by Agent-Workflow. The operator must bypass
lineage recovery and create an unrelated fresh delegation.

### 5. Fresh delegation requires an explicit dirty-worktree exception

The first fresh external delegation attempt failed as designed:

```text
error: delegate stage 'agent-run-prepare' failed: worktree is dirty:
/lump/worktrees/osint-simplification-task-001; commit/stash changes or pass
--allow-dirty
```

Adding `--allow-dirty` prepared the continuation run. This was necessary only
because the prior valid completion left its own implementation uncommitted.

The resulting run had:

```text
agent_run_id: specgen-e77d7d5fc8268e78-retry-01
worker_mode: external
state: prepared
dirty_at_launch: true
```

### 6. Corrective steering was persisted but not acknowledged

The following instruction was durably queued before launch:

```text
Continue TASK-001 from the existing dirty worktree: commit only the four scoped
.gitignore changes; rerun validation; then publish completion evidence whose
head_revision is the commit. Do not touch unrelated files.
```

Agent-Workflow recorded it as:

```text
message_id: 8f5b6941-72bd-4cd2-af60-bbffd46372c3
direction: parent_to_child
kind: steer
delivery_outcome: queued
```

No worker acknowledgement exists because the worker process never started.

### 7. Generated external contract fails without a terminal

The external delegation returned a structured launch contract pointing to:

```text
/home/nate/.local/state/agent-workflow/runs/
specgen-e77d7d5fc8268e78-retry-01/run.sh
```

Executing that exact script without a TTY failed:

```text
Error: stdin is not a terminal
```

The script's non-TTY branch invokes a Codex command form that requires an
interactive standard input, so it cannot service automation or a headless
external host.

### 8. Generated external contract fails with a terminal

Executing the same returned script with a TTY failed earlier in the Agent
Workflow runner:

```text
usage: runner.py [-h] --run-dir RUN_DIR [--command-b64 COMMAND_B64]
runner.py: error: unrecognized arguments: --interactive
```

The generated TTY branch is equivalent to:

```text
python -m agent_workflow.runner --run-dir RUN_DIR --command-b64 VALUE --interactive
```

but the runner's parser does not define `--interactive`.

Impact: the public external launch contract is self-inconsistent. The non-TTY
branch invokes an interactive worker; the TTY branch gives an unsupported flag
to its wrapper. Neither branch starts the worker.

### 9. Final continuation-run status

After the failed launch attempts, Agent-Workflow reported:

```text
status: failed
observed_state: failed
failure_category: command_not_found
durable_failure_category: command_not_found
completion_validation_status: missing
next_action: agent-workflow agent-run restart specgen-e77d7d5fc8268e78-retry-01
```

The suggested next action is not currently viable: the same public restart
path already fails for the `bridge` profile.

## Root-cause assessment

| Defect | Immediate cause | Consequence |
|---|---|---|
| Completion validation gap | Validation accepts unchanged revision IDs with non-empty changed files | False confidence at the completion gate |
| Restart profile incompatibility | `bridge` cannot reconstruct/use an explicit command | Terminal external runs cannot create proper retry lineage |
| Non-TTY contract mismatch | Generated command requires a terminal | Headless external launch fails |
| TTY contract mismatch | Script passes `--interactive` to a parser that does not support it | Interactive external launch fails |
| Misleading recovery action | Status recommends `restart` despite profile incompatibility | Operator is directed to a known failing path |

## Minimal remediation

1. Reject a `completed` implementation sidecar when `changed_files` is nonempty
   and `head_revision == base_revision`, unless an explicit no-commit policy is
   part of the immutable task contract.
2. Make `agent-run restart` reconstruct the external launch data recorded for
   `bridge`, or reject preparation of a profile that cannot be restarted.
3. Generate a coherent launcher:
   - either implement `--interactive` in `agent_workflow.runner`, or stop
     emitting it;
   - make the non-TTY branch use a noninteractive Codex execution form.
4. Exercise each generated external `run.sh` under TTY and non-TTY conditions
   in an integration test. Assert a durable `running` transition and a worker
   acknowledgement, not merely script generation.
5. Suppress `restart` from `safe_actions` when profile validation proves it
   cannot work, and expose the reason in status output.

## Required retest

After repair, demonstrate this sequence in a disposable worktree:

1. Prepare an external implementation run.
2. Persist steering before launch.
3. Launch the returned contract both from TTY and non-TTY hosts as supported.
4. Confirm `prepared -> running`, receipt of the steering message, and a
   correlated acknowledgement.
5. Commit one scoped change.
6. Publish completion with a head revision different from the base revision.
7. Verify validation rejects the same fixture after replacing the head revision
   with the base revision.
8. Complete independent evaluation/review/acceptance as separate gates.

## Current disposition

No acceptance is authorized. The first run's build/release evidence may be
useful for a future implementation run, but it is not revision-bound. The
second run failed before it could make or validate any implementation change.

## Remediation implemented

Completion collection now rejects a completed result that claims changed files
while binding both revisions to the same launch HEAD. Restart reconstructs the
recorded agent identity with its saved command, including legacy external
profiles such as `bridge`, so lineage recovery does not select an unrelated
profile.

External launchers now use the runner contract consistently: terminal hosts use
the recorded interactive command, while non-terminal hosts select the
persisted non-interactive provider command. The runner validates the matching
command digest in either mode. Regression coverage protects the revision
invariant and external lifecycle contract; full disposable-host TTY and
non-TTY execution remains part of the release retest matrix.
