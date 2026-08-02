# Operations

This document consolidates day-to-day delegation lifecycle, agent policy, recovery, and host-routing guidance.

## Execution model

Each delegation has:

- a source repository and pinned baseline revision;
- a dedicated Git worktree;
- a fresh session ID and durable run directory;
- a copied and hashed prompt;
- a configured executor/model/class selection or explicit argv;
- a tmux session or pane used as an observation and process-control surface;
- sealed terminal evidence and later immutable lifecycle receipts.

The CLI and MCP adapter call shared services. Shell scripts are compatibility wrappers only.

## Process and environment policy

Governed commands are argv arrays and never use `shell=True` or command-string fallback. The shared process substrate applies a timeout, owns the complete non-interactive process group, caps stdout/stderr, and performs graceful cancellation followed by bounded escalation. `command.json`, provenance, logs, completion collection, and diagnostics contain redacted argv/output; explicit launches are classified as `unclassified`.

Child environments start from fixed `PATH`/locale defaults. A configured executor may name variables in `environment_allowlist`; only those ambient values, plus named values supplied by the caller, are passed through. Credential-agent and cloud credential variables are not inherited by default. `unsafe_inherit` is an explicit break-glass policy and is not used by governed launch paths.

## Launch policy

Agent classes constrain interactivity, executor, and model combinations. Named profiles may narrow those choices but cannot escape class policy. Explicit no-go authorization is recorded in provenance.

Routing advice is deterministic and explainable, but advisory. The launch plan produced by configured policy is authoritative. Never allow a recommendation, prior trial, or agent-selected value to bypass class, executor, model, or permission restrictions.

The default classes are:

| Class | Intended use | Default behavior |
|---|---|---|
| `exploratory` | bounded research and reconnaissance | non-interactive, low-cost models |
| `review` | independent inspection and evidence review | non-interactive |
| `implementation` | code-changing work | interactive by default |

The concrete allowlists live in configuration, not documentation. Use `agent-workflow config show` to inspect effective policy.

`agent-workflow --json doctor` reports the exact trusted policy inputs, resolved
executor path, probed version, adapter version, capabilities, compatibility
decision, and explanation code. Local mode reports unsafe ownership/modes and
custom executors as warnings. Governed and release modes fail closed with a
remediation message; an unsupported named adapter is never silently treated as
unclassified.

The executor compatibility policy is shipped as the versioned
`executor-compatibility/v1` data asset. It is intentionally separate from user
settings so changing provider support requires a release-backed asset update.
Launch provenance records the actual absolute executable path, version, optional
digest, compatibility policy digest, adapter version, and decision. This makes a
PATH substitution between doctor and launch observable even when the host PATH
changes.

Implementation work starts interactive. Exploration, research, and review work
starts non-interactive. When an implementation launch is inside a tmux window
that has reached its configured capacity, the CLI reports the count and
explicitly identified idle panes. The operator may close enough idle panes and
retry, choose a structured non-interactive fallback, or cancel. The fallback
sets both assignment and executor mode to non-interactive; it is never an
implicit downgrade. A structured provider stream is required when the run will
be evaluated after completion.

When no shared tmux window is available, a dedicated named session remains an
interactive executor context; it is not a silent non-interactive downgrade.

## Observe and control

```bash
agent-workflow list
agent-workflow status SESSION --capture 50
agent-workflow attach SESSION
agent-workflow tail SESSION
```

Controls preserve prior evidence:

```bash
agent-workflow interrupt SESSION
agent-workflow terminate SESSION
agent-workflow kill SESSION
agent-workflow restart SESSION --new-session RETRY_SESSION
```

A potential stall is a diagnostic state, not authorization to terminate. Inspect runner heartbeat, executor/process liveness, pane death, semantic progress, terminal snapshots, output/event growth, permission state, lifecycle events, and durable messages before acting. A fresh supervisor heartbeat does not count as semantic progress and cannot conceal a stuck executor.

## Foreground supervision and bounded recovery

Run one reconciliation cycle during diagnosis or a continuous foreground loop while delegations are active:

```bash
agent-workflow --json supervisor once
agent-workflow supervisor run --interval-seconds 10
```

Safe defaults collect evidence, repair a missing or corrupt `status.json` only when immutable authority can reconstruct it, deduplicate incidents, and send at most one progress probe per incident/rule ceiling. Automatic interruption and restart are disabled by default:

```bash
agent-workflow supervisor run \
  --interrupt-stalled \
  --restart-orphaned \
  --max-remediation-attempts 1
```

Enable those switches only under an operator-approved policy. A restart always creates a new run ID and preserves retry lineage. The supervisor never approves a permission request, changes a model/tool allowlist, increases resource limits, accepts implementation evidence, merges a branch, or deletes a run.

### Manual force acceptance

`agent-workflow force-accept SESSION --actor ID --reason TEXT --acknowledge FORCE-ACCEPT` is an explicit local operator override for a terminal run whose ordinary acceptance gate cannot be satisfied. The acknowledgement token is a narrowly documented manual confirmation mechanism; the actor value is an operator-supplied label, not authenticated-human authorization. The command writes a read-only `force-accept-receipt.json` linked to the sealed final-receipt digest with the session, actor, timestamp, reason, command identity, and normal-gate failures, then projects `force-accepted` in status and ledger output. It never rewrites normal lifecycle, completion, evaluation, review, or final-receipt artifacts. Running/launched sessions, missing or tampered sealed evidence, and repeated requests fail closed. HARD-007 remains the required future authenticated authority boundary.

Key evidence:

| Artifact | Operational use |
|---|---|
| `run-health-samples.jsonl` | distinguish runner/executor liveness, host pressure, and semantic progress |
| `terminal-events.jsonl` | inspect bounded changed interactive output without treating pane text as authority |
| `permission-events.jsonl` | surface observed permission waits, denials, and later clears |
| `incident-events.jsonl` | stable typed diagnosis with deduplicated fingerprints |
| `remediation-events.jsonl` | rule, attempt, action, result, and verification history |
| `process-result.json` | exact exit/signal, timeout/cancel, completion-authorized termination, bytes, and truncation outcome |

### Incident response order

1. Read `agent-workflow status SESSION` and the latest incident/remediation records.
2. Confirm immutable launch authority and whether semantic progress actually stopped.
3. Resolve permission, credential, sandbox, or policy incidents manually; do not widen access through a retry.
4. For a transient stall, allow the bounded probe before opting into interruption.
5. Restart only when the original process is proven unavailable or terminal and the retry budget permits it.
6. Verify the new run from durable evidence, not from a pane appearing active.

## Searchable evidence projection

The host-local SQLite database is an operational projection, not execution authority. The supervisor performs `index sync` after each cycle by default. For manual operations:

```bash
agent-workflow index status
agent-workflow index sync
agent-workflow index query runs --state possibly_stalled
agent-workflow index query incidents --category permission_wait
agent-workflow index verify
```

Use a full verification before relying on an older index for analysis:

```bash
agent-workflow index verify --full
```

`--full` rehashes every indexed source artifact in addition to SQLite integrity and foreign-key checks. A mismatch indicates stale or altered current source evidence; it does not rewrite the source file. Obsolete non-authoritative legacy runs are reported as preserved quarantines and do not become valid/current evidence. Unsafe paths and current-schema failures remain blocking.

To verify one named reviewed run and its direct gate evidence without changing
the global result, use `agent-workflow index verify --full --review SESSION`.
The report exposes this separately as `review_valid`; global `valid` still
reflects every unresolved host integrity blocker.

### Rebuild and corruption recovery

If the database is missing, corrupt, on an unsupported schema, or suspected of drift:

```bash
agent-workflow index rebuild
agent-workflow index verify --full
```

The rebuild removes only the SQLite projection and its WAL/SHM companions, acquires the exclusive indexer lock, then reconstructs rows from validated active and archived run evidence. A corrupt individual run is quarantined as an index error while healthy runs remain queryable. Never repair an authoritative JSON/JSONL artifact by editing SQLite.

For a scoped repair:

```bash
agent-workflow index rebuild --run SESSION
```

The database does not require an independent evidence backup because it is reconstructable. Back up or transfer authoritative run/archive directories and their sealed receipts instead. Do not copy a live WAL database as the sole record of a run.

### Concurrency and freshness

Only the indexer writes. It uses an exclusive state-root lock, short transactions, WAL mode, foreign keys, and stable shared-lock reads of append-only journals. Query commands are fixed and read-only. `index status` reports source/index counts, last synchronization, and errors; automation must treat a stale or incomplete index as a query limitation rather than a lifecycle fact. Disable supervisor reconciliation temporarily with `--no-sync-index` or `[supervisor].sync_index = false`.

## Durable messages

The fsynced message journal is the authority. tmux `wait-for` is a local wakeup accelerator only. Producers append immutable records; consumers replay by sequence and acknowledge work explicitly.

Per-consumer cursor files are rebuildable performance projections below the
configured state root. They are keyed by hashed trusted consumer and source
journal identities, use lock-scoped compare/update, and advance only after a
committed target-effect receipt. Missing, stale, truncated, or corrupt cursor
files are reconstructed from the source journal and target evidence. A source
message ID is idempotent only when its canonical digest matches; conflicting
reuse fails closed. Handling states are the fixed dispositions `applied`,
`rejected`, `ignored`, `deferred`, and `security_error`.

```bash
agent-workflow steer SESSION "Run the focused tests." --actor orchestrator
agent-workflow watch SESSION --after 0 --timeout 300
agent-workflow progress SESSION "Focused tests passed." --actor child
agent-workflow ack SESSION MESSAGE_ID "Applied." --actor child --outcome applied
```

A steer is pending until correlated acknowledgement exists. Logs, terminal text, or a live tmux process do not prove delivery or application. The default adapter is `unsupported`. Use `steering_adapter = "control-file-v1"` only for a cooperative executor/wrapper that watches `AGENT_WORKFLOW_STEERING_INBOX` and writes a correlated `ack` through the bound CLI/control bridge. The durable delivery journal distinguishes `queued`, `delivered`, `applied`, `rejected`, `unsupported`, `expired`, and `failed`; an expired request cannot later become applied.

## Completion evidence

JSON Schema validation is only the first gate. A `completed` handoff must match the launch session/ticket/pack identity, name real base/head revisions, include at least one acceptance criterion with evidence, include at least one successful command receipt, and contain no unresolved items. `partial`, `failed`, and `blocked` handoffs must preserve their nonzero/skipped/unavailable command receipts and explain unresolved work. Invalid completion collection is durable evidence and forces a failed terminal status.

## Source cleanliness evidence

`worktree create` and launch preflight execute a fresh exact-root `git -C <root> status --porcelain`. The command preserves the operator's configured Git exclude view while still disabling pagers, editors, diff helpers, and credential prompts. Worktree creation returns bounded provenance—resolved executable, exact argv/root, return code, byte counts, and output digests—without exposing the unbounded filename list. A real tracked or untracked change remains fail-closed unless `--allow-dirty` is explicit.

## Interactive agent reuse

`task-complete` is terminal by default: after the host validates the completion intent it stops the interactive executor, seals the run, and lets tmux close the pane. Interactive agents can retain bounded assignment context only with the explicit `--keep-alive` mode. Reuse then requires:

- explicit prior task completion;
- an idle, live, unexpired session;
- the exact same worktree;
- a compatible agent policy;
- exact ticket/retry lineage for automatic reuse;
- correlated acknowledgement of the reassignment.

```bash
agent-workflow agent task-complete SESSION --actor AGENT --summary "Implemented parser" --keep-alive
agent-workflow agent candidates /path/to/worktree --ticket TICKET --pack PACK
agent-workflow agent reuse SESSION ./next-task.md --actor orchestrator --ticket TICKET --pack PACK
```

Similarity ranking helps an operator choose; it is not autonomous memory or routing authority.

## Workflow recovery

Workflow snapshots are immutable and event journals append-only. To recover after interruption:

1. verify the supplied snapshot is identical to the started snapshot;
2. run `workflow status` to refresh projections from the journal;
3. inspect child run evidence for running or terminal nodes;
4. run `workflow resume` to reconcile and schedule eligible work;
5. seal only after every node is terminal.

Never edit `workflow-status.json` to repair state. It is a projection.

## Comparative benchmark operations

Use `agent-workflow benchmark suite-export` to materialize the installed frozen suite. A planned run creates a coordinator and two sibling arm worktrees per case/repetition; the original repository is never a benchmark output target. `benchmark run` performs the automated pipeline and normally stops at `awaiting_human_review`. Use `benchmark review` to create a neutral left/right assignment and submit a completed rubric, then run `benchmark verify`.

Do not manually remove arm worktrees before consolidation. `benchmark cleanup` verifies the receipt and manifest, removes only the arm worktrees and branches, writes `cleanup.json`, and preserves the coordinator plus `benchmarks/runs/<run-id>`. A failed verification is a hard cleanup stop. Real-provider configurations should inherit only explicitly allowlisted credentials and must emit the complete usage contract when `provider_usage` is a required guardrail.

## Worktree and evidence cleanup

Do not delete a failed worktree or run directory automatically. Review the patch and receipts first. Removing a worktree does not remove the authoritative XDG run evidence.

Use `worktree remove` only after deciding whether the branch should be retained. Use uninstall only for installer-owned links and launchers; unrelated paths are left untouched.

## Host routing

Global instructions may recommend `agent-workflow` for bounded delegation. They are guidance, not a security boundary. Future installer-owned hooks may block a narrowly defined set of direct delegation commands, but only after explicit maintainer authorization and an audited break-glass path. See `BKL-007` in [BACKLOG.md](BACKLOG.md).

## Orchestrator registry and inbox

Run one foreground aggregate supervisor per orchestrator:

```bash
agent-workflow orchestrator watch ORCHESTRATOR_ID [--operator-override]
```

It acquires a durable single-writer lease, replays registered child journals
fairly after each timeout or wake hint, appends normalized metadata before
advancing each source cursor, and records redacted startup/replay/error/
shutdown metadata. A second active watcher exits with a stable diagnostic.
Normal stale-lock recovery requires recorded process identity/start evidence;
`--operator-override` is a bounded explicit recovery option for ambiguous
metadata and never rewrites source journals or sealed evidence.

The repository provides the `MSG-001` registry and aggregate inbox surfaces:

```text
agent-workflow orchestrator registry create ORCHESTRATOR_ID
agent-workflow orchestrator registry register ORCHESTRATOR_ID SESSION
agent-workflow orchestrator inbox import ORCHESTRATOR_ID
agent-workflow orchestrator inbox list ORCHESTRATOR_ID --after 0 --limit 100
```

The registry binds child sessions to immutable launch evidence and preserves source evidence on unregistration. Inbox import is delivery authority only; it does not replace child lifecycle authority. The foregroundable supervisor, shared wake loop, and safe orchestrator resume adapter remain `MSG-002` and `MSG-003`.

See [Durable two-way messaging](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md).
