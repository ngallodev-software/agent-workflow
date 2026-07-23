# Prompt-Pack Runtime Integration Plan

## 0. Document contract

| Field | Value |
|---|---|
| Status | Active plan; Phases A-C implemented and verified; Phase D blocked on external contract definition |
| Audience | Orchestrator, prompt-pack builder, runtime implementer, reviewer |
| Scope | Bridge external prompt-pack jobs, completions, ledgers, and reviews to agent-workflow run state |
| Non-goals | Tax-domain logic, weakened sealing, bypassed review, acceptance from agent prose |
| Evidence | Live Tax Machine Phase 0 delegation, 2026-07-22 |

### Implementation status

| Phase | Status | Evidence |
|---|---|---|
| A: evidence boundary | Implemented | Worktree-local handoff, no-follow bounded collection, required sealed collection receipt, lifecycle acceptance guard, and valid/missing/invalid/symlink/oversize/escape tests. |
| B: native job binding | Implemented | JSON-only native job schema, launch preflight, immutable sealed binding, and enforced scope/controlled-command receipts. |
| C: Tax Machine adapter | Implemented | Adapter-local contained schema validation, sealed snapshots/external completion, and intentional non-mapping to canonical completion. |
| D: ledger and review | Blocked | Requires an external append-only ledger contract and versioned reviewer-receipt/binding contract before implementation can be safe. |

## 1. Problem

Agent-workflow launches, observes, and seals an executor process. A prompt pack
may independently define a job schema, completion schema, append-only ledger,
allowed paths, and acceptance commands. The two evidence systems are currently
adjacent rather than integrated.

Result: an executor may exit zero and produce a valid final receipt while the
prompt pack retains only a placeholder completion and cannot safely mark its
ticket green.

The goal is to make ticket-completion evidence a validated, sealed runtime
artifact. Process completion remains distinct from ticket acceptance.

## 2. Observed evidence

### 2.1 Installed-schema incident

The installed CLI wrote command.json with schema
agent-workflow/command/v1. Sealing failed because runtime schema discovery did
not include the user data-files location. Schemas existed in
~/.local/share/agent-workflow/schemas but discovery searched only
package-adjacent and interpreter-prefix locations.

Invariant:

    Every schema referenced by a newly written runtime artifact is discoverable
    by that same installed CLI before the artifact is sealed.

This incident was repaired before this plan. A launch-and-seal smoke test then
completed with a final receipt.

### 2.2 Placeholder completion sidecars

For Tax Machine tickets, agent-workflow sealed executor evidence but its
completion.json remained a generated placeholder:

    result: blocked
    unresolved: agent completion sidecar not finalized

The executor sandbox correctly prevented writes to the authoritative state path
under ~/.local/state/agent-workflow/runs. The executor therefore could not
replace the sidecar even when it had implementation/test evidence.

### 2.3 Job and ledger split

The Tax Machine pack creates repository-local job and ledger records. Launch
accepts labels such as ticket and pack, but no --job input. Runtime status does
not bind prompt-pack run ID, job path, allowed paths, or acceptance commands.

### 2.4 Pack discovery mismatch

Tax Machine uses MANIFEST.json plus custom schemas/templates. Native discovery
expects a different pack layout, so session status recorded a null pack root
even when the source prompt was inside a pack.

### 2.5 Review lifecycle gap

The review command records a disposition receipt. It does not dispatch a
bounded independent reviewer or bind a prompt-pack reviewer role/checklist to
the implementation evidence.

## 3. Safety invariants

1. Executor exit code zero MUST NOT mean ticket complete, reviewed, accepted,
   merged, or green.
2. Executors MUST NOT receive write access to authoritative runtime state merely
   to submit completion evidence.
3. Completion evidence MUST validate before it affects a ledger, review,
   acceptance, or manifest state.
4. Sealing MUST hash submitted completion evidence and its collection
   provenance.
5. Pack-defined allowed paths MUST be enforced or explicitly reported as
   advisory; they MUST NOT be silently ignored.
6. Acceptance command receipts MUST contain cwd, command, exit code, timestamps,
   stdout/stderr references, and input revision.
7. Reviewer identity MUST differ from implementation identity where the pack
   requires independence.
8. Missing, malformed, failed, or out-of-scope completion evidence MUST remain
   resumable and auditable without overwriting executor evidence.
9. Pack adapters MUST reject unknown schemas and path escapes.
10. Integration MUST preserve existing redaction and secret-handling boundaries.

## 4. Target model

    prompt pack
      job.json --------------------------> launch --job
      completion.schema.json -----------> adapter validation
      ledger.json <---------------------> append-only ledger bridge
      reviewer requirements -----------> reviewer dispatch and receipt

    agent-workflow run state
      executor evidence, immutable after seal
      collected completion evidence
      command and scope receipts
      final receipt with hashes
      reviewed / accepted / rejected lifecycle receipts

| Component | Owner | Executor writable |
|---|---|---|
| Ticket worktree | Executor | Yes, inside sandbox and declared scope |
| Worktree handoff directory | Executor | Yes |
| Runtime run state | Collector | No |
| Prompt-pack ledger | Bridge/orchestrator | No direct executor write |
| Manifest ticket state | Reviewed integration patch | No implicit executor write |

## 5. Proposed features

### F1. Pack adapter registry

Add a registry that recognizes native pack.yaml packs and supported external
pack formats.

Minimum adapter surface:

    discover(prompt_path) -> PackDescriptor
    validate_job(job_path) -> ValidatedJob
    completion_schema(pack) -> SchemaRef
    ledger(pack, run_id) -> LedgerRef
    reviewer_policy(job) -> ReviewerPolicy

PackDescriptor MUST include root, format/version, manifest hash, schema
locations, and trusted path boundaries.

Initial adapters:

1. Native agent-workflow pack.yaml format.
2. Tax Machine MANIFEST.json format with schemas/job.schema.json,
   schemas/completion.schema.json, and templates.

### F2. Launch job binding

Add:

    agent-workflow launch SESSION WORKDIR PROMPT --job PATH [options]

Required behavior:

1. Discover adapter from job or prompt.
2. Validate job before tmux creation.
3. Copy job, validation receipt, and SHA-256 to run state.
4. Record run ID, job ID, ticket ID, model, path policy, dependencies, and
   acceptance commands in status/provenance.
5. Reject job/worktree mismatch, ticket mismatch, path escape, and unsupported
   model before launch.

Do not synthesize missing job fields from CLI labels.

### F3. Worktree-local completion handoff

Create an authorized handoff directory during launch:

    .agent-workflow-handoff/<session-id>/
      completion.json
      completion.md
      evidence.json

Launch context MUST state this path and the completion schema. The executor
writes only here, never under ~/.local/state.

**Boundary correction:** `.delegations/<session-id>` is a discoverability
symlink to authoritative runtime state. A handoff directory MUST NOT be created
beneath it. The handoff is instead a real directory under the ticket worktree,
ignored through that repository's local Git exclude metadata. It is exposed to
the executor only as its declared writable completion output path.

Post-executor collection:

1. Read handoff.
2. Validate through adapter.
3. Store immutable copies in run state with source path and hash.
4. Record one of valid, missing, or invalid collection statuses.
5. Permit sealing missing/invalid evidence, but prohibit acceptance and avoid
   silently replacing it with a generic placeholder.

### F3.1 Phase-A completion protocol

Phase A implements only a native runtime handoff; it does not infer or transform
external completion schemas. Its contract is deliberately narrow:

1. Launch creates the real handoff directory and writes its absolute path in
   `AGENT_WORKFLOW_HANDOFF_DIR`, `launch-prompt.md`, and status.
2. The executor atomically writes `completion.json` to that directory and may
   write the optional Markdown/evidence sidecars there. It has no runtime-state
   write path.
3. After the executor exits and before sealing, the runner collects files using
   no-follow, regular-file checks; rejects path traversal/symlinks; enforces a
   bounded file size; hashes exact source bytes; and copies accepted bytes into
   the run directory.
4. A valid native `agent-workflow/completion/v1` handoff replaces the initial
   canonical runtime `completion.json`; the collection receipt records the
   source path, source hash, stored path, adapter `native`, and validation
   result. It may not fabricate fields or convert an external schema.
5. A missing or invalid handoff leaves the initial canonical placeholder in
   place, writes a collection receipt with `missing` or `invalid`, preserves
   validation errors, and still permits runner sealing. Existing acceptance
   checks then reject the placeholder/non-completed result.
6. The completion collection receipt is always present and becomes a required
   sealed artifact. A sealed run therefore proves whether completion evidence
   was valid, missing, or invalid rather than inferring it from agent prose.

Collection precedes post-execution acceptance commands, scope collection, patch
capture, and `seal_run`; this fixes the evidence boundary before any downstream
gate may consume it. The initial implementation accepts only native completion
schema bytes. Adapter-owned external schemas begin in Phase C.

### F4. Acceptance-command collection

Collect baseline and post-executor acceptance commands in a controlled runner.
Each receipt MUST contain:

    phase: baseline | post_execution | review
    command: exact command
    cwd: execution directory
    started_at / finished_at
    exit_code
    stdout_path / stderr_path
    worktree_revision

Commands from untrusted packs MUST remain subject to existing shell and sandbox
policy. JSON validation alone is not authorization to execute arbitrary shell.

### F5. Ledger bridge

Add an explicit append-only command:

    agent-workflow ledger sync --job RUN_STATE_OR_JOB --ledger LEDGER.json

The bridge records session ID, final-receipt hash, completion status, review
disposition, revision, and timestamp. It MUST atomically reject a ledger whose
run ID or repository root disagrees with the binding.

The source pack remains authority for semantic ticket state. The bridge reports
evidence; it does not set green from a process exit code.

### F6. Reviewer dispatch

Add review launch or launch --role reviewer. Inputs MUST include implementation
session/final receipt, reviewer role/model, checklist, and acceptance commands.

The reviewer receipt MUST:

1. Bind to the implementation final-receipt hash and exact revision.
2. Enforce independent identity/model when policy requires it.
3. Include diff, path-scope report, completion evidence, and test receipts.
4. Reject approval if completion is missing/invalid or required gates failed.
5. Be required by accept for jobs declaring independent review.

## 6. New runtime contracts

### 6.1 Job binding receipt

Schema: agent-workflow/job-binding/v1.

Required fields:

    schema
    session_id
    adapter
    job_path
    job_sha256
    job_id
    run_id
    ticket_id
    worktree_path
    allowed_paths
    forbidden_paths
    acceptance_commands
    bound_at

### 6.2 Completion collection receipt

Schema: agent-workflow/completion-collection/v1.

Required fields:

    schema
    session_id
    adapter
    source_path
    source_sha256
    validation_status: valid | missing | invalid
    validation_errors
    collected_at
    stored_path

Conditional requirements:

- `source_path`, `source_sha256`, and `stored_path` are required only for
  `valid` and `invalid` input that was safely read.
- A `missing` result records `source_path` as null, has no source hash, and
  contains a machine-readable missing reason.
- `invalid` preserves bounded validation errors and source hash where input was
  safely read; symlink, path-escape, and size-limit failures record a stable
  rejection reason without following/reading unsafe input.
- `adapter`, `adapter_version`, `canonical_mapping`, and `canonical_sha256` are
  explicit. Phase A uses `native`, version `v1`, and an identity mapping only.

### 6.3 Status extension

Add nullable fields without changing status semantics:

    job_binding_path
    completion_collection_path
    completion_validation_status
    pack_adapter
    prompt_pack_root
    review_requirement

Completed means executor process exit plus runtime evidence sealing. Ticket
acceptance remains a lifecycle receipt, not a status alias.

## 7. Implementation sequence

### Phase A: evidence boundary

1. Implement worktree-local handoff creation and collection.
2. Add schemas and validation statuses.
3. Include collection receipts in sealing.
4. Test valid, missing, and invalid handoffs.

Exit: executor cannot write runtime state; valid completion handoff is sealed
with exact source bytes.

#### Phase-A acceptance criteria

1. Every launch creates a real ignored worktree handoff directory; no handoff
   path resolves inside the authoritative run directory.
2. Runner launch context exposes only the handoff path for completion writes;
   the existing canonical completion paths remain collector-owned.
3. Valid native handoff JSON is copied, validated, becomes canonical completion
   evidence, and is represented by a required sealed collection receipt.
4. Missing, malformed, oversized, or symlinked handoff input produces a sealed
   `missing`/`invalid` receipt, preserves the canonical placeholder, and cannot
   satisfy acceptance.
5. Existing launches with no handoff remain compatible and seal successfully.
6. Unit and runner integration tests cover valid, missing, invalid, and
   state-path-escape attempts without a live model or network.

#### Phase-A file ownership

| Area | Expected change | Owner |
|---|---|---|
| `sessions.py` | Create/ignore handoff, record paths, pass launch context. | Runtime implementation |
| `runner.py` | Collect before post gates/seal and update final status. | Runtime implementation |
| `receipts.py`, contracts, schemas | Define/validate/require collection receipt. | Runtime implementation |
| tests | Launch, runner, receipt, and lifecycle regressions. | Runtime implementation and verifier |
| adapters, Tax Machine, ledger, reviewer dispatch | No Phase-A change. | Deferred |

### Phase B refinement: native job binding tickets

Native `pack.yaml` and scaffolded YAML task manifests do not define the JSON job
contract required by `--job`. Phase B therefore begins by introducing a new,
versioned, JSON-only native job schema; it MUST NOT accept arbitrary Markdown or
YAML and infer missing execution policy.

Split Phase B into three independently reviewable tickets:

| Ticket | Scope | Exit condition |
|---|---|---|
| B1 | Native job schema and adapter | A validated job has explicit `schema`, `job_id`, `ticket_id`, pack-relative prompt, worktree target, allowed paths, argv-vector acceptance commands, and review requirement. |
| B2 | `launch --job` preflight/binding | All paths are resolved under the selected pack/worktree; every mismatch fails before run-directory creation or tmux. Raw job bytes and a validated binding receipt are immutable run artifacts. |
| B3 | Validated execution mapping | Allowed paths become enforced `ScopePolicy` inputs and accepted argv commands become baseline/post receipts. A job cannot silently downgrade these fields to advisory. |

The preflight must reject job-outside-pack, prompt escape, worktree mismatch,
`--ticket` disagreement, and `--pack` disagreement before it creates state.
Status/provenance schema changes must include separate source/stored job paths
and hashes. Restart must preserve the immutable binding or fail explicitly;
losing binding on retry is unsafe.

### Phase C refinement: external adapters

External schemas are adapter-local trust boundaries. Do not add arbitrary pack
roots to `contracts._schema_roots()` and do not use global schema-ID lookup for
Tax Machine validation. An adapter resolves only allowlisted pack-local schema
files and `$ref` paths under its resolved root, snapshots manifest/job/schema
bytes at launch, and rejects root conflicts or unknown schema IDs.

External completion bytes are always preserved separately. They can replace the
native canonical `completion.json` only through an explicit deterministic,
versioned mapping that supplies the native result, revision, criteria, and
command facts. If a safe one-to-one mapping does not exist, the canonical
placeholder remains and acceptance rejects the run even if the external
completion is individually valid. This is deliberate: semantic evidence is not
authorization to bypass native lifecycle gates.

Phase-C tests use a synthetic local MANIFEST/job/completion fixture and a fake
executor only. They cover schema/root discovery, external validation, unsafe
`$ref` and path rejection, sealed snapshots, mapping outcome, and no ledger
mutation.

### Phase B: native job binding

1. Add --job for native packs.
2. Validate/bind before launch.
3. Capture command metadata.
4. Add binding fields to status/provenance.

Exit: mismatched job/ticket/worktree fails before tmux creation.

### Phase C: Tax Machine adapter

1. Implement MANIFEST.json discovery.
2. Validate Tax Machine job/completion schemas.
3. Map template fields to receipts without mutating its ledger.
4. Add end-to-end fixture pack.

Exit: a Tax Machine run has a valid collected completion and sealed evidence,
while its ledger remains authoritative.

### Phase D: ledger and review

1. Add append-only ledger bridge.
2. Add reviewer dispatch/receipt binding.
3. Require review and gate receipts for accept when declared by job.

Exit: an accepted ticket has linked job, completion, tests, review, final
receipt hashes, and one exact revision.

## 8. Required regression tests

| Test | Expected result |
|---|---|
| User-base schema discovery | Installed CLI seals a run using user-base schemas |
| Valid handoff | Collector validates/copies it; final receipt hashes it |
| Missing handoff | Run seals; completion is missing; accept rejects |
| Invalid handoff | Errors retained; accept rejects |
| State write attempt | Sandbox rejects it; worktree handoff still works |
| Job ticket mismatch | Launch fails before tmux/session state |
| Prompt path escape | Adapter rejects it |
| Out-of-scope diff | Scope receipt reports violation; review cannot approve without override evidence |
| Failing post-execution command | Completion may exist; acceptance rejects |
| Self-review | Reject when independence policy requires another reviewer |
| Ledger revision mismatch | Sync fails atomically with no ledger mutation |
| Tax Machine fixture | MANIFEST.json, job/completion schemas, and TDD commands work end to end |

## 9. Definition of done

1. A real prompt-pack job launches with validated job binding.
2. Executor submits schema-valid completion without escaping worktree sandbox.
3. Collector seals completion, collection, scope, and command receipts.
4. Exit zero plus placeholder completion cannot be accepted.
5. Reviewer receipt binds to exact implementation receipt/revision.
6. Supported external pack resolves root and schemas without ad hoc wrappers.
7. Default tests remain offline and synthetic.
8. Existing native launches remain compatible when --job is absent.

### Phase-D unblock contract

Do not implement ledger sync or reviewer dispatch until the source pack defines
these versioned contracts:

1. **Ledger event schema:** append-only event shape, event identity, run/job/
   repository-root binding, permitted transitions, and idempotency key.
2. **Ledger write semantics:** authoritative file/root, full-ledger validation,
   revision or compare-and-swap behavior, lock/concurrency rule, temp-file
   fsync/replace atomicity, and conflict handling.
3. **Reviewer receipt schema:** implementation final-receipt hash, exact
   revision, reviewer identity/model/role, checklist hash, required gate hashes,
   outcome, and independence policy.
4. **Acceptance linkage:** which job policies require a reviewer receipt and
   how a lifecycle receipt references it without amending sealed agent evidence.

Until those contracts exist, `ledger` remains the current read-only derived run
view and `review`/`accept` remain the existing local lifecycle operations. This
is a deliberate safety gate, not a missing automation feature.

## 10. Operator guidance until implemented

1. Treat status completed as process completion only.
2. Inspect diff and executor log before review.
3. Never mark a prompt-pack manifest green from runtime exit code.
4. Keep pack jobs/ledgers in their repository-local run directory.
5. Use a separate reviewer for tax, security, schema, retrieval, and integration.
6. Preserve blocked provenance findings; never replace them with derivative
   runtime hashes or inferred citations.
