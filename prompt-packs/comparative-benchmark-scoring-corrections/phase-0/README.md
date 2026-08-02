# Phase 0 — contract and policy freeze

## Objective

Create the exact corrected scoring contract and decide how efficiency interacts with winner declarations before implementation changes begin.

## Tickets

| Ticket | Tier | Risk | Dependencies | Reviewer requirement |
|---|---|---|---|---|
| BENCH-CORR-001 | C | Critical | None | Independent benchmark-contract reviewer |
| BENCH-CORR-010 | B | Medium | None | Benchmark-methodology reviewer |

The tickets may be analyzed in parallel. Their decisions must be reconciled in one phase gate.

## Exit gate

- exact point arithmetic validates;
- benchmark/scorer version boundary is explicit;
- v1 preservation is explicit;
- duplicate-credit policy is explicit;
- efficiency remains separate from quality unless a formally approved rule says otherwise;
- no scorer implementation ticket starts before independent acceptance.
