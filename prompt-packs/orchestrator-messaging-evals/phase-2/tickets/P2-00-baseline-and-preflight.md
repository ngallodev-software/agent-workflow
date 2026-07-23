# P2-00 — Metrics and deterministic regression eval

## Objective

Add sealed normalized metrics/control artifacts and a small deterministic
`normalize_records(records)` regression fixture. Preserve raw executor streams.

## Required evidence

- For `orchestrator`, `child:<id>`, `verification`, and `total`, capture nullable
  input/cached-input/output/provider-total/cost/currency, monotonic elapsed
  time, first-output latency, retry/error records, and steer counts.
- Add JSON schemas; seal artifacts; surface summaries in reports without
  recomputing provider facts.
- Fixture uses exact known tests, evaluator-only hidden cases through existing
  oracle references, command/scope receipts, mutation failures, and stable
  re-scoring.

## Writable paths

`schemas/`, runner/executor/receipt/reporting modules, deterministic fixture
files, matching tests, and documentation only.

## Acceptance criteria

One sealed run reports nullable stage and total token/cost/time/error facts;
the baseline/mutations fail and the repaired deterministic fixture passes known
and hidden cases; a repeated score has the same verdict.

## Tests

Schema validation, provider-usage normalization, runner sealing, fixture,
mutation, oracle-leak, and repeat-score tests are all required.

## Stop

Never convert absent cache tokens to zero or infer child activity from prose.
