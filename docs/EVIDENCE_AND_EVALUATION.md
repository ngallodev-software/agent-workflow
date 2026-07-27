# Evidence and evaluation

`agent-workflow` separates observations, durable records, sealed artifacts, and evaluator conclusions so that mutable convenience files cannot become authority by accident.

## Evidence hierarchy

1. **Operator observations:** terminal output, tmux capture, and logs help diagnose a run but do not authorize transitions.
2. **Durable records:** append-only message, lifecycle, assignment, and workflow journals reconstruct actions and state.
3. **Sealed run evidence:** the final receipt commits to required artifacts and their sizes and SHA-256 digests.
4. **Lifecycle receipts:** review, acceptance, and rejection bind an actor, reason, revision, and validated sealed evidence.
5. **Workflow receipt:** a terminal aggregate commits to the workflow snapshot, journal, node bindings, child receipts, approvals, retry lineage, and disposition.
6. **Evaluation evidence:** scorer receipts, score sets, trial evidence, and cohort comparisons bind conclusions to sealed source evidence.

Status JSON files are projections and may be regenerated.

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

Score-set verdicts are accepted only after their content-addressed scorer receipts and the sealed final receipt are validated.


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

`agent-workflow eval ledger-row` verifies the final receipt and score-set chain before exposing an evaluation result. An unreadable, absent, tampered, or unverified score remains `null` with `evaluation_state: not_verified`. Lifecycle disposition is derived from the immutable receipt chain, not mutable `status.json` fields. Exported-run assessment additionally binds a one-trial collection back to the run ID, final-receipt digest, sealed provider-evidence digest, raw-stream digest, and verified score verdict before marking the collection complete.

`agent-workflow eval archive-plan` inventories regular non-symlink run files in stable path order, excluding `*.sha256`, `MANIFEST.sha256`, and transient lock files. The resulting plan says how to generate and verify a transfer checksum beside the archive. Such checksum files remain ignored repository-transfer artifacts and are never contract prerequisites.

## Cohort comparison

Baseline and candidate cohorts must contain matching task/repetition identities and compatible evidence semantics. Comparisons report descriptive rates and paired outcomes. They do not declare a winner when sample size or configured evidence is insufficient.

Real paid-provider comparisons remain an operator-run gate. Before publishing a claim, pin executor version, model, environment, tool policy, prompt/fixture revision, repetitions, exclusions, billing meaning, and cache policy. Track that work under `BKL-004` in [BACKLOG.md](BACKLOG.md).
