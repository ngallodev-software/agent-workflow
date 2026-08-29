# Agent-Workflow delegation and external lifecycle diagnosis — 2026-08-29

## Scope

Read-only diagnosis of the blocking failures encountered while delegating the
OSINT Suite simplification prompt-pack through Agent-Workflow. No Agent-Workflow
source, configuration, run-state evidence, or external system was modified.

## Executive result

There are two confirmed defects and one separate environment hazard:

1. `agent-workflow delegate` fails at import time because of a stale internal
   import.
2. External workers cannot reach structured completion because the public
   lifecycle has no supported `prepared -> running` transition for an external
   host.
3. Direct Python diagnostics can import an older globally installed package
   rather than the current `src/` checkout, making diagnosis/reproduction
   misleading if the imported path is not proved.

The first is a small regression. The second is a product-contract gap: external
workers are documented as able to consume a prepared run, yet the public
authority surface cannot record that the external host started the worker, and
therefore correctly refuses worker completion. The third is not the cause of
the observed source-checkout `delegate` failure, but it can conceal or confuse
future diagnosis.

## 1. Confirmed stale import in `delegate`

### Symptom

The normal delegation facade fails before creating/starting the Agent Run:

```text
ImportError: cannot import name 'synchronize_projection' from 'agent_workflow.state'
```

### Evidence

- `src/agent_workflow/delegation.py:13-14` imports
  `authoritative_execution_status` from `.run_lifecycle`, but imports
  `synchronize_projection` from `.state`.
- `src/agent_workflow/run_lifecycle.py:187` defines
  `synchronize_projection`.
- `src/agent_workflow/delegation.py:59` calls it while refreshing the status
  projection during idempotent existing-run delegation.
- Reproduction against the current checkout:

  ```bash
  PYTHONPATH=/lump/apps/agent-workflow/src \
    python3 -c 'import agent_workflow.delegation'
  ```

  This raises the same `ImportError`.
- History shows the symbol move in commit `680e15f`
  (`refactor: finalize headless documentation cleanup`), which introduced
  `run_lifecycle.py`; `delegation.py` was later added in `760899a`
  (`refactor: complete phase 2 skill-first surface`) with the stale `.state`
  import.

### Minimal repair

```python
from .run_lifecycle import authoritative_execution_status, synchronize_projection
from .state import run_dir
```

Do not restore `synchronize_projection` as a compatibility export from
`state.py`: that would recreate the old lifecycle/state boundary instead of
correcting its sole stale consumer.

### Required regression coverage

1. Import smoke: `import agent_workflow.delegation` succeeds from the intended
   source/wheel artifact.
2. Delegation idempotency: exercise `_matching_existing_run()` and verify it
   refreshes the mutable projection from the authoritative lifecycle evidence.
3. Product-level delegation journey: invoke the public `delegate` CLI once so
   packaging/import wiring is covered as well as the module import.

## 2. Confirmed external-worker lifecycle gap

### Intended lifecycle

The documented external-worker model is:

```text
prepare external Agent Run
  -> external host launches worker
  -> Agent-Workflow records running
  -> worker publishes task-complete
  -> completion, evaluation, review, acceptance
```

Agent-Workflow intentionally does not own the external process, terminal, or
host topology. That separation is correct. The missing step is a durable,
host-facing way to record the external worker's start without giving that host
authority to rewrite provenance or terminal lifecycle outcomes.

### Current behavior and evidence

- External preparation intentionally yields `prepared`:
  `tests/acceptance/test_cli_product_journeys.py:123-142` asserts this.
- `src/agent_workflow/agent_runs.py:1253-1260` rejects `agent-run start` for
  all non-headless Agent Runs:

  ```text
  external Agent Runs must be launched by an external host
  ```

- `src/agent_workflow/agent_context.py:158-166` requires authoritative status
  `running` or `interruption_requested` for `agent task-complete`; it explicitly
  rejects `prepared` with:

  ```text
  task completion requires a running Agent Run
  ```

- `src/agent_workflow/external_bindings.py:134-187` provides
  `bind-external`, but it only writes the host-neutral external-worker binding
  projection/journal.
- `docs/EXTERNAL_WORKER_BINDING.md:16-31,58-65` explicitly says that binding
  is non-authoritative and cannot transition lifecycle state.
- `src/agent_workflow/run_lifecycle.py` already permits and authoritatively
  records the `prepared -> running` transition; the lifecycle authority tests
  cover the generic transition in
  `tests/invariants/test_run_lifecycle_authority.py:40-58`.

Therefore, `bind-external` followed by `agent task-complete` must fail: no
public command can record the required running transition. This is not a stale
status projection and cannot be repaired by editing `status.json`.

### Minimal safe product repair

Add an explicit host-facing command/API, for example:

```text
agent-workflow agent-run start-external RUN RUNTIME_TYPE WORKER_ID --generation N
```

Its required behavior:

1. Require `worker_mode=external`.
2. Require an active external binding whose runtime type, worker ID, and
   generation exactly match the supplied values.
3. Transition only through
   `transition_execution(..., "running", actor=<recorded-host>, reason=...)`.
4. Append durable lifecycle evidence for the start; refresh the projection only
   from that authority.
5. Remain idempotent for the same active binding and reject stale/rebound
   generations.
6. Leave `bind-external` as a non-authoritative binding operation. Binding must
   not implicitly start the run.
7. Continue to leave `interrupt` and `terminate` unavailable for external
   workers unless a separately designed host-control capability is approved.

Do **not** loosen `agent task-complete` to accept `prepared`. That would permit
completion with no durable worker-start evidence and would bypass the execution
lifecycle authority.

### Required regression coverage

1. Extend
   `tests/acceptance/test_cli_product_journeys.py:test_external_prepare_is_host_independent_and_process_control_is_unavailable`
   with:

   ```text
   prepare -> bind external -> start external -> status running
   -> valid completion handoff -> task-complete
   ```

2. In `tests/invariants/test_run_lifecycle_authority.py`, assert exactly one
   `prepared`, then `running`, lifecycle chain for a valid external start.
3. Add negative cases: missing binding, mismatched runtime/worker, stale
   generation, and a prepared external run calling `task-complete` all fail.
4. Add an external-binding idempotency/rebind test proving that a replaced
   generation cannot start or complete against the prior binding.
5. Add a boundary test near
   `tests/invariants/test_agent_run_control_boundary.py:98` showing that the
   explicit external-start bridge is allowed while host process-control actions
   remain unavailable.

## 3. Source-versus-installed import hazard

### Evidence

From the Agent-Workflow checkout, unqualified Python imports a globally
installed package:

```bash
python3 - <<'PY'
import agent_workflow
print(agent_workflow.__file__)
PY
```

Observed path:

```text
/home/nate/.local/lib/python3.13/site-packages/agent_workflow/__init__.py
```

The source checkout uses `src/` layout. Running against source explicitly
imports the current checkout and reproduces the stale import defect:

```bash
PYTHONPATH=/lump/apps/agent-workflow/src python3 - <<'PY'
import agent_workflow
print(agent_workflow.__file__)
import agent_workflow.delegation
PY
```

The `agent-workflow` console script is executed by the shared agent-tools venv,
so every repair must be verified against both the intended source checkout and
the exact installed wheel/editable artifact used by the console entry point.

### Recommendation

Make diagnostic and developer instructions prove import origin, for example:

```bash
PYTHONPATH="$PWD/src" python3 -m agent_workflow.cli --help
python3 -m build --wheel --no-isolation
```

Then install the exact wheel in an isolated target/venv and verify its entry
points and imports. Do not treat a bare `python3 -c 'import agent_workflow'`
as checkout evidence.

This environment hazard is separate from the confirmed stale import in the
current source, but it can cause a test or operator to inspect an older package
and reach the wrong conclusion.

## Repair order

1. Correct the stale `delegation.py` import and add the import/idempotent
   delegation tests.
2. Design and implement the narrow `start-external` lifecycle bridge with
   binding/generation checks and positive/negative acceptance coverage.
3. Standardize source-versus-installed diagnostic instructions and add an
   installed-product delegation test that proves the actual import path.
4. Run the focused tests first, then the repository's canonical offline/release
   authority checks. Do not claim external-worker acceptance from a worker
   process, a binding record, or a test pass alone; completion, evaluation,
   independent review, and acceptance remain separate gates.

## Suggested focused validation commands

```bash
cd /lump/apps/agent-workflow

PYTHONPATH="$PWD/src" python3 -c 'import agent_workflow.delegation'

python3 -m pytest -q \
  tests/acceptance/test_delegation_journeys.py \
  tests/acceptance/test_cli_product_journeys.py \
  tests/invariants/test_run_lifecycle_authority.py \
  tests/invariants/test_agent_run_control_boundary.py

python3 -m build --wheel --no-isolation
```

After a wheel build, install the exact wheel in an isolated target/venv and
exercise the public `agent-workflow delegate` and external lifecycle journey.
The worktree must remain clean except for the intended repair before any
completion/review/acceptance claim.

## Diagnostic method and limitations

- A fresh exact-worktree `codebase-memory-mcp` full index was used with
  persistence disabled; `git status --porcelain` was identical before and
  after indexing.
- Structural graph evidence identified the live `prepare`, `delegate`,
  `complete_task`, `synchronize_projection`, and external-binding paths.
- Three independent Luna read-only investigations corroborated the stale import
  and the missing external start transition.
- No source changes, test changes, package installation, deployment, external
  worker launch, or lifecycle-state mutation was performed by this diagnosis.

## Addendum: prompt-pack delegation retry (2026-08-29)

### What was attempted

The valid `osint-suite-repo-simplification-20260829` prompt pack was retried
at its dependency-free `TASK-001`, using its recorded Agent Run
`specgen-e77d7d5fc8268e78` and source revision
`af7cd1ce6c79b0017fa3c14554807716e9e53feb`.

The ordinary facade invocation, which defaults to headless mode, failed before
launch with:

```text
error: delegate stage 'existing-run-validation' failed: agent run ID already
exists with different immutable inputs: worker_mode
```

The documented external form reused the existing run successfully:

```text
worker_mode: external
state: prepared
reused_existing_run: True
worktree_created: False
```

However, it returned only prose next actions, not an executable launch command.
The actual contract was discoverable only by separately inspecting the private
run directory, where `run.sh` invoked the configured external Codex/Luna
worker. Executing that contract transitioned the durable run from `prepared`
to `running` and produced worker heartbeat/executor events.

### Corrected lifecycle finding

The earlier conclusion that there is no external start transition is too broad
for this installed product version. A transition exists, but is implicit in the
generated external launch script rather than available as a public,
discoverable Agent-Workflow command. The resulting defect is still material:

1. `delegate` hides a necessary launch artifact while asking the caller to
   launch it.
2. Replaying a prepared external run with the default facade produces an
   opaque immutable-input error instead of reporting the existing worker mode
   and the exact compatible retry command.
3. The public CLI/API contract remains unable to record an external start
   without the host-local generated script, weakening host independence and
   recoverability.

The minimal remediation is to return a structured `launch_contract` object
from external `delegate` output, including the exact script/argv, worktree,
run ID, and transition semantics. On immutable worker-mode mismatch, report
the recorded mode and a compatible command. A public `start-external` command
remains preferable for host-independent recovery, but it is no longer required
to explain the observed `prepared -> running` transition.

### Additional integration issues observed

- The external worker startup logged a model-catalog decode failure:
  `missing field truncation_policy`. It nevertheless started work. The error
  printed the multi-megabyte raw catalog response, including base instructions,
  to stderr. Bound/redact diagnostic bodies before exposing terminal output.
- `rtk find` accepted the command but ignored GNU `-printf`. This is a wrapper
  compatibility limitation, not an Agent-Workflow lifecycle failure; callers
  needing formatted `find` output must use plain `find` or a supported `rtk`
  form.

No completion, evaluation, review, or acceptance is claimed by this addendum.

## Resolution verification (2026-08-29)

The identified implementation and test gaps are now closed:

- `delegation.py` imports `synchronize_projection` from `run_lifecycle`.
- External delegation exposes a structured `launch_contract` containing the
  runner argv, worktree, and binding/start command templates.
- `agent-run start-external` records only a binding- and generation-matched
  `prepared -> running` transition and is idempotent for the active binding.
- Missing bindings, mismatched workers, stale generations, and external host
  process-control attempts are covered by acceptance and invariant tests.
- Source import, installed public `delegate`, and immutable retry-mode errors
  are covered by release and acceptance tests.

The remaining model-catalog decode output and `rtk find -printf` behavior are
environment/tooling issues, not lifecycle authority defects. No completion,
evaluation, review, or acceptance is inferred from these test results.

### Completion-integrity observation (2026-08-29)

The external run later reached `status: completed` with a schema-valid
`completion.json` and an acceptance claim for `AC-001`. Its completion sidecar
lists four changed `.gitignore` files, but records identical base and head
revisions (`af7cd1ce6c79b0017fa3c14554807716e9e53feb`). The assigned worktree
still reports those same four files as modified and uncommitted.

This conflicts with the generated completion guidance, which requires an
implementation worker to commit changes before publishing a completed sidecar
and bind `head_revision` to that commit. Completion validation nevertheless
reported `valid`. Therefore the run is complete only at the worker/completion
gate; it must not be reviewed or accepted as a revision-bound implementation
until validation rejects this condition or the worker produces a committed,
lineage-correct closeout.
