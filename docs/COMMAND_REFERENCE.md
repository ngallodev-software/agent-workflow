# Command reference

> The hierarchy contract, journal/replay, and sealed-receipt authority layer is implemented as a review-gated built-in feature API. It does not yet expose team-runtime or tmux-topology commands; this reference lists only supported public CLI behavior.

The parser-derived command catalog is authoritative for agent execution. Run `agent-workflow commands --json` for the full machine-readable contract or `agent-workflow commands --role ROLE --format markdown` for a role-scoped command card. Agents should invoke represented commands directly and use `--help` only after a catalog/version mismatch, an argument error, or when a required command is absent. Global `--json`, `--config PATH`, and `--no-plugins` may appear before or after the subcommand; tokens after launch `--` belong to the delegated command.

## Top-level

```text
agent-workflow [--config PATH] [--json] [--no-plugins] COMMAND ...
agent-workflow --version
agent-workflow doctor
agent-workflow commands [--format json|markdown] [--role all|orchestrator|implementation|review]
agent-workflow config show
agent-workflow plugins list
agent-workflow completion bash|zsh|tcsh
agent-workflow orchestrator registry create ORCHESTRATOR_ID [--workflow-id ID]
agent-workflow orchestrator registry inspect ORCHESTRATOR_ID
agent-workflow orchestrator registry register ORCHESTRATOR_ID SESSION
agent-workflow orchestrator registry unregister ORCHESTRATOR_ID SESSION --state completed|abandoned
agent-workflow orchestrator inbox import ORCHESTRATOR_ID [--session-id SESSION]
agent-workflow orchestrator inbox list ORCHESTRATOR_ID [--after SEQUENCE] [--limit N]
agent-workflow orchestrator inbox read ORCHESTRATOR_ID [--event-id UUID] [--include-content]
```

`commands` is offline and generated from the exact installed parser, including enabled plugin command groups and their installed-distribution provenance. Every new launch stores the full catalog and a role-scoped command card in the sealed run, binds their digests into launch-contract v2, and exports their paths to the child process. `doctor` is offline. It probes only local binaries and local `--version`/`--help` surfaces.

### Trusted plugins

Plugin candidates are discovered from Python package metadata but imported only when their entry-point names are listed in `[plugins].enabled`. `plugins list` reports discovered, enabled, loaded, suppressed, and validated package-resource state. Enabled plugins may declare digest-bound schema and asset files beneath installed Python packages; traversal, missing files, collisions, and digest mismatches fail before registry activation. `--no-plugins` suppresses all configured imports and restores the core-only parser for recovery. Plugins are trusted executable code and never gain authority merely by being present. See [Trusted plugin API](PLUGIN_API.md).

## Worktrees and sessions

```text
agent-workflow worktree create REPO TICKET BASE [--dest PATH] [--branch NAME] [--allow-dirty]
agent-workflow worktree list REPO
agent-workflow worktree remove REPO WORKTREE [--delete-branch] [--force]

agent-workflow launch SESSION WORKDIR PROMPT
  [--ticket ID] [--tier low|medium|high|critical] [--pack PACK] [--job JOB]
  [--agent-name NAME] [--agent-class CLASS] [--executor NAME] [--model MODEL]
  [--allow-no-go-model] [--evaluation PLAN] [--structured]
  [--interactive|--no-interactive] [--allow-dirty]
  [--pane-limit-action prompt|close-idle|non-interactive|cancel]

agent-workflow launch SESSION WORKDIR PROMPT -- COMMAND...
agent-workflow list
agent-workflow archive SESSION... [--verified] [--dry-run] [--reason TEXT]
agent-workflow clear SESSION... [--verified] [--dry-run] [--reason TEXT]
agent-workflow archive --all-verified [--verified] [--dry-run] [--reason TEXT]
agent-workflow status SESSION [--capture N]
agent-workflow attach SESSION
agent-workflow tail SESSION [--lines N]
agent-workflow interrupt SESSION
agent-workflow terminate SESSION [--grace-seconds N]
agent-workflow kill SESSION
agent-workflow restart SESSION [--new-session NAME]
```

Configured launches enforce class/executor/model allowlists and permission arguments. Implementation launches are interactive by default; exploration/review classes are non-interactive by default. At a full tmux pane limit, the CLI reports idle candidates and requires an explicit close-idle, structured non-interactive, or cancel choice. A no-go model requires `--allow-no-go-model`, which is recorded. `--structured` and native interactive TUI mode are mutually exclusive. Git worktrees must be clean unless `--allow-dirty` is explicit; retries preserve prior evidence and lineage.

`archive` is the recoverable `list` cleanup operation; `clear` is an alias. It never deletes evidence. A run must have a valid sealed final receipt, completed/valid completion collection, authoritative accepted lifecycle receipt, matching accepted revision, and a closed tmux session. `--all-verified` skips runs that fail a gate and reports the reason. Use `--dry-run` first. A real move requires the explicit `--verified` confirmation and writes a read-only archive manifest under the state archive root.

## Supervisor

The aggregate child-journal supervisor runs in the foreground and treats the
hashed tmux channel only as a wake hint. Durable journals, the inbox, and
per-child cursors remain authoritative:

```text
agent-workflow orchestrator watch ORCHESTRATOR_ID
  [--interval-seconds N] [--poll-seconds N]
  [--batch-size N] [--max-per-child N] [--max-cycles N]
  [--operator-override]
```

`--operator-override` is a bounded local recovery authorization for ambiguous
stale supervisor-lock metadata. It never rewrites source journals or sealed
lifecycle evidence; normal recovery relies on process identity/start evidence.

```text
agent-workflow supervisor once
  [--session SESSION]...
  [--capture-interactive|--no-capture-interactive]
  [--capture-lines N]
  [--probe-stalled|--no-probe-stalled]
  [--interrupt-stalled|--no-interrupt-stalled]
  [--restart-orphaned|--no-restart-orphaned]
  [--max-remediation-attempts N]
  [--sync-index|--no-sync-index]

agent-workflow supervisor run
  [the same policy options]
  [--interval-seconds N]
  [--max-cycles N]
```

`once` performs one evidence, reconciliation, diagnosis, and remediation cycle. `run` repeats the same deterministic cycle in the foreground. `--session` is repeatable and limits scope. Interactive capture and one bounded progress probe follow configuration defaults; interrupt and orphan restart are disabled unless explicitly enabled. All performed actions are journaled with rule IDs and attempt ceilings. Incremental SQLite reconciliation is enabled by default and may be disabled for a cycle with `--no-sync-index`; an indexing error is reported but does not stop supervision. Global `--json` prints the cycle report as structured data.

## Searchable evidence index

```text
agent-workflow index status
agent-workflow index sync [--run SESSION] [--active-only]
agent-workflow index rebuild [--run SESSION] [--active-only]
agent-workflow index verify [--full] [--review SESSION]
agent-workflow index query runs|incidents|permissions|performance|workflows|workflow-nodes|errors
  [--session SESSION] [--state STATE] [--category CATEGORY]
  [--executor NAME] [--model MODEL] [--pack PACK] [--limit N]
```

`status` reports the database path, schema/application versions, source and indexed run counts, freshness, journal mode, historical quarantines, and blocking index errors. `sync` reconciles only changed source directories; `rebuild` replaces the projection from authoritative JSON/JSONL and sealed receipts. `verify` always runs SQLite integrity and foreign-key checks; `--full` additionally rehashes indexed source files and reports preserved legacy artifacts separately from blocking current mismatches. `--review SESSION` adds a separately named `review_valid` result for that indexed sealed run and its direct completion/lifecycle gate; it never changes global `valid`. Unsafe paths, malformed current schemas, and changed current evidence remain failures.

`query` exposes fixed, parameterized operational views rather than arbitrary SQL. JSON output uses an `agent-workflow/index-query/v1` envelope containing freshness, stale/error counts, and `rows`; human output prints the same freshness summary before the table. Rows include source provenance. The index is disposable: lifecycle, permission, workflow, remediation, review, and acceptance authority remains in source artifacts and sealed receipts. Raw prompts, terminal/message bodies, and large logs are not copied into SQLite. See [SQLite evidence index architecture](SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md).

The explicit-only integrity foundation is separate from run artifacts and the legacy `index_errors` projection:

```text
agent-workflow index integrity migrate
agent-workflow index integrity record SESSION ARTIFACT ERROR_ID CATEGORY DETAIL
```

These commands append versioned v2 records with exact identity, generator identity/version, and a deterministic verified-input snapshot digest. Normal `rebuild`, `sync`, and `verify` never write the authority. Migration records carry the legacy ledger digest for lineage only; legacy contents remain untrusted.

## Durable messages

```text
agent-workflow steer SESSION TEXT --actor ID
agent-workflow progress SESSION TEXT --actor ID
agent-workflow ack SESSION MESSAGE_UUID TEXT --actor ID [--outcome applied|rejected]
agent-workflow watch SESSION [--after SEQUENCE] [--timeout SECONDS]
```

These commands append validated fsynced records. `watch` replays the journal and may use a best-effort tmux wakeup hint. A steer is pending until correlated evidence proves acknowledgement/application. Executors default to `steering_adapter = "unsupported"`; a cooperative wrapper may explicitly select `control-file-v1`, which publishes an immutable bounded request under the run handoff and records delivery outcomes in `steering-delivery.jsonl`. `--outcome rejected` is distinct from application failure or silence.

`status`/`observe` reports runner heartbeat, executor/process liveness, semantic-progress age/source, output/event/terminal activity, permission state, tmux liveness, pane death, and output-capture exhaustion independently. A fresh heartbeat is liveness evidence only; it cannot prevent `possibly_stalled` when every semantic-progress source is stale.

Completed handoffs must contain matching session/ticket/pack identity, substantive revisions, criterion evidence, and command receipts. A schema-valid placeholder completion is collected as invalid and makes the run fail rather than silently sealing success. Failed, partial, and blocked completions may retain nonzero commands but must state unresolved evidence.

## Interactive agent context and reuse

```text
agent-workflow agent context SESSION
agent-workflow agent task-complete SESSION --actor ID --summary TEXT [--tag TAG] [--file PATH] [--keep-alive]
agent-workflow agent candidates WORKDIR [--ticket ID] [--pack ID] [--retry-of ID] [--agent-class CLASS] [--tag TAG]
agent-workflow agent reuse SESSION PROMPT --actor ID [--ticket ID] [--pack ID] [--retry-of ID] [--tag TAG]
agent-workflow agent auto-reuse WORKDIR PROMPT --actor ID [--ticket ID] [--pack ID] [--retry-of ID] [--agent-class CLASS] [--tag TAG]
```

`task-complete` validates the handoff, emits a durable child-to-parent completion, and is terminal by default: the host stops the still-live executor, seals the run, and closes its tmux pane. `--keep-alive` is the explicit exception for a cooperative interactive executor that must remain available for same-worktree reuse. A steer remains pending until its correlated acknowledgement; only an adapter that consumes the immutable steering inbox can claim application.

## Workflow graphs

```text
agent-workflow workflow validate SNAPSHOT
agent-workflow workflow template pipeline SPEC.json --output SNAPSHOT.json
agent-workflow workflow template parallel-review-fan-in SPEC.json --output SNAPSHOT.json
agent-workflow workflow template implementation-independent-review SPEC.json --output SNAPSHOT.json
agent-workflow workflow start RUN_DIR SNAPSHOT
agent-workflow workflow status RUN_DIR SNAPSHOT
agent-workflow workflow resume RUN_DIR SNAPSHOT
agent-workflow workflow seal RUN_DIR SNAPSHOT
agent-workflow workflow verify RUN_DIR SNAPSHOT
```

`start` stores the canonical normalized snapshot and schedules eligible nodes. Later status/resume/seal/verify calls must supply the same snapshot digest; a substituted snapshot is rejected. Status is reconstructed from append-only events. Approval nodes verify canonical lifecycle receipts. Result bindings use bounded RFC 6901 JSON Pointers over sealed ancestor results. `seal` requires every node to be terminal and writes a read-only aggregate receipt.

Template request files contain `workflow_id`, `pack_id`, `pack_manifest_sha256`, and template-specific `parameters`. Expansion is deterministic and produces the same canonical snapshot schema used by hand-authored workflows.

## Review and acceptance

```text
agent-workflow review SESSION --actor ID --reason TEXT
agent-workflow accept SESSION --actor ID --reason TEXT --revision SHA
agent-workflow force-accept SESSION --actor ID --reason TEXT --acknowledge FORCE-ACCEPT
agent-workflow reject SESSION --actor ID --reason TEXT
```

Review/accept/reject append immutable lifecycle receipts. Acceptance requires a prior review, valid final seal and collected completion, exact head revision, stable passing scores when evaluation is required, and reviewer independence for high/critical tiers.

`force-accept` is a separate local operator override for a terminal run when the normal gate cannot be satisfied. It requires the exact `FORCE-ACCEPT` acknowledgement and a non-empty reason, writes the immutable `force-accept-receipt.json`, and reports `force-accepted` distinctly from normal `accepted`. It never changes normal review, completion, evaluation, or final-receipt evidence. The actor label is not authenticated human authorization; HARD-007 remains the required future security boundary. Running/launched runs, missing or invalid sealed evidence, and repeated overrides are rejected.

## Evaluation

```text
agent-workflow eval template evaluation-plan|benchmark-manifest|sealed-run-assessment|benchmark-report|ledger-row|lifecycle-archive --output PATH
agent-workflow eval validate PLAN [--pack PACK]
agent-workflow eval validate-benchmark MANIFEST [--pack PACK]
agent-workflow eval score RUN [--output-dir PATH] [--oracle-root PATH]
agent-workflow eval report RUN [--format json|markdown] [--output PATH]
agent-workflow eval collect RUN... --output TRIALS.json
agent-workflow eval compare BASELINE.json CANDIDATE.json --output PATH
agent-workflow eval benchmark-report MANIFEST BASELINE.json CANDIDATE.json --output PATH [--markdown PATH]
agent-workflow eval ledger-row RUN --output PATH
agent-workflow eval archive-plan RUN --output PATH [--retention-class transient|standard|release|legal-hold]
agent-workflow eval inspect PROMPT --executor codex|claude --model MODEL --dockerfile FILE --log-dir DIR
agent-workflow eval swebench-prediction RUN --instance-id ID --model MODEL --output FILE.jsonl
agent-workflow ledger PACK [--runs-root PATH] [--output PATH]
```

`eval collect` accepts only sealed runs with complete provider evidence. `validate-benchmark` enforces stable case IDs, unique task/repetition identities, normalized writable scopes, and explicit unavailable-data reasons. `benchmark-report` verifies declared source, optional pack-checksum, model, executor, executor-version, prompt/input, fixture, oracle, and reference identity before combining cohorts; unmatched trials are reported rather than ignored. Provider-billed and locally estimated cost remain separate, and cost comparisons are omitted when currency or local price-catalog identity differs. `archive-plan` excludes transient lock and checksum-transfer files; transfer checksums are generated beside archives, not tracked in the repository.

## Paired comparative benchmarks

```text
agent-workflow benchmark suite-export DEST [--benchmark-id priority-picker-v1|priority-picker-v2|priority-picker-fast-v1] [--force]
agent-workflow benchmark validate SPEC [--executor CONFIG]
agent-workflow benchmark auth-check CONFIG
agent-workflow benchmark readiness SPEC --executor CONFIG [--policy FILE] [--runtime-lock FILE]
agent-workflow benchmark runtime-attest LOCK [--claim-level development|internal|publication]
agent-workflow benchmark runtime-seal BASE_LOCK OUTPUT --container-image IMAGE@sha256:DIGEST
agent-workflow benchmark fixture-create SPEC DEST [--force]
agent-workflow benchmark plan SPEC --executor CONFIG --repo REPO
  [--base-ref REF] [--run-id ID] [--repetitions N]
  [--worktree-root PATH] [--allow-dirty]
  [--policy FILE] [--runtime-lock FILE]
  [--assistance-cohort unassisted|assisted]
agent-workflow benchmark run RUN
agent-workflow benchmark resume RUN
agent-workflow benchmark status RUN
agent-workflow benchmark live-start RUN
agent-workflow benchmark live-stop RUN
agent-workflow benchmark visual-capture RUN
agent-workflow benchmark score RUN
agent-workflow benchmark consolidate RUN
agent-workflow benchmark review RUN --reviewer ID [--input FILE]
agent-workflow benchmark report RUN
agent-workflow benchmark verify RUN
agent-workflow benchmark cleanup RUN [--stop-live-apps] [--remove-worktrees]
```

`readiness` now performs the same non-mutating two-pane capacity check used by execution, so a crowded invoking window fails before planning or layout changes.

The built-in suite family includes historical `priority-picker-v1`, corrected full `priority-picker-v2`, and compact `priority-picker-fast-v1`. Subscription-backed Codex/Claude CLI sessions are the default; API credentials are optional explicit profiles. `run` must start inside tmux, creates exactly two additional panes in the invoking window, reuses one stable pane per arm, and streams provider output visibly. It then starts one live server per selected arm, captures browser evidence from those URLs, scores, consolidates, reports, and preserves the applications while awaiting blinded human review. `status` reports pane IDs and live URLs; `live-start`/`live-stop` manage review servers without deleting evidence. Default `cleanup` preserves apps and worktrees. Destructive removal requires verified evidence and stopped apps. Reports retain timing, usage/cost semantics, eligibility, confidence intervals, human review, and the 70/30 composite. See the [implementation](COMPARATIVE_BENCHMARK_IMPLEMENTATION.md) and [operations guide](COMPARATIVE_BENCHMARK_OPERATIONS.md).

## Prompt packs

```text
agent-workflow pack scaffold DEST [--phases N] [--name NAME]
agent-workflow pack validate SOURCE [--verify-checksums]
agent-workflow pack checksum SOURCE
agent-workflow pack archive SOURCE OUTPUT.tar.zst
```

Validation checks required files, manifests, cross-phase dependency DAGs, result contracts, paths, and bounded portable assets. It does not require the ignored `MANIFEST.sha256`, which would become stale during implementation. `--verify-checksums` opts into checking that transfer artifact; `pack checksum` creates it. Archive creation is deterministic when GNU tar and zstd are available.

## MCP entry point

```text
agent-workflow-mcp [--config PATH] [--repo-root PATH]
```

The optional current server is local stdio and bounded/read-only, with `pack_validate`; capability and parser-derived command-catalog resources; and run/status/message/receipt/verified-command-context resources. It is a separate executable, not a top-level `agent-workflow mcp` command. Install with the `mcp` optional extra. `--repo-root` constrains pack validation to an explicit repository root; the configured state root still governs run resources.

Current command resources are `agent-workflow://capabilities`, `agent-workflow://commands`, `agent-workflow://commands/{orchestrator|implementation|review}`, `agent-workflow://runs/{session_id}/command-context`, and `agent-workflow://runs/{session_id}/command-card`. These are read-only discovery/audit resources. They do not authorize a CLI command or dynamically expose the CLI as MCP tools. Planned mutation tools are documented but not implemented.
