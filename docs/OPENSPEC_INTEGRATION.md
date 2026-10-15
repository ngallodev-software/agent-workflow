# OpenSpec integration

Agent-Workflow treats OpenSpec as an upstream **specification/planning authority** and keeps
execution, evidence, evaluation, review, recovery, and acceptance as Agent-Workflow
responsibilities.

The first qualified import surface is intentionally narrow:

- OpenSpec `1.13.2` exactly;
- package-owned `spec-driven` schema version `1`;
- one local Git repository and one active change;
- a clean, committed planning revision;
- strict OpenSpec validation;
- no project/user schema override;
- no OpenSpec store or multi-repository import.

This is a versioned compatibility surface, not a claim that arbitrary future OpenSpec releases
have equivalent semantics.

The qualified upstream reference is the published `v1.13.2` release at
`Fission-AI/OpenSpec@db2309783547a14e150dbcbfc19120e4028446c3`, not a later
`main` checkout that may still report the same package version. In that release,
`instructions apply --json` exposes task `id`, `description`, and `done`;
the later `sourcePath` / `line` task fields are not part of the published
1.13.2 surface. The importer therefore derives source locations from the frozen
`tasks.md` and cross-checks that source projection against the release CLI
before binding an Agent-Workflow task.

## Boundary

```text
OpenSpec change
   |
   | documented CLI JSON + frozen planning artifacts
   v
agent-workflow/source-specification-import/v1
   |
   v
agent-workflow/native-job/v2
   |
   v
Agent Run
   execution / evidence / evaluation / review / acceptance
```

The imported pack is self-contained for Agent-Workflow preparation and execution. OpenSpec is not
consulted again after import.

Legacy `agent-workflow/native-job/v1` remains supported and continues to negotiate the immutable
SpecGen/Agent-Workflow shared contract bundle. The v1 schema is not reinterpreted as OpenSpec.
New OpenSpec imports use `native-job/v2`, which is owned by Agent-Workflow and has no
`bundle_provenance` field.

## Import

Prepare an Agent-Workflow-owned execution policy separately from the OpenSpec change:

```json
{
  "scope": {
    "writable_paths": [],
    "writable_trees": ["src"],
    "disposable_trees": []
  },
  "acceptance_commands": [
    {
      "id": "test",
      "argv": ["python3", "-m", "pytest", "-q"],
      "cwd": ".",
      "timeout_seconds": 300,
      "result_format": "exit-code",
      "junit_path": null
    }
  ],
  "criteria": [
    {
      "id": "tests-pass",
      "description": "The declared test command passes.",
      "acceptance_command_ids": ["test"]
    }
  ],
  "review_requirement": {
    "required": false,
    "independent": false
  }
}
```

Then import:

```bash
agent-workflow pack import-openspec /path/to/repo CHANGE /path/to/generated-pack \
  --job-policy /path/to/job-policy.json
```

The destination must be outside the source repository so import cannot make the frozen source
revision dirty.

The importer records:

- OpenSpec executable identity and SHA-256;
- resolved package schema and template SHA-256 values;
- raw OpenSpec reports: plain text from `--version`, JSON from schema/template/status/validation/apply/show commands;
- exact source Git revision and branch;
- SHA-256 for the planning artifacts used by the import;
- stable Agent-Workflow task IDs mapped to OpenSpec task locators and source-line hashes.

Generated jobs reject any `openspec/` entry in writable or disposable execution scope. Paths
and recursive trees remain distinct so a directory cannot accidentally be lowered as an exact
writable file.

Each pending dotted task locator produces its own stable task ID, prompt, and
job. Completed checkboxes remain in the provenance receipt but do not produce
jobs. Each job references only its own task in the shared import receipt.
The explicit job policy is copied to every pending job: scope, acceptance
commands, criteria, and review requirements are pack-wide authorizations.
Import does not infer task-specific permissions or validators from prose.

## Planning verification is not execution acceptance

OpenSpec task text is worker-visible planning input. It may describe how an author expects a task
to be checked, but Agent-Workflow does not parse that prose into executable acceptance authority.

In particular:

- a command mentioned in `tasks.md` does not become an acceptance command;
- OpenSpec agent verification workflows are not deterministic host validators;
- hidden/external oracle material remains Agent-Workflow-owned;
- independent review remains Agent-Workflow-owned;
- executable commands enter through the explicit Agent-Workflow job policy and are frozen with the
  native job.

This keeps the implementation worker from implicitly choosing the authoritative test for its own
work.

## Source binding

At v2 preparation, Agent-Workflow verifies that the selected worktree:

1. is at the exact imported Git revision;
2. is clean at first launch;
3. contains byte-identical frozen OpenSpec planning artifacts.

The absolute path recorded during import is provenance only. A fresh worktree may live elsewhere as
long as the revision and imported planning bytes match.

The source specification receipt is copied into run-local evidence and sealed with the run.

For multiple independent tasks, prepare each job on a separate fresh worktree
at that same imported revision. A completed task's commit is a different
revision and cannot be reused as the next job's launch baseline. This execution boundary
uses host-driven public Agent Run commands. The separate host integration
operation below combines accepted independent results; it does not orchestrate
dependent edits. The current workflow scheduler
launches nodes against its shared workdir, rather than provisioning a fresh
source-bound worktree for each imported job. Automatic multi-task scheduling
is outside this qualification.

## Phase-0 execution qualification

`tests/compat/openspec-phase0-smoke.sh` qualifies the real published OpenSpec
1.13.2 surface through host acceptance, with `specgen_contracts` absent. It
initializes and strictly validates a committed `spec-driven` change with one
completed and two pending tasks. It imports only the pending jobs and verifies
checksums, stable IDs, distinct prompts/task references, source/task hashes,
v2 scope, and the absence of `bundle_provenance`.

Immediately after import, the smoke replaces `openspec` on PATH with a logging
shim that exits 97. It checks the guard and resets the sentinel log before pack
validation, preparation, and execution; the worker also verifies that the shim
is selected. The completed lifecycle must leave that log empty.

The fixture runs both jobs sequentially on separate clean worktrees from the
exact imported revision, using the existing external-worker lifecycle:

1. Prepare the imported job at low tier, bind the fixture host, and start the
   generation-bound external worker.
2. Launch the prepared command as a real process. The worker commits only
   its task's source file (`src/rate_limiter.py` or `src/rate_response.py`)
   and calls public `agent finish --result completed`.
   Agent-Workflow runs `compile-src` and derives the mapped `source-compiles`
   criterion from its passing command evidence.
3. After observing the process exit successfully, record public `external-exit`
   and finalize the run. Sealing validates both supported job-binding versions
   and includes the byte-identical source-specification receipt, completion,
   and verification evidence.
4. Record host review and acceptance through public commands and check the
   terminal summary and seal.

Both jobs intentionally share an explicit two-file writable policy, a
disposable `src/__pycache__/` tree for compiler output, and the same host-owned
compile check. Each worker changes only its task's file.
Separate worktrees isolate these overlapping authorizations; this is not a
claim of task-specific access control or safe parallel conflicting edits.
No per-task policy extension is needed for this fixture.

The gate rejects launch with a different ticket, a dirty worktree, or the
first task's advanced revision. It checks independent run identities,
completion and verification evidence, seals, reviews, and acceptance records;
finishing task two must not change task one's sealed evidence. The original
source checkout and every frozen planning file remain unchanged. The logging
OpenSpec guard must record zero calls across both executions.

An external worker has a host-observed exit receipt rather than an
Agent-Workflow-owned process-result record. The fixture does not fabricate
such a record. Its job policy does not require independent review, but host
acceptance still requires a recorded review. No separate semantic assertion or
additional evaluation plan is needed for the command-mapped criterion; the
fixture qualifies deterministic execution rather than a production limiter or
an independent semantic review policy.

Execution preserves every frozen `openspec/` file and changes only the
permitted source files. OpenSpec is neither invoked nor used as lifecycle
authority after import, and v2 needs no SpecGen/shared-contract negotiation.
The installed-product journey provides regression coverage for the same public
external lifecycle; the real-upstream smoke is the gate that proves contract
package absence.

Set `OPENSPEC_SMOKE_EVIDENCE_DIR` to an external directory to preserve
the real fixture, imported pack, command outputs, run-local evidence, and
seals for inspection in a fresh subdirectory. Without it, the smoke removes its
temporary fixture.
The installed-product tests use a fake upstream CLI; only the compatibility
smoke qualifies the real published upstream surface.

This qualification does not exercise autonomous workflow scheduling,
dependent-task rebasing, headless completion, production provider
workers, or independent semantic review. The host integration tests reject
rewritten imported job/task references; generic v2 preparation semantics remain
unchanged. Host-supplied policy and checksum validation remain
authority for the generated pack.

## Compatibility and retirement boundary

This integration does **not** archive SpecGen or rewrite historical artifacts.

Current compatibility policy:

- `native-job/v1`: frozen legacy SpecGen/shared-contract path;
- `native-job/v2`: OpenSpec source-specification path, no SpecGen negotiation;
- the shared contract package remains installed while supported v1 jobs exist;
- new planning work should prefer OpenSpec rather than creating new SpecGen authoring state;
- execution qualification does not freeze or retire legacy authoring compatibility;
- before retirement, inventory remaining SpecGen authoring consumers and supported v1 jobs,
  complete their migration or explicitly freeze their support boundary, and obtain review and
  acceptance of that compatibility decision;
- removal of the mandatory shared-contract dependency requires a separate packaging change with
  v1 compatibility and sealed historical evidence preserved.

SpecGen capabilities that were actually execution invariants—source binding, fail-closed lowering,
result contracts, writable scope, evaluation/oracle identity, and review requirements—remain
Agent-Workflow concerns rather than being discarded with the authoring system.

## Deferred

The initial integration deliberately does not support:

- custom/forked OpenSpec schemas;
- project or user schema overrides;
- OpenSpec stores;
- multi-repository worksets;
- arbitrary future OpenSpec versions;
- automatic translation of planning prose into validators;
- OpenSpec archive operations as Agent-Workflow lifecycle actions.

Each requires separate qualification rather than widening the v1 import receipt silently.

## Host integration interface (OPENSPEC-003)

The real 1.13.2 smoke now continues from the two accepted tasks to one detached
integrated revision, passes a fresh command that imports and checks both task
results together, verifies its archived evidence, and reproduces the exact
revision in an explicit replay. The post-import OpenSpec guard remains empty
through integration and replay, with `specgen_contracts` absent. Installed-product
negative journeys cover conflicting accepted edits, cross-source/wrong-task
inputs, duplicates, missing seals/acceptance, dirty sources, evidence tampering,
failed/mutating commands, and ambient Git routing. Archived verification is also
exercised after the original input worktrees are removed.

Investigation found that sealed artifact readers and canonical host lifecycle
receipts already provide task input authority. Worktree creation and bounded
process execution also exist. `worktree closeout` observes repository state and
remote ancestry; it does not select or apply accepted task commits. The missing
behavior is a host operation that validates those inputs, combines their commits,
and verifies the combined revision. It does not require another worker lifecycle.

The bounded interface is:

```bash
agent-workflow --json worktree integrate /path/to/source \
  --run TASK_A_RUN --run TASK_B_RUN \
  --commands /path/to/combined-commands.json \
  --dest /path/to/new-detached-worktree \
  --output /path/to/new-integration-evidence \
  --actor integration-host --reason 'Verify the combined result'
agent-workflow --json worktree integration-verify /path/to/new-integration-evidence
```

The command file is a host-authored JSON array, for example:

```json
[
  {
    "id": "combined-behavior",
    "argv": ["python3", "-B", "tests/check_combined.py"],
    "cwd": ".",
    "timeout_seconds": 60
  }
]
```

Commands are explicit argv arrays, use exit-code results, and run afresh against
the combined worktree. Independent task acceptance is not equivalent to
successful integrated acceptance. No command is inferred from OpenSpec prose.

Inputs must be two distinct, sealed, canonically host-accepted v2 runs from the
same import bytes and source revision. Each must contain exactly one non-merge
commit directly on that revision, and its original worktree must still be clean
at the accepted head in the same repository. The operation cross-checks sealed
job/binding/task identities, source receipt and job hashes, source baseline,
completion changed paths, sealed scope inventory hashes against exact Git
blob bytes, and regular-file writable scope. A nonempty sealed binary patch
must also match; the integration archives its own explicit host diff. Historical
empty patches remain supported without rewriting old seals. New normal
and recovery-finalized runs capture accurate binary patches or fail collection
and sealing explicitly (see [patch evidence collection](OPERATIONS.md#patch-evidence-collection)).
The installed-product journey and real upstream smoke require nonempty patches
whose sealed hashes match independently generated Git diffs. Frozen planning
hashes are checked at both input revisions. Symlink and
submodule changes are outside this operation's contract.

Integration creates a new detached worktree at the frozen base and cherry-picks
in the supplied `--run` order, preserving original author/message provenance with
`-x`. The committer identity and date are fixed so explicit replay yields the
same commit IDs. Hooks, signing, filesystem monitors, configured merge drivers, and configured
checkout filters are disabled for these host Git operations. Git uses a
controlled environment so ambient repository/index routing cannot redirect it.
The original checkout, input worktrees, branches, and task receipts are not
rewritten. Successful integration retains its detached worktree for host
inspection; landing or pushing it is a separate operator action.

`agent-workflow/task-integration/v1` is a new host decision receipt, not a change
to native-job, completion, review, or acceptance contracts. It records input
seals, task/commit identities and scopes, ordered applied commits, combined tree
and revision, exact host command policy and bounded process results, actor,
reason, and accepted/rejected decision. Evidence includes complete sealed input
snapshots, canonical review/acceptance receipts, original-commit Git bundles,
and the combined-result bundle. Every artifact has a SHA-256 and size; the
receipt has a canonical SHA-256 and all published evidence files are read-only.
These hashes detect changes relative to the retained receipt; they are not a
signature or a replacement for trusted host custody of the receipt digest.

`integration-verify` checks the manifest, original run seals and acceptance,
then replays the recorded commits from archived bundles in temporary Git
storage and compares the exact combined revision/tree. It requires no original
worker checkout or OpenSpec executable. It verifies recorded acceptance results;
it does not rerun their commands. A fresh integration attempt reruns commands.

The evidence destination is the attempt identity and exclusive creation lock.
An identical successful request returns its verified historical receipt without
applying commits again. Changed requests, rejected attempts, and interrupted
attempts cannot silently reuse it. An explicit retry uses new evidence and
worktree destinations; the same valid inputs and ordering reproduce the same
revision. No existing target revision is ever appended to, so a task cannot be
silently applied twice to an integration target.

On conflicts, invalid inputs, or failed/mutating combined checks, the operation
records a rejected decision and diagnostics, exits nonzero, and removes only
its newly created worktree. The receipt records rollback results; a failed
cleanup requires operator attention. Path errors that would place evidence in
source/run/Git storage are refused before creating artifacts. Abrupt process
termination can leave an incomplete attempt and its detached worktree; no
success receipt is published and retry requires an explicit new attempt.

This boundary does not provide dependent-task rebasing, multi-commit task
integration, autonomous scheduling, parallel conflict resolution, or production
semantic review. It requires retained input worktrees for initial validation;
archived integration verification is independent of them. Legacy compatibility,
SpecGen retirement, headless completion, and REL-003 acceptance remain separate.
