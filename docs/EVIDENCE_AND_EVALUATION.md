# Evidence and evaluation

`agent-workflow` separates observations, durable records, sealed artifacts, and evaluator conclusions so that mutable convenience files cannot become authority by accident.

## Evidence hierarchy

1. **Operator observations:** terminal output, tmux capture, and logs help diagnose a run but do not authorize transitions.
2. **Durable records:** append-only message, lifecycle, assignment, and workflow journals reconstruct actions and state.
3. **Sealed run evidence:** the final receipt commits to required artifacts and their sizes and SHA-256 digests.
4. **Lifecycle receipts:** review, acceptance, and rejection bind an actor, reason, revision, and validated sealed evidence.
5. **Workflow receipt:** a terminal aggregate commits to the workflow snapshot, journal, node bindings, child receipts, approvals, retry lineage, and disposition.
6. **Evaluation evidence:** scorer receipts, score sets, trial evidence, and cohort comparisons bind conclusions to sealed source evidence.

Status JSON files and the SQLite evidence index are projections and may be regenerated.

Scope snapshots also distinguish source inventory from explicitly disposable operator-tool artifacts. When `.codebase-memory/` exists, the snapshot records its owner, mode, file count, byte size, deterministic tree digest, authorization state, cleanup policy, and size-limit result. Disposable classification prevents authorized local cache files from being mistaken for source changes, while unauthorized, unsafe, or oversized residue still fails the scope gate.

## Searchable operational projection

`agent-workflow index` materializes validated run, workflow, health, incident, permission, remediation, process, and performance fields into a host-local SQLite database. The projection exists to answer cross-run questions efficiently; it does not replace source artifacts or sealed receipts. Every imported file and record is traceable through relative path, sequence, schema identity, size, modification metadata, and SHA-256 digest.

The index intentionally excludes prompts, raw terminal/message bodies, large output logs, and credentials. Fixed read-only query kinds cover operational run views, incident and permission summaries, performance observations, workflow state, and index errors. Performance projections keep provider-billed and locally estimated cost separate and do not average across incompatible currencies. A complete rebuild from authoritative evidence is always supported. See [SQLite evidence index architecture](SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md).

SQLite is the operational catalog for the current single-host design. Privacy-governed Parquet snapshots and DuckDB analysis may be added later for large immutable cohorts; PostgreSQL or another shared service is deferred until multi-host orchestration is authorized and demonstrated.

## Provider event envelope

Structured provider evidence records a bounded raw JSONL stream and a normalized envelope. Usage-bearing records are explicitly classified as:

- `delta`: add each unique event exactly once;
- `cumulative`: use the latest monotonic total for that stream;
- `terminal`: authoritative terminal totals that replace, rather than add to, nonterminal usage.

A provider event ID is idempotent only when the repeated payload digest is identical. Conflicting reuse invalidates the usage evidence. Mixed nonterminal modes, non-finite values, decreasing cumulative totals, empty terminal usage, or incomplete cost metadata fail closed.

Mapped usage fields include input, cached input, cache-write input, output, reasoning output, and provider total tokens. Unknown or unavailable values remain `null`; absence is never converted to zero.

## Cost rules

Provider-billed cost and local catalog estimates are distinct fields. A local estimate must record catalog identity, currency, and sufficient token evidence. Currency values are never converted or combined implicitly. Retries and re-steers remain separate evidence dimensions rather than hidden inside one aggregate price.

## Trial evidence

A trial binds:

- task and repetition identity;
- source, optional prompt-pack checksum, model, executor, and executor-version identity;
- base revision and fixture revision;
- prompt, oracle, acceptance-command, scope-policy, budget, and scorer-version digests;
- final receipt, raw provider stream, normalized provider evidence, and score receipts;
- duration, usage, cost, retry, steering, error, and verdict fields;
- explicit exclusions or missing evidence.

Score-set verdicts are accepted only after their content-addressed scorer receipts and the sealed final receipt are validated. `completion_presence` is mandatory: a missing or invalid native completion collection produces an explicit `invalid` score rather than suppressing evaluation output.


## Evaluation and benchmark templates

The installed template catalog is sourced from `templates/evaluation/`:

| Template | Purpose |
|---|---|
| `evaluation-plan` | Objective, hypothesis, ticket/pack identity, provider/model, cohort controls, task set, metrics, stopping rules, budgets, privacy, and reproducibility inputs. |
| `benchmark-manifest` | Stable case IDs, prompt/input digests, expected evidence class, oracle/reference identity, fixture provenance, writable scope, cohort identity, and explicit unavailable-data markers. |
| `sealed-run-assessment` | Receipt and completion verification, structured-stream state, score/report/collection paths, scope audit, ledger evidence, contradictions, and lifecycle disposition. |
| `benchmark-report` | Baseline/candidate definitions, per-case outcomes, aggregates, missingness, regressions, usage/cost fields, and reproducible commands. |
| `ledger-row` | One evidence-first run/ticket/case row with source and pack identity, receipt digest, evaluation result, disposition, and durable evidence paths. |
| `lifecycle-archive` | Retention class, export inventory, transfer-checksum instructions, archive state, and cleanup state. |

Use `agent-workflow eval template KIND --output PATH`. Template output is canonical JSON and repeated rendering is byte-stable. Evaluation plans remain backward-compatible with the original required fields while the template supplies the richer planning surface.

## Benchmark manifests and reports

`agent-workflow eval validate-benchmark` validates the manifest schema, rejects duplicate case IDs and path traversal, and requires an explanatory reason for every unavailable case. An available case cannot carry an unavailable reason.

`agent-workflow eval benchmark-report` combines two immutable trial collections only after their declared source revision, optional pack checksum, model, executor, and executor version agree with the corresponding cohort definition. Case-level prompt, input, fixture, oracle, and reference digests are verified when declared. Trials outside the manifest are counted and named rather than silently discarded. The report preserves unavailable cases and missing metrics rather than filling them with zero or a fabricated verdict. Regressions are explicit per-case transitions from baseline `pass` to a non-pass candidate verdict. The aggregate comparison remains non-decisive when the configured evidence threshold is not met.

## Ledger and archive inputs

Every terminal sealed attempt now receives a post-seal `ledger-row.json`. When evaluation was planned, the runner also writes `scores/score-set.json`, `reports/evaluation.json`, and `reports/evaluation.md`; recovery finalization uses the same path. These projections summarize immutable evidence and never grant acceptance. Reports and ledger rows keep executor result, completion validity, budget-policy result, deterministic score, review disposition, and acceptance eligibility as separate fields.

## Supplemental evidence repair

A sealed run is never edited to repair a historical completion-format mismatch. `agent-workflow evidence repair` instead creates an append-only record under `evidence-repairs/<repair-id>/` containing the deterministic adapter identity, a canonical supplemental completion, a normalization-difference record, and a read-only repair receipt. The record binds the source session, exact final-receipt SHA-256, sealed source artifact path, and source artifact SHA-256. Source fingerprints before and after generation must match.

The only built-in adapter, `completion-normalize-v1`, translates legacy completion schema/session identity and review-disposition/result encodings. It preserves criteria, command evidence, revisions, changed files, unresolved findings, ticket/pack identity, and usage byte-for-byte at the JSON-value level. Legacy command strings, missing command receipts, or other substantive schema failures remain invalid and require a new authoritative run rather than an invented repair.

Verified repairs are exposed as `supplemental_repairs` in evaluation reports and ledger rows and as the `repairs` SQLite view. They preserve both original and supplemental interpretations, always carry `acceptance_authority: false`, and cannot make an originally ineligible run acceptable. Receipt or artifact drift, writable artifacts, unsafe paths, and symlinks exclude the repair from projections and make direct verification fail.

`agent-workflow eval ledger-row` verifies the final receipt and score-set chain before exposing an evaluation result. An unreadable, absent, tampered, or unverified score remains `null` with `evaluation_state: not_verified`. Lifecycle disposition is derived from the immutable receipt chain, not mutable `status.json` fields. Exported-run assessment additionally binds a one-trial collection back to the run ID, final-receipt digest, sealed provider-evidence digest, raw-stream digest, and verified score verdict before marking the collection complete.

`agent-workflow eval archive-plan` inventories regular non-symlink run files in stable path order, excluding `*.sha256`, `MANIFEST.sha256`, and transient lock files. The resulting plan says how to generate and verify a transfer checksum beside the archive. Such checksum files remain ignored repository-transfer artifacts and are never contract prerequisites.

## Cohort comparison

Baseline and candidate cohorts must contain matching task/repetition identities and compatible evidence semantics. Comparisons report descriptive rates and paired outcomes. They do not declare a winner when sample size or configured evidence is insufficient.

Real-provider comparisons remain an operator-run gate. Subscription-backed CLI sessions are the default; API credentials are optional explicit cohorts. Before publishing a claim, pin executor version, model, authentication/billing mode, environment, tool policy, prompt/fixture revision, repetitions, exclusions, cost semantics, and cache policy. Track external execution evidence under `BKL-004` in [BACKLOG.md](BACKLOG.md).

## Adopted paired comparative benchmark

The initial comparative benchmark design is defined in [Comparative benchmark specification](COMPARATIVE_BENCHMARK_SPEC.md) and governed by [DEC-008](DECISIONS/DEC-008-INITIAL-COMPARATIVE-BENCHMARK.md). Each repetition runs the same canonical multiphase task concurrently in isolated `control_raw/v1` and `workflow_full/v1` worktrees. Pair identity binds the canonical task and environment while separately recording the intentionally different constraint wrapper and effective prompt.

The first fixture is the synthetic visual priority picker. Its initial composite is 70% deterministic machine score and 30% blinded human visual score; both components remain visible and incomplete human review cannot produce a final composite. The canonical task, hidden tests, 100-point allocation, visual captures, rubric, phase prompts, and writable scope are frozen in the suite requirement-to-evaluation matrix.

The modular `agent_workflow.benchmarking` implementation creates the coordinator and paired arm worktrees, synchronizes each phase, records phase/arm/pair/run metrics, captures desktop/tablet/mobile evidence, runs command-owned scorers, creates neutral left/right reviewer bundles, consolidates digests, verifies the final run, and removes only verified arm worktrees. Installed packages can materialize the suite with `agent-workflow benchmark suite-export`. See [Comparative benchmark implementation](COMPARATIVE_BENCHMARK_IMPLEMENTATION.md).

[DEC-002](DECISIONS/DEC-002-COMPARATIVE-BENCHMARK-OPERATING-POLICY.md) makes subscription-backed CLI sessions the default and API credentials optional explicit adapters. Authentication status, operating policy, retry attempts, cache treatment, assistance cohort, runtime attestation, and cost semantics are sealed into each run. Subscription use normally has no attributable provider-billed per-run amount; reports preserve a separate API-equivalent estimate and optional subscription allocation instead of treating it as zero cost. Winner-enabled cohorts use paired bootstrap intervals and minimum effect/regression thresholds.

The included browser path supports development evidence. Publication runtime sealing and browser/font digest enforcement are implemented; `BKL-010` retains the operator-built immutable image evidence. Real subscription/API cohorts remain gated by `BKL-004` plus the existing isolation, privacy, and compatibility prerequisites.
