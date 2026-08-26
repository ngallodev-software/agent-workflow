# DEC-002 — Comparative benchmark operating policy

- **Status:** decided
- **Date:** 2026-08-01
- **Scope:** real and synthetic paired comparative benchmark runs
- **Complements:** [DEC-008](DEC-008-INITIAL-COMPARATIVE-BENCHMARK.md)
- **Implementation:** current benchmark modules, schemas, built-in assets, and acceptance journeys

## Decision

The comparative benchmark uses three versioned operating-policy profiles:

| Profile | Claim level | Paired repetitions | Winner claim |
|---|---|---:|---|
| `comparative-development/v1` | development | 1 | disabled |
| `comparative-internal/v1` | internal | 10 | enabled after 10 eligible pairs |
| `comparative-publication/v1` | publication | 20 | enabled after 20 eligible pairs |

The profiles are machine-readable in the materialized built-in `priority-picker-v1` suite under `policies/`. Canonical packaged copies live in the shared benchmark asset layers and are copied and hashed into every run.

### Authentication

Subscription-backed provider CLI sessions are the default authentication mechanism. The initial adapters are the Codex CLI and Claude Code CLI. A subscription profile must:

- verify the existing authenticated session before creating worktrees;
- pass the phase prompt through standard input rather than command-line arguments;
- retain only the explicitly allowlisted session/configuration environment;
- refuse to run when a provider API-key or access-token environment variable is present;
- prohibit silent fallback from subscription authentication to API billing.

API-key and access-token execution is not supported in the 0.9 line. Subscription profiles list provider credential environment-variable names only so the preflight can fail closed when ambient API billing credentials are present. Credentials are never stored in benchmark evidence; only bounded authentication status, mode, command identity, and output digests are recorded.

### Models and executors

The operating policy does not hard-code a universal model name. Before an internal or publication cohort, the operator must pin a provider-supported model and exact executor configuration, then keep that configuration unchanged across both arms and every eligible repetition. Different providers, models, executor versions, authentication modes, or pricing catalogs are separate cohorts and must not be pooled.

### Cost semantics

Reports preserve three different values:

1. `provider_billed_cost`: a directly attributable per-run amount emitted by a metered provider path;
2. `local_estimated_cost`: an API-equivalent estimate derived from sealed token evidence and a named price catalog, or an explicitly supplied local estimate;
3. `subscription_allocated_cost`: an optional accounting allocation of a subscription fee, clearly labeled as an allocation rather than provider billing.

Subscription-session runs normally have `provider_billed_cost = null`. They are not described as free. Cost comparisons are omitted when required evidence, currency, or price-catalog identity is incompatible.

### Cache treatment

Provider-managed caching is allowed only when cached and cache-write token fields are recorded. A cohort may not mix cache policies or authentication/billing paths. Cache state is reported, not guessed. If a provider cannot expose the required fields, that limitation remains visible and any configured completeness guardrail applies.

### Retries and interruption

Each pair may receive one infrastructure-only retry. A retry uses fresh paired worktrees, a new attempt identity, and a new pair nonce. All attempts are retained; only the terminal eligible attempt is selected for scoring. Task failure, low score, or incomplete implementation does not qualify as infrastructure failure.

An interrupted pair is discarded and retried from fresh paired worktrees. It is never resumed as though the arms remained temporally comparable.

### Human assistance

`unassisted` and `assisted` are separate cohorts. Assistance state is sealed in the run plan and may not change after execution begins. The default profiles are unassisted. An assisted cohort must define and record the identical assistance channel available to both arms.

### Statistical decision rule

Winner-enabled profiles use paired deltas and a deterministic 95% paired-bootstrap confidence interval. A winner requires:

- the profile's minimum eligible pair count;
- a composite-score improvement of at least 5 points;
- the confidence interval to support the configured direction;
- no machine-score regression greater than 3 points;
- no human-visual regression greater than 3 points;
- no required guardrail or comparability failure.

Machine, human, composite, time, tokens, and cost remain separately reported even when no winner is declared.

### Visual evidence

Development claims may use the pinned host-detected runtime lock. Publication claims require a runtime lock sealed from inside a content-addressed browser container and containing the browser executable digest plus a digest for every declared font. Three blinded reviewers are required for publication, two for internal claims, and one for development.

## Rationale

The benchmark is intended to measure the effect of `agent-workflow`, not differences in credentials, provider access, retry opportunity, cache behavior, or visual runtime. Subscription-only authentication matches normal interactive use and deliberately excludes API-key/access-token billing paths in the 0.9 line. Explicit profiles make every material policy choice inspectable and prevent an operator from changing repetitions, retry rules, or winner thresholds after observing results.

## Consequences

- `DEC-002` is closed by executable policy profiles and validation.
- Real provider execution no longer requires API keys.
- Production benchmark execution supports only Codex and Claude subscription sessions; synthetic execution remains development/test-only.
- `BKL-004` retains the external execution/acceptance evidence gate; the runner, adapters, readiness checks, statistics, and reporting mechanics are implemented.
- `BKL-010` retains only the operator-produced content-addressed image/digest evidence needed for publication; sealing and attestation mechanics are implemented.
- No publication claim may be made from the synthetic executor or a development visual runtime.
