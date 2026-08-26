# Operations

## Normal delegation

1. Create or validate an isolated worktree.
2. Prepare an Agent Run by logical role (normally `--role implementation`, `review`, or `exploration`).
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

## External workers

Use `--worker-mode external` when another runtime will launch the worker. Preparation remains durable and host-independent. The external runtime is presentation/execution infrastructure, not workflow authority.

Agent-workflow does not guess external process ownership or silently control an external host. Host-specific binding/reconciliation remains future work unless an explicit public integration contract is present.

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

## Completion gates

Do not infer success from worker exit alone. Verify completion schema, sealed evidence, evaluation policy, review state, and lifecycle disposition.

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
