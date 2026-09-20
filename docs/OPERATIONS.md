# Operations

## Normal delegation

1. Create or validate an isolated worktree.
2. Prepare an Agent Run by logical role (normally `--role implementation`, `review`, or `exploration`). The command profile is a separate bounded CLI surface: `exploration` currently maps explicitly to the `implementation` profile.
3. For headless mode, start the worker.
4. Observe lifecycle state and durable progress.
5. Persist steering requests when needed.
6. Require explicit acknowledgement for steering disposition.
7. Collect completion and evaluation evidence.
8. Review and accept/reject separately.
9. Seal/archive when appropriate.

## Role and runtime operations

Normal callers use `--role`; they do not select a provider/model. Inspect the public catalog with:

```bash
agent-workflow agent roles
agent-workflow agent roles implementation
```

Role-to-runtime bindings and runtime aliases are operator configuration. In 0.9 production aliases may resolve only to Codex or Claude subscription-backed executors. Raw `--executor`, `--model`, and `--agent-class` controls remain temporary operator/diagnostic compatibility escapes and should not appear in normal workflow or skill instructions.

Changing a private role binding must not require changing a workflow, prompt, role file, or peer-agent message. The actual resolved runtime remains available in restricted run provenance for diagnosis and reproducibility.

### Logical names versus runtime selection

`--agent-name` names the logical worker lease; it does not select a model. `[agents].preferred_names` is the automatic-allocation order, not an allowlist for explicit valid names. An operator may therefore use a descriptive logical name such as `terra` without changing runtime selection.

`--role` and explicit runtime overrides are intentionally separate modes. A role selects its configured private runtime binding. If an operator must pin a runtime for diagnosis or qualification, omit `--role` and use the matching `--agent-class` with `--executor`, `--model`, and optional `--reasoning-effort`. For example, a review qualification may use `--agent-class review --executor codex --model MODEL`; this is an operator compatibility path, not normal workflow vocabulary.

## Dirty source baselines

Source cleanliness remains fail-closed. Use `--allow-dirty` only when the operator has intentionally chosen to preserve an already-dirty worktree or repository as the launch baseline. Agent-Workflow records the dirty baseline and injects that fact into the immutable launch context; it does not normalize, discard, or authorize rewriting pre-existing changes.

For read-only review or evidence collection on a dirty repository, combine `--allow-dirty` with an explicit read-only task contract. The worker should preserve all pre-existing changes, report only newly observed evidence, and avoid treating the mere presence of baseline drift as a task failure.

## External workers

Use `--worker-mode external` when another runtime will launch the worker. Preparation remains durable and host-independent. The external runtime is presentation/execution infrastructure, not workflow authority.

Agent-workflow does not guess external process ownership or silently control an external host. The implemented host-neutral binding and generation-checked delivery contract is documented in [EXTERNAL_WORKER_BINDING.md](EXTERNAL_WORKER_BINDING.md); host-specific UI/process behavior remains outside the core.

## Recovery and restore

Recovery starts from source, immutable Agent Run contracts, append-only journals, sealed evidence, and workflow snapshots. Mutable status, indexes, and external-host bindings are projections and may be rebuilt.

Recommended restore sequence:

1. restore and verify repository source;
2. install the current package and dependencies;
3. run `agent-workflow doctor`;
4. verify the relevant worktree/source baseline;
5. inspect Agent Run contracts and durable journals;
6. repair mutable run status and rebuild the SQLite projection where needed;
7. resume workflow scheduling or create a new Agent Run with retry lineage;
8. rerun applicable tests/evaluations before acceptance.

Do not depend on prior UI state, a prior interactive host, or host-specific absolute paths.

## Interrupt and termination

For headless workers, Agent Run control targets the Agent-Workflow-owned process group. External workers are not controlled through guessed host mechanisms; unsupported lifecycle operations fail clearly.

## Messaging

Persist first. Delivery is optional. A steer request remains pending until correlated acknowledgement evidence exists.

Inspect steering capability before depending on live delivery. `delegate` returns a compact `steering` block, while `agent-run status RUN` exposes `steering_supported`, `steering_adapter`, and `steering_reason`. If a request returns `delivery_outcome=unsupported`, the message is still durable, but no evidence-capable adapter delivered it to the running worker. The worker must not be assumed to have seen or applied it; correlated acknowledgement remains the gate.

For one Agent Run, `agent-run watch` accepts `--after` and `--timeout`:

```bash
agent-workflow agent-run watch RUN --after 0 --timeout 60
```

Do not pass `--max-cycles` to that command. `--max-cycles` is an `orchestrator watch` option for the foreground orchestrator loop.

## Completion gates

Do not infer success from worker exit alone. Verify completion schema, sealed evidence, evaluation policy, review state, and lifecycle disposition.

Read-only work is still evidence-bearing work. When there is no task-specific test to execute, record one known-safe successful verification such as:

```bash
agent-workflow agent verify --cwd /path/to/worktree RUN -- git rev-parse --verify HEAD
```

The `agent verify` parser consumes the verification command as the trailing remainder. Use the parser-native ordering `agent verify [--cwd ...] [--timeout ...] RUN -- COMMAND`; the CLI also normalizes the common `RUN --cwd ... -- COMMAND` form. Failed verification receipts remain durable and block a later `completed` handoff; investigate uncertain commands outside `agent verify`, then record the command intended as completion evidence.

## Failure classification and triage

Do not use exit code alone to decide why a run failed. The precise durable `failure_category`, incident evidence, completion/evaluation evidence, and provider/process observations remain authoritative.

For operator triage only, the historical three-way distinction is still useful:

- **environment/runtime** — authentication, permission, network, rate-limit, dependency/command availability, host resource pressure, process loss, or bounded output/provider-capture failures;
- **specification/contract** — invalid or missing completion handoffs, invalid contracts/digests, contradictory requirements, or other failures showing that the requested/evidence contract could not be satisfied as written;
- **execution/task** — the executor ran but the implementation, acceptance commands, timeout/interruption path, or other task execution did not complete successfully.

This grouping is deliberately coarser than Agent-Workflow's failure categories. Never replace a precise recorded category with the coarse domain, and never convert an unknown category into a confident domain merely to simplify reporting. Implementation/test failures should remain grounded in completion and evaluation evidence instead of being inferred from process exit alone.

## SQLite index operations

The SQLite database is a disposable query projection over durable evidence. It may accelerate fleet status, workflow views, incidents, permissions, and performance analysis, but it must never become authority for an acceptance or lifecycle decision.

Common operations:

```bash
agent-workflow index status
agent-workflow index sync
agent-workflow index rebuild
agent-workflow index verify --full
agent-workflow index query runs --state running
agent-workflow index query incidents --category process_alive_no_progress
agent-workflow index query errors
```

Use `index sync` for normal incremental reconciliation. Fingerprints skip unchanged runs; a changed run is replaced transactionally.

Use `index rebuild` after database loss/corruption, projection-schema changes, or when a clean reconstruction is preferable to diagnosis. A rebuild deletes/recreates only the projection and never rewrites Agent Run source evidence.

Use `index verify --full` when source drift or post-index tampering is suspected. Corrupt or unsafe source evidence is isolated as an index error; it is not silently repaired or translated into an older representation.

The foreground supervisor synchronizes the index after each cycle by default. When diagnosing the index itself, disable that integration explicitly:

```bash
agent-workflow supervisor once --no-sync-index
```

The public query surface is curated and parameterized. It intentionally exposes neither arbitrary SQL nor raw prompt/message/log/provider bodies.

## Command discovery

The CLI parser is the command authority. Generate the exact installed command surface rather than maintaining a parallel static command listing:

```bash
agent-workflow commands --format markdown
```

Use normal `--help` output when investigating a catalog/version mismatch, an argument error, or a command absent from the catalog.
