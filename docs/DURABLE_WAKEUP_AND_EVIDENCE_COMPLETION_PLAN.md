# Durable Wakeup and Evidence Completion Plan

## Purpose

Complete the two remaining foundations for observable, restart-safe orchestration:

1. accelerate durable control-record delivery when parent and child share a tmux server, without making tmux authoritative; and
2. turn sealed execution metrics into comparable, provenance-backed token, cost, and timing evidence.

This plan deliberately separates implementation that is deterministic and safe to ship now from provider-specific and real-executor work that needs a controlled cohort.

## Starting point

The existing append-only `messages.jsonl` protocol is authoritative. Records are locked, flushed, and fsynced; replay is restart-safe; steering, progress, and acknowledgement records already exist. `watch` currently obtains responsiveness by replay polling. Sealed execution metrics already contain nullable normalized usage fields, elapsed time, and command-collection files, but the runner preserves only the latest executor usage event and the evaluation CLI cannot yet persist or compare a sealed-trial cohort.

## Non-negotiable contracts

| Contract | Required behavior |
|---|---|
| Durable-first | A message is visible on replay before any wake signal is sent. A failed signal must never change a successful append into an error. |
| Replay authority | A receiver replays before waiting and after every wake. A wake may be lost, stale, duplicated, or unavailable without losing a record. |
| Bounded waiting | A `tmux wait-for` client is bounded by the caller deadline. Timeout, absent tmux, absent server, or nonzero exit returns to ordinary bounded replay polling. |
| No terminal injection | Mid-task executor steering remains adapter work. This plan does not use `send-keys` or infer state from terminal text. |
| Usage semantics | Accumulate only explicitly labeled provider deltas. A later cumulative/terminal total replaces the corresponding accumulated dimension; do not guess and double-count. |
| Unknown is null | Missing child usage, provider cost, or stage duration stays `null`, never zero or derived from prose. |
| Sealed inputs | Benchmark trials are extracted only from sealed receipts and written to explicit baseline/candidate evidence files. Comparison never mutates a sealed run or auto-selects a baseline. |

## Model routing and work split

Use Lina for the wakeup implementation and GPT-5.4-mini for evidence implementation, with mini agents only for read-only research and independent checks. In this environment those requested model labels are not exposed; use the smallest available worker for the equivalent bounded task and preserve the same ownership boundaries.

| Phase | Primary owner | Independent verifier | Scope |
|---|---|---|---|
| A | Lina-equivalent implementation agent | mini research/verifier | tmux wakeup accelerator |
| B | GPT-5.4-mini-equivalent implementation agent | mini verifier | usage accumulation and stage timing |
| C | GPT-5.4-mini-equivalent implementation agent | mini verifier | immutable trial evidence and CLI comparison |
| D | operator plus mini analyst | phase gate reviewer | real-executor cohort and baseline decision |

## Phase A — Durable Control Record wakeup accelerator

### A1. Add a narrow tmux wake adapter

Change `src/agent_workflow/tmux.py` only to add a deterministic channel function plus best-effort signal/wait functions. The channel must be a versioned SHA-256 digest of `run_dir.resolve()` (for example `agent-workflow/v1/<digest>`), not a raw session identifier. `signal_waiters(channel)` invokes `tmux wait-for -S CHANNEL` and suppresses unavailable tmux/server/nonzero failures. `wait_for_wakeup(channel, timeout_seconds)` runs `tmux wait-for CHANNEL`, enforces its own timeout, reaps the child process, returns `False` for unavailable/error/timeout, and preserves `KeyboardInterrupt` after cleanup.

`tmux wait-for` is a hint only. Do not depend on retained signals or on a tmux socket being available in tests.

### A2. Notify only after the durable commit

Add an injectable `after_commit` hook to `append_message` in `src/agent_workflow/messages.py`. Invoke it after append, flush, fsync, close, and lock release. Suppress callback errors so the successful returned record remains successful. In `src/agent_workflow/sessions.py`, route `steer`, `progress`, and `acknowledge` through one helper that appends and then calls the tmux signal function for that run directory.

Direct callers of `append_message` remain durable without automatically waking; document that boundary in code/tests.

### A3. Make waiting replay-first and bounded

Extend `wait_for_messages` with injectable wake/channel seams rather than coupling `messages.py` directly to tmux. Preserve existing polling as the default. `wait_for_message` supplies the run’s channel and wait function. Each loop must replay first, return contiguous records if present, calculate a monotonic remaining deadline, wait for at most `min(poll_seconds, remaining)`, and replay again. If wake fails or is unavailable, sleep only when the waiter did not consume the time slice.

This intentionally tolerates a record arriving between replay and wait registration: the next bounded replay finds it even if the signal was lost.

### A4. Acceptance tests

- Failed notifier does not fail or corrupt a durable append; it runs only after the record is observable.
- Existing replay returns immediately without invoking wake.
- Signal then append, stale/spurious signals, and a dropped-signal replay/wait race all return only durable records and preserve ordering.
- `timeout=0`, finite timeout, unavailable tmux, waiter error, and cancellation are bounded and clean up the process.
- Channels are deterministic per resolved run directory and differ across directories.
- Session steer/progress/ack wrappers signal the matching run; README accurately calls `watch` durable replay with a best-effort tmux wakeup.

### A5. Visible child panes when launched from tmux

When the launcher process has a valid `TMUX` environment and can resolve its current tmux session/window, create the child with `split-window` in that exact window rather than a detached fresh session. Record the resulting pane target/ID in the same durable launch metadata already used for tmux identification. Do not parse untrusted shell output, infer a target from a pane title, or attach elsewhere. If the environment is absent, stale, or unresolvable, retain the present detached named-session path; do not silently launch a pane into an arbitrary server/window.

Tests must mock current-client discovery and assert the exact target is used, pane metadata is persisted, and every unavailable/stale-environment path falls back to the existing named-session behavior. This is a local operator-visibility feature, not a cross-host transport or a steering mechanism.

## Phase B — Provider-neutral token, cost, and timing evidence

### B1. Create an explicit usage accumulator

Add a small pure helper near `event_usage`/metrics that consumes normalized provider events with one declared mode: `delta`, `cumulative`, or `terminal`. It should carry input, cached-input, output, total, cost, and currency independently. Sum explicitly-delta numeric fields; a cumulative/terminal value is authoritative for that field and replaces an earlier accumulated value. Reject booleans, negatives, and malformed numbers. Never infer a mode from field shape.

Wire the runner to retain the final accumulated snapshot in provenance and in budget checks rather than retaining only the last structured event. Keep legacy events compatible by treating a plain final usage object as one terminal snapshot when it is emitted at terminal completion; document the boundary and test it.

### B2. Normalize common cached-token layouts

Extend `normalize_usage` to support known aliases without manufacturing data: `cached_input_tokens`, `cache_read_input_tokens`, top-level `cached_tokens`, and OpenAI-style `prompt_tokens_details.cached_tokens`. Preserve `null` for unknown values. Preserve provider reported total/cost/currency only when valid.

### B3. Populate verifier command timing

Read the sealed `collections/commands-post.json` content when constructing execution metrics. Report a verification-stage duration derived from valid command durations. Keep overall elapsed time as run wall time, never the sum of stages. Verifier usage/cost and child-stage usage/time remain null unless a future sealed receipt explicitly supplies them.

### B4. Acceptance tests

- delta input/output aggregation, then a terminal cumulative replacement, cannot double-count;
- nested cached-token aliases normalize correctly and malformed/bool/negative values remain null;
- partial usage stays partial rather than becoming zero;
- command post-collection produces verification duration, while total remains run wall time;
- absent child receipt leaves child fields null;
- legacy final event behavior and existing metric-schema validation stay compatible.

## Phase C — Immutable benchmark evidence and comparison

### C1. Define a sealed-trial extractor

Add `src/agent_workflow/eval/trials.py` (or a similarly focused module) that validates a completed run’s final receipt, provenance, execution metrics, and score verdict and produces one explicit trial record. Include run ID/path, schema/version, receipt digest, verdict, total wall duration, input/output/cached/total tokens, cost/currency, retry/error/steer summaries, and source file digests/paths. Derive `tokens` only if both input and output are known; derive cost/duration only when reported. No hidden filesystem scan or baseline choice.

### C2. Add explicit evidence collection and compare CLI

Add commands under `agent-workflow eval` to write a supplied set of run directories to a supplied JSON evidence file and compare two supplied evidence files using the existing comparator. Suggested shape:

```text
agent-workflow eval collect --output baseline.json RUN_DIR [...]
agent-workflow eval compare baseline.json candidate.json --output comparison.json
```

The command must reject unsealed/incomplete inputs, duplicate trial IDs, incompatible currency aggregation, and malformed evidence. It must write atomically, include its own schema/version and collection timestamp, and print an inspectable result path. It must not change any run directory.

### C3. Acceptance tests

- extractor rejects placeholder/missing final receipts and accepts known-good sealed fixtures;
- output evidence is deterministic except for documented collection timestamp;
- comparator produces pass/fail/regression deltas for duration, token, and cost from explicit files;
- unknown numeric values remain unknown, not coerced to zero;
- invalid/cross-currency comparisons fail with a useful message;
- existing eval commands and schemas remain valid.

## Phase D — Controlled real-executor cohort (operator gate)

This phase is not a unit-test substitute. After Phases A-C merge, run 3–5 approved real sessions for the deterministic fixture under one pinned executor/version/configuration. Retain each sealed trial evidence record, inspect failures/resteers, and consciously designate exactly one baseline file. Run `eval compare` against a second cohort. Do not make release assertions from a cohort with changed prompt, model revision, tool policy, browser image, or pricing/currency semantics.

For the visual fixture, remain blocked until a pinned browser image digest, installed-font manifest, browser-artifact bridge, and explicit child lifecycle telemetry contract exist. Then run DOM/keyboard/ARIA assertions plus screenshot comparison with declared tolerance.

## Integration sequence

1. Merge/review Phase A independently; run focused message/tmux/session tests.
2. Merge/review Phase B; run focused executor/metrics/runner tests.
3. Merge/review Phase C; run eval tests and CLI help/smoke commands.
4. Run `PYTHONPATH=src pytest -q`, `python -m build --wheel`, schema/doctor checks, and `scripts/release-check.sh`.
5. Bump version only after all code and docs land as one releaseable change; build/install the wheel; run a smoke session and verify `final-receipt.json` plus evidence collection.
6. Commit and push only after the phase gate accepts the combined diff.

## Explicit out of scope

- A daemon, Redis/NATS, or generic message bus. The durable JSONL control log remains the bus for this scope.
- A fake synchronous “steer” capability for one-shot executor stdin.
- Provider pricing inference or estimated costs.
- A screenshot visual eval without the pinned environment prerequisites.

## ChatGPT research handoff prompt

Use this only for the remaining external/prior-art deep dive; do not ask it to edit the repository blindly:

```text
You are researching design options for the Python project agent-workflow. Do not write code. Produce a cited technical decision memo focused on two topics:

1) Durable orchestration control delivery: append-only fsynced JSONL records are authoritative; tmux wait-for may be used only as a best-effort local wakeup accelerator. Compare tmux wait-for, filesystem notifications (inotify/watchfiles), SQLite notification patterns, Redis Streams, NATS JetStream, and a local Unix socket. Analyze delivery guarantees, restart behavior, lost/coalesced wakeups, multi-host implications, security boundaries, operational burden, and a migration path that keeps replayable durable records as source of truth. Recommend a staged architecture for single-host tmux today and optional multi-host tomorrow.

2) Benchmark evidence: evaluate provider-neutral token/cost/time evidence for OpenAI/Codex-like streaming events and other common agent executors. Specify an explicit delta/cumulative/terminal usage event envelope; map known cached-token field variants; identify pitfalls that cause double-counting; and propose an immutable JSON trial-evidence schema plus baseline/candidate cohort comparison semantics. Include what must stay null, currency rules, retry/re-steer/error accounting, provenance digests, and a real-executor cohort protocol.

Requirements: cite primary sources only; distinguish facts from recommendations; include concrete JSON examples and a compact decision matrix; do not recommend terminal keystroke injection as a steering API; no implementation patches. Finish with prioritized actionable recommendations, open questions, and tests/evals that would falsify each recommendation.
```
