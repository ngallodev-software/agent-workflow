# Provider evidence and usage normalization research

**Status:** implemented in release 0.2.0; hardened in 0.2.1
**Research date:** 2026-07-24
**Scope:** Codex/OpenAI-style JSONL, Claude Code stream JSON, immutable run evidence, and comparison-safe token/cost accounting.

## Decision summary

`agent-workflow` treats the bounded raw executor event stream as evidence and the normalized usage object as a derived projection. Each classified usage update carries an explicit mode: `delta`, `cumulative`, or `terminal`. A terminal update is authoritative for the run and is never added to earlier deltas. Mixed nonterminal modes invalidate usage. Replayed records with an explicit provider event identity are idempotent. Identical unidentified terminal/cumulative snapshots may be ignored safely, but an identical unidentified `delta` is ambiguous and makes usage incomplete rather than silently undercounting it. Missing or unproven values remain `null`.

The implementation is in `src/agent_workflow/provider_evidence.py`; contracts are `schemas/provider-evidence.schema.json` and `schemas/trial-evidence.schema.json`; comparison semantics are in `src/agent_workflow/eval/{trials,compare}.py`.

## Primary sources reviewed

| Provider surface | Primary source | Verified use |
|---|---|---|
| OpenAI API pricing | https://developers.openai.com/api/docs/pricing | Pricing is model- and date-dependent; runtime estimates require a pinned catalog identity rather than an embedded current price. |
| OpenAI reasoning usage | https://developers.openai.com/api/docs/guides/reasoning | Reasoning-token details may be reported separately from ordinary output tokens. |
| OpenAI prompt caching | https://developers.openai.com/api/docs/guides/prompt-caching | Cached input is a subset/details field and must not be added to input token totals. |
| Codex CLI event examples | https://github.com/openai/codex/issues | Current examples show `turn.completed` usage with input, cached-input, output, and reasoning fields; issue history also demonstrates that CLI fields have changed across releases. |
| Anthropic Messages usage | https://docs.anthropic.com/en/api/messages | Message usage exposes input, cache-creation, cache-read, and output token fields. |
| Anthropic streaming events | https://docs.anthropic.com/en/api/messages-streaming | Streaming has message-start/content-delta/message-delta/message-stop boundaries; intermediate usage is not assumed to be a run total. |
| Anthropic prompt caching | https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching | Cache-read and cache-creation tokens have distinct meanings and billing treatment. |
| Anthropic pricing | https://docs.anthropic.com/en/docs/about-claude/pricing | Provider prices vary by model and cache category; estimates require a pinned price catalog. |
| Claude Code output formats | https://docs.anthropic.com/en/docs/claude-code/cli-reference | `stream-json` is a supported machine-readable CLI surface. |
| Claude Agent SDK result messages | https://docs.anthropic.com/en/api/agent-sdk/python | Final result messages can carry aggregate usage and provider-reported total cost. |

URLs are recorded because these facts are executor-version-sensitive. The raw event stream and executor version in run provenance remain the evidence needed to reinterpret historical runs.

## Event envelope

Every classified update is stored as:

```json
{
  "sequence": 12,
  "event_sha256": "…",
  "event_type": "turn.completed",
  "mode": "terminal",
  "usage": {
    "input_tokens": 1000,
    "cached_input_tokens": 600,
    "cache_write_input_tokens": null,
    "output_tokens": 300,
    "reasoning_output_tokens": 90,
    "provider_total_tokens": 1300,
    "provider_billed_cost": null,
    "local_estimated_cost": null,
    "currency": null,
    "price_catalog_id": null
  }
}
```

### Mode semantics

- `delta`: values apply only to that event and may be summed with other delta events from the same run.
- `cumulative`: the last valid cumulative update supersedes prior cumulative updates only when numeric counters are nondecreasing and cost metadata is consistent.
- `terminal`: one terminal usage vector is authoritative. Replayed equivalent terminal records are harmless; conflicting terminal vectors invalidate usage. Earlier delta/cumulative records remain provenance but do not fill missing terminal fields.
- mixed `delta` and `cumulative` without a terminal record: invalid, because summing or selecting would require guessing.

## Field mapping

| Normalized field | Known variants |
|---|---|
| `input_tokens` | `input_tokens`, `prompt_tokens` |
| `cached_input_tokens` | `cached_input_tokens`, `cache_read_input_tokens`, `cached_tokens`, `input_tokens_details.cached_tokens`, `prompt_tokens_details.cached_tokens` |
| `cache_write_input_tokens` | `cache_write_input_tokens`, `cache_creation_input_tokens` |
| `output_tokens` | `output_tokens`, `completion_tokens` |
| `reasoning_output_tokens` | `reasoning_output_tokens`, `reasoning_tokens`, `output_tokens_details.reasoning_tokens` |
| `provider_total_tokens` | `total_tokens`, `provider_total_tokens` |
| `provider_billed_cost` | explicit provider field such as Claude Code `total_cost_usd`; legacy `cost` only when `cost_source=provider` |
| `local_estimated_cost` | explicit estimate field; legacy `cost` only when `cost_source=local_estimate` |

Cached input is not a new token category to add to input. It is a billed/details subset of input. Reasoning output is likewise retained as a detail and is not added again when the provider already includes it in output or total tokens.

## Double-counting hazards and controls

1. **Terminal plus deltas:** terminal wins; deltas are not summed into it.
2. **Cached input:** cached tokens are never added to `input_tokens`.
3. **Reasoning output:** reasoning details are never added to provider output or total fields.
4. **Duplicate records:** explicit provider event IDs establish replay identity. Without an ID, equivalent terminal/cumulative snapshots may be deduplicated, while duplicate delta lines are flagged as ambiguous and make the run comparison-ineligible.
5. **Retries:** each run has its own evidence and `retry_of_run_id`; cohort aggregation must decide whether retries are separate trials or exclusions rather than merging them silently.
6. **Provider versus estimated cost:** the two fields are never collapsed into one number.
7. **Currency/catalog mismatch:** provider costs are comparable only within one currency; local estimates are comparable only when currency and `price_catalog_id` both match.
8. **Malformed/truncated streams:** usage is incomplete and the trial extractor rejects the run.

## Bounded capture and immutability

- Raw executor events must be regular non-symlink files and remain unchanged during capture. Parsing is capped at 16 MiB per run while the complete file is hashed from the same descriptor.
- The evidence records raw byte count, SHA-256, capture limit, completion flag, malformed count, classified records, and incomplete reasons.
- `provider-evidence.json` is sealed into `final-receipt.json`.
- Trial extraction verifies the complete final seal, rejects incomplete provider evidence, and validates `score-set.json` against content-addressed scorer receipts tied to that final receipt.
- The full raw file is hashed with streaming SHA-256; parsing reads at most the declared cap plus one byte.

## Cost and currency rules

- `provider_billed_cost` remains `null` unless the provider/executor explicitly reports a billed amount.
- A provider-billed cost requires a currency.
- `local_estimated_cost` remains `null` unless a pinned catalog calculation has been performed.
- A local estimate requires both currency and `price_catalog_id`.
- No current prices are embedded in source. This prevents historical evidence from changing when public pricing changes.
- Cross-cohort cost comparison is excluded when currency or catalog identity differs.

## Retry, re-steer, and error accounting

Trial evidence carries:

- `retry_of_run_id` and runtime `retry_count`;
- structured error records from execution metrics;
- steering count and acknowledged-steering count;
- source artifact digests, including prompt, command collection, provider evidence, and raw events.

These fields are evidence, not instructions to combine trials. A benchmark manifest must declare inclusion/exclusion semantics for interrupted, retried, or human-assisted runs.

## Known limits

- Codex and Claude CLI event JSON are operational interfaces rather than repository-pinned JSON Schemas. Executor version and raw evidence are therefore mandatory provenance.
- Claude assistant-message usage is treated as a per-message delta inside the enclosing CLI run. This is an implementation inference documented in code and must be revalidated when the CLI format changes.
- No paid live baseline/candidate cohort was run in this completion pass. That remains `BKL-004` and requires an explicit benchmark policy decision.
- No local price catalog is shipped; local estimated cost remains `null` unless a future catalog implementation supplies a stable identity.

## Acceptance evidence

Focused tests cover terminal authority/conflict/emptiness, delta summation and duplicate ambiguity, cumulative monotonicity, mixed-mode invalidation, cached/reasoning mapping, non-finite values, raw-file type safety, malformed input, size overflow, provider/local cost metadata, forged score-set rejection, incomplete-trial rejection, and comparison exclusions. See `tests/test_provider_evidence.py`, `tests/test_eval_trials.py`, and `tests/test_eval_compare.py`.
