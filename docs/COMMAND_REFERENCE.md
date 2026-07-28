# Command reference

The parser-derived command catalog is authoritative for agent execution. Run `agent-workflow commands --json` for the full machine-readable contract or `agent-workflow commands --role ROLE --format markdown` for a role-scoped command card. Agents should invoke represented commands directly and use `--help` only after a catalog/version mismatch, an argument error, or when a required command is absent. Global `--json` and `--config PATH` may appear before or after the subcommand; tokens after launch `--` belong to the delegated command.

## Top-level

```text
agent-workflow [--config PATH] [--json] COMMAND ...
agent-workflow --version
agent-workflow doctor
agent-workflow commands [--format json|markdown] [--role all|orchestrator|implementation|review]
agent-workflow config show
agent-workflow completion bash|zsh|tcsh
```

`commands` is offline and generated from the exact installed parser. Every new launch stores the full catalog and a role-scoped command card in the sealed run, binds their digests into launch-contract v2, and exports their paths to the child process. `doctor` is offline. It probes only local binaries and local `--version`/`--help` surfaces.

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
agent-workflow status SESSION [--capture N]
agent-workflow attach SESSION
agent-workflow tail SESSION [--lines N]
agent-workflow interrupt SESSION
agent-workflow terminate SESSION [--grace-seconds N]
agent-workflow kill SESSION
agent-workflow restart SESSION [--new-session NAME]
```

Configured launches enforce class/executor/model allowlists and permission arguments. Implementation launches are interactive by default; exploration/review classes are non-interactive by default. At a full tmux pane limit, the CLI reports idle candidates and requires an explicit close-idle, structured non-interactive, or cancel choice. A no-go model requires `--allow-no-go-model`, which is recorded. `--structured` and native interactive TUI mode are mutually exclusive. Git worktrees must be clean unless `--allow-dirty` is explicit; retries preserve prior evidence and lineage.

## Durable messages

```text
agent-workflow steer SESSION TEXT --actor ID
agent-workflow progress SESSION TEXT --actor ID
agent-workflow ack SESSION MESSAGE_UUID TEXT --actor ID
agent-workflow watch SESSION [--after SEQUENCE] [--timeout SECONDS]
```

These commands append validated fsynced records. `watch` replays the journal and may use a best-effort tmux wakeup hint. A steer is pending until correlated evidence proves acknowledgement/application.

## Interactive agent context and reuse

```text
agent-workflow agent context SESSION
agent-workflow agent task-complete SESSION --actor ID --summary TEXT [--tag TAG] [--file PATH]
agent-workflow agent candidates WORKDIR [--ticket ID] [--pack ID] [--retry-of ID] [--agent-class CLASS] [--tag TAG]
agent-workflow agent reuse SESSION PROMPT --actor ID [--ticket ID] [--pack ID] [--retry-of ID] [--tag TAG]
agent-workflow agent auto-reuse WORKDIR PROMPT --actor ID [--ticket ID] [--pack ID] [--retry-of ID] [--agent-class CLASS] [--tag TAG]
```

`task-complete` is the only `busy -> idle_reusable` transition. Reuse is restricted to the same worktree; automatic reuse requires exact ticket/retry lineage and remains pending until acknowledgement.

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
agent-workflow reject SESSION --actor ID --reason TEXT
```

Review/accept/reject append immutable lifecycle receipts. Acceptance requires a prior review, valid final seal and collected completion, exact head revision, stable passing scores when evaluation is required, and reviewer independence for high/critical tiers.

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
