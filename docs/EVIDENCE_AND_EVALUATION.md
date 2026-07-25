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
- base revision and fixture revision;
- prompt, oracle, acceptance-command, scope-policy, budget, and scorer-version digests;
- final receipt, raw provider stream, normalized provider evidence, and score receipts;
- duration, usage, cost, retry, steering, error, and verdict fields;
- explicit exclusions or missing evidence.

Score-set verdicts are accepted only after their content-addressed scorer receipts and the sealed final receipt are validated.

## Cohort comparison

Baseline and candidate cohorts must contain matching task/repetition identities and compatible evidence semantics. Comparisons report descriptive rates and paired outcomes. They do not declare a winner when sample size or configured evidence is insufficient.

Real paid-provider comparisons remain an operator-run gate. Before publishing a claim, pin executor version, model, environment, tool policy, prompt/fixture revision, repetitions, exclusions, billing meaning, and cache policy. Track that work under `BKL-004` in [BACKLOG.md](../BACKLOG.md).
