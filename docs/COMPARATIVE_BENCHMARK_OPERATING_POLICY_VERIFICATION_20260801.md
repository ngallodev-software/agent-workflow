# Comparative benchmark operating-policy verification — 2026-08-01

## Scope

This record verifies the `agent-workflow` 0.7.6 completion of DEC-002 and the locally implementable portions of BKL-004 and BKL-010. It covers subscription-first real-executor authentication, optional explicit API authentication, operating-policy enforcement, retry and interruption semantics, paired cohort statistics, truthful cost accounting, publication visual-runtime contracts, packaged-suite parity, and the installed-wheel benchmark journey.

The adopted paired experiment remains unchanged: the same canonical `priority-picker-v1` task is executed through `control_raw/v1` and `workflow_full/v1` in isolated worktrees, with a 70% machine / 30% blinded-human composite.

## Authentication verification

The implementation treats an authenticated provider CLI session as the default real-executor path:

- `codex-subscription.json` checks `codex login status` and executes through the existing Codex login session;
- `claude-subscription.json` checks `claude auth status` and executes through the existing Claude account session;
- API-key and access-token profiles are separate, explicit opt-in adapters;
- subscription mode rejects ambient provider credential variables instead of silently falling back to API billing;
- authentication evidence records the mode, provider, command identity, status, and a digest of status output without persisting credentials or raw login output.

No Codex or Claude executable and no authenticated subscription session were available in the validation environment. Consequently, this verification does not claim that a real provider cohort was executed. The readiness and execution mechanisms are implemented; the first external cohort remains an operator-run acceptance event under BKL-004.

## Operating-policy verification

Three versioned policies are packaged with the suite:

| Profile | Repetitions | Intended claim | Winner declaration |
|---|---:|---|---|
| `development` | 1 | Local/synthetic development evidence | Disabled |
| `internal` | 10 | Controlled internal comparison | Enabled after minimum complete pairs |
| `publication` | 20 | Publication candidate | Enabled only after all publication gates |

The policies seal:

- allowed and default authentication modes;
- unassisted versus separately named assisted cohorts;
- provider-managed cache recording and prohibition on mixed cache treatment;
- one infrastructure-only retry using a fresh paired worktree attempt;
- retention of every attempt and explicit selection of the terminal attempt;
- discard-and-fresh-pair treatment for interrupted comparisons;
- reviewer minimums and visual-runtime requirements;
- deterministic SHA-seeded paired-bootstrap confidence intervals;
- a 95% confidence level, five-point minimum composite effect, and three-point maximum machine or human regression;
- prohibition on command-line repetition or assistance overrides for internal/publication claims.

Development overrides remain possible and are retained in run evidence. Internal and publication policy changes require a new versioned policy file so reported claims cannot silently drift.

## Cost and timing verification

The evidence contracts and reports keep these values distinct:

- provider-billed cost;
- API-equivalent catalog estimate;
- optional, separately labeled subscription allocation;
- input, cached-input, cache-write, output, and reasoning tokens;
- phase wall time, active process time, provider elapsed time, first-output latency, queue time, visual capture time, verification time, pair critical path, and complete pipeline wall time.

Subscription execution intentionally leaves per-run provider-billed cost unavailable unless the provider supplies such evidence. It does not report subscription usage as zero-cost. Synthetic execution retains deterministic synthetic billing fields solely for fixture validation.

## Publication visual-runtime verification

The suite now contains:

- a publication browser-container definition;
- development runtime attestation for Playwright, browser, fonts, and container identity;
- a runtime-lock schema and example publication lock;
- sealing that requires a content-addressed image reference, browser digest, and font digests;
- publication readiness checks that reject mutable tags, missing hashes, or development-only runtime evidence.

This environment produced development runtime evidence using Playwright 1.57.0 and Chromium 144.0.7559.96. It did not build and publish a trusted registry image or independently verify an immutable registry digest. BKL-010 therefore remains an external acceptance gate rather than a missing implementation.

## Source validation

The dependency-independent repository selection completed successfully:

```text
151 passed, 12 xfailed in 126.91s
```

The expected failures are approved future contracts. They include the intentionally unaccepted real-provider cohort claim and unrelated future orchestration, MCP, supervisor, privacy, and analytical-export work.

Additional checks passed:

```text
agent-workflow 0.7.6
benchmark schemas: valid
executor and policy JSON: valid
release assets: valid
```

The unrestricted test suite cannot collect MCP-dependent journeys in this environment because the repository-pinned `mcp==1.28.1` distribution is unavailable from the configured package index. The failure occurs at fixture setup, not in the comparative benchmark implementation.

## Installed-wheel verification

A built wheel was installed into an isolated virtual environment. From the installed product, the following public journey completed successfully:

```text
benchmark suite-export
benchmark readiness
benchmark fixture-create
benchmark plan
benchmark run
benchmark verify
```

The installed run:

- exported all policies, authentication profiles, schemas, fixture files, and visual-runtime assets;
- created the coordinator and paired arm worktrees;
- ran all three synthetic phases through synchronized paired execution;
- captured visual evidence and deterministic machine scores;
- consolidated and digest-verified evidence;
- stopped truthfully in `awaiting_human_review`.

The synthetic reference scores remained 88 for `control_raw` and 96 for `workflow_full`. These scores validate fixture determinism; they are not real-provider performance claims.

## Completion boundary

The remaining backlog entries are acceptance events, not unimplemented benchmark machinery:

- **BKL-004:** run and independently accept a controlled subscription-backed provider cohort after its security, privacy, and release prerequisites are accepted.
- **BKL-010:** build/publish the browser image and independently verify its immutable content digest and font manifest before a publication-grade visual claim.

DEC-002 is decided and enforced in code. API credentials remain optional, explicit adapters; subscriptions are the default real-executor authentication mechanism.
