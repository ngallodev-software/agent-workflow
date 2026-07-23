# Durable Orchestration Delivery and Benchmark Evidence for `agent-workflow`

**Status:** Proposed architecture decision
**Scope:** Design research only; no implementation changes
**Date:** July 23, 2026

**Task tracking:** [BACKLOG.md](../BACKLOG.md) is the canonical register for
work derived from this research. Keep this document as the detailed evidence
and design reference; do not maintain a second task list here.

## Executive decision

`agent-workflow` should preserve **append-only, fsynced, replayable JSONL control records as the authoritative orchestration state**. Notification mechanisms should carry only an advisory statement equivalent to “new durable records may be available.” They must never carry the sole copy of a steer, acknowledgement, cancellation, or other control instruction.

For the current single-host tmux deployment, use:

1. durable JSONL append and `fsync`;
2. a monotonically advancing durable cursor per consumer;
3. `tmux wait-for` as an optional, best-effort wakeup accelerator;
4. periodic reconciliation polling as the correctness backstop.

Filesystem notifications may later replace or complement tmux wakeups, but should remain advisory because kernel notification queues can overflow and events may be coalesced. For multi-host operation, introduce a broker adapter—preferably NATS JetStream or Redis Streams—without changing the durable control-record contract. The broker should distribute record references or replicated envelopes, while replayable records and idempotent consumer cursors remain the semantic source of truth.

For benchmark evidence, normalize every executor’s telemetry into an immutable event stream that explicitly identifies whether usage is a **delta**, **cumulative snapshot**, or **terminal total**. Never sum a mixture of those modes. Preserve raw provider events and derive normalized trial evidence from them. Token and cost fields that cannot be proven from executor output or a pinned price catalog must remain `null`, not zero.

---

# 1. Durable orchestration control delivery

## 1.1 Required invariant

A control operation is accepted only after its complete JSONL record has been appended and durably synchronized. A wakeup signal may be sent only after that durability point.

Conceptually:

```text
validate record
→ append complete JSON line
→ flush userspace buffers
→ fsync durable file
→ publish advisory wakeup
```

The consumer reacts to any wakeup by replaying records after its durable cursor. If no wakeup arrives, periodic reconciliation eventually discovers the record.

This architecture separates two concerns:

* **Durable truth:** what control records exist and in what order.
* **Scheduling hint:** how quickly an idle process notices that truth changed.

That separation is necessary because none of the local wakeup mechanisms evaluated below independently provides the desired combination of durable replay, crash recovery, ordering, and migration portability.

## 1.2 Facts about candidate mechanisms

### tmux `wait-for`

The tmux manual defines `wait-for name` as blocking until another client executes `wait-for -S name`. It also provides channel locking through `-L` and `-U`. The interface is managed by the running tmux server rather than by a persistent message store.

**Implications:**

* It is suitable for waking processes attached to the same tmux server.
* It provides no independently replayable record.
* A tmux-server restart destroys the live waiting relationship.
* A signal issued before a process begins waiting must not be assumed to become a durable queued notification.
* It is inherently single-host and tied to a specific tmux server socket and security context.

### Filesystem notifications: inotify and watchfiles

Linux inotify reports filesystem changes through a kernel event queue. The Linux manual explicitly states that the queue can overflow and events are then lost; robust applications must recover by rebuilding state. It also documents event coalescing when successive unread events are identical.

`watchfiles` exposes sets of filesystem changes and recursively watches directories, but it remains an abstraction over operating-system notification facilities rather than a durable event log.

**Implications:**

* Notifications can reduce latency without a tmux dependency.
* Multiple appends may produce one observed change notification.
* Queue overflow or watcher restart can lose wakeups.
* Watching a directory is generally safer than assuming an inode remains stable across atomic replacement or log rotation.
* Correctness still requires checking durable file state and cursor position.

### SQLite notification patterns

SQLite’s `sqlite3_update_hook()` is registered on a specific database connection. It has documented exclusions, including changes to internal tables, `WITHOUT ROWID` tables, certain `REPLACE` deletions, and truncate optimization; callback code also cannot modify the invoking connection.

SQLite WAL improves reader/writer concurrency but does not turn SQLite into a cross-process push-notification service. Durable cross-process change discovery generally requires polling a durable table, polling `PRAGMA data_version`, or adding a separate wakeup channel.

**Implications:**

* A transactional inbox table can provide strong durable ordering, uniqueness, acknowledgement, and cursor semantics.
* Connection-local hooks are not a general multi-process notification bus.
* SQLite introduces schema migration, locking, backup, corruption-recovery, and database-lifecycle concerns that are unnecessary if JSONL already satisfies the authoritative-record requirement.
* SQLite is more compelling as a future materialized index than as the immediate wakeup mechanism.

### Redis Streams

Redis Streams retain ordered entries, support replay, consumer groups, pending-entry tracking, acknowledgement, and recovery of entries left pending by failed consumers. Redis documents consumer-group processing as at-least-once and distinguishes Streams from Pub/Sub, whose delivery is at-most-once and loses messages for disconnected subscribers.

**Implications:**

* Redis Streams can distribute work across hosts and recover unacknowledged deliveries.
* Consumers must remain idempotent because redelivery is expected.
* Persistence depends on Redis durability configuration, retention policy, failover design, and operational discipline.
* Trimming a stream before all required durable consumers have advanced can remove replay evidence.
* Redis becomes another stateful service that must be secured, monitored, backed up, and upgraded.

### NATS JetStream

Core NATS provides best-effort, at-most-once delivery. JetStream adds stored streams and consumers that can provide at-least-once delivery. NATS documents stronger “exactly once” behavior as a composition of publication deduplication and double acknowledgements, not as freedom from application-level identity and idempotency design.

JetStream streams define storage and retention limits, while durable consumers retain delivery state.

**Implications:**

* JetStream is well suited to multi-host command distribution and request/reply messaging.
* Durable names, acknowledgement policy, redelivery timing, retention, replicas, and deduplication windows become part of correctness.
* Application-level record IDs remain necessary beyond any bounded broker deduplication window.
* It introduces a networked security boundary and a stateful clustered service.

### Local Unix-domain socket

Unix-domain sockets support local interprocess communication. On Linux, pathname socket access can be constrained by directory and socket permissions, but POSIX does not require all systems to honor pathname-socket permissions consistently; Linux abstract sockets do not use filesystem permissions.

**Implications:**

* A pathname socket can provide low-latency local wakeups and bidirectional status exchange.
* A disconnected process misses any notification that was not separately persisted.
* Stream sockets require connection management, framing, backpressure, and stale-socket cleanup.
* The socket server becomes a local availability dependency.
* It does not naturally extend across hosts without replacing the transport.
* Pathname sockets should live in a private runtime directory with restrictive ownership and mode; abstract sockets should not be treated as permission-protected endpoints.

## 1.3 Compact decision matrix

Ratings describe fitness for the stated `agent-workflow` role, not absolute product quality.

| Mechanism            |                        Durable replay | Restart behavior                         | Wakeup loss/coalescing                             |                            Multi-host | Security boundary                                       | Operational burden | Recommended role                    |
| -------------------- | ------------------------------------: | ---------------------------------------- | -------------------------------------------------- | ------------------------------------: | ------------------------------------------------------- | -----------------: | ----------------------------------- |
| tmux `wait-for`      |                                    No | Lost with tmux server state              | Treat as lossy edge signal                         |                                    No | tmux server/socket and local account                    |           Very low | Immediate local accelerator         |
| inotify/watchfiles   |                                    No | Watch must be recreated                  | Queue overflow and coalescing possible             |                                    No | Filesystem access plus process identity                 |                Low | Generic local accelerator           |
| SQLite inbox/polling |                                   Yes | Durable DB recovery                      | Polling avoids wakeup dependence                   | Shared filesystem only; not ideal WAN | DB-file permissions                                     |             Medium | Optional indexed local store        |
| Redis Streams        | Yes, subject to persistence/retention | Consumer pending state supports recovery | At-least-once; redelivery expected                 |                                   Yes | Network ACL/TLS/account boundary                        |        Medium–high | Optional distributed adapter        |
| NATS JetStream       |  Yes, subject to stream configuration | Durable consumers and stream replay      | At-least-once by default; dedupe/acks configurable |                                   Yes | NATS accounts, credentials, TLS, subject permissions    |        Medium–high | Preferred distributed control plane |
| Unix socket          |                                    No | Listener and clients reconnect           | Disconnected clients miss signals                  |                                    No | Local directory/socket permissions and peer credentials |             Medium | Optional local RPC/wakeup channel   |

## 1.4 Recommended staged architecture

### Stage A — single-host tmux

**Recommendation**

Keep one append-only control journal per orchestration scope, or one global journal with an explicit orchestration ID. Each record has a globally unique record ID and a monotonically ordered sequence assigned under an exclusive append lock.

After `fsync`, the producer may execute a tmux signal such as:

```text
tmux wait-for -S agent-workflow:<orchestration-id>:changed
```

The consumer:

1. reads from its last durably committed sequence;
2. validates complete lines and record identities;
3. handles every applicable record idempotently;
4. durably advances its cursor;
5. begins waiting again;
6. also wakes on a bounded reconciliation interval.

The tmux channel name must not be treated as a message queue or contain the command payload.

**Why**

This adds minimal operational complexity while preserving correctness if:

* tmux is unavailable;
* the signal arrives before the waiter;
* the tmux server restarts;
* several appends collapse into one observed signal;
* the producer crashes after `fsync` but before signaling.

### Stage B — transport-neutral notifier interface

Define an internal conceptual interface with only advisory semantics:

```text
notify(scope_id, highest_durable_sequence)
wait(scope_id, timeout) → advisory_high_watermark | timeout
```

The returned high-water mark is a hint. The consumer still reads the authoritative log and never assumes all lower records were processed merely because it observed a larger wakeup value.

Provide tmux and filesystem-watcher adapters. Keep periodic reconciliation enabled for both.

### Stage C — durable record indexing

Add a materialized index only when JSONL scan cost becomes measurable. SQLite is a reasonable single-host index for:

* record ID uniqueness;
* per-consumer cursors;
* acknowledgement relationships;
* searchable status projections.

The JSONL journal should remain independently replayable. The SQLite database should be reconstructable from the journal, or journal and database should be updated through a carefully specified transaction/outbox protocol. Avoid declaring two independently writable stores authoritative.

### Stage D — optional multi-host broker

Introduce a broker adapter without changing the durable record envelope.

Two defensible patterns are:

**Reference distribution**

```json
{
  "kind": "control-record-available",
  "scope_id": "run-2026-07-23-001",
  "record_id": "01JZ...",
  "sequence": 184,
  "journal_uri": "artifact://runs/run-2026-07-23-001/control.jsonl",
  "record_sha256": "..."
}
```

The consumer retrieves and validates the durable record from shared artifact storage.

**Envelope replication**

Publish the complete canonical record to JetStream or Redis Streams, while archiving the same canonical bytes in immutable trial/run evidence. Broker sequence numbers are transport metadata, not business record identity.

Prefer NATS JetStream when the project needs subject-based routing, service communication, and multi-tenant authorization. Prefer Redis Streams when Redis is already an accepted operational dependency and stream/consumer-group semantics are sufficient. Do not introduce either solely to improve same-host wakeup latency.

## 1.5 Control-record envelope

Recommended durable record:

```json
{
  "schema": "agent-workflow.control-record.v1",
  "record_id": "01JZ7FJCNMDDTHTM55ABAPQ4KB",
  "scope_id": "run-2026-07-23-001",
  "sequence": 184,
  "occurred_at": "2026-07-23T21:18:42.413927Z",
  "kind": "steer",
  "direction": "orchestrator-to-agent",
  "producer": {
    "actor_id": "orchestrator",
    "host_id": "sha256:...",
    "process_instance_id": "01JZ..."
  },
  "target": {
    "actor_id": "agent-review-02"
  },
  "correlation_id": null,
  "payload": {
    "instruction": "Re-run the failing fixture with the pinned environment.",
    "reason": "candidate result lacks required evidence"
  },
  "payload_sha256": "sha256:...",
  "previous_record_sha256": "sha256:...",
  "record_sha256": "sha256:..."
}
```

Hash chaining is recommended for tamper evidence, not as a substitute for filesystem permissions, signatures, or immutable storage.

## 1.6 Explicit non-decision: terminal keystrokes

Terminal keystroke injection should not be an orchestration steering API.

It lacks a stable machine contract, can be interpreted differently depending on terminal state and foreground application, does not inherently prove durable acceptance, is difficult to authenticate at the command level, and is not portable to nonterminal executors.

A terminal may remain a human observation and emergency-intervention surface. Machine steering should use durable control records consumed by an executor integration.

---

# 2. Provider-neutral benchmark evidence

## 2.1 Evidence principles

A benchmark trial should preserve three layers:

1. **Raw evidence:** exact executor events or bounded canonical captures.
2. **Normalized events:** provider-neutral usage and lifecycle envelopes.
3. **Derived summary:** trial totals and cohort statistics.

The normalized and derived layers must identify the raw evidence digests from which they were produced. Raw evidence must not be overwritten after trial sealing.

OpenAI’s Agents SDK tracks aggregate request count, input tokens, output tokens, total tokens, cached-input details, reasoning-output details, and per-request usage entries; it also aggregates across model calls, tool calls, and handoffs.

Anthropic exposes input, output, cache-creation, and cache-read token fields. Anthropic explicitly states that total request input is the sum of ordinary input, cache-creation input, and cache-read input.

Gemini billing can depend on input, output, cached-token count, and cache-storage duration, so a generic “input plus output” model is insufficient for all executors.

## 2.2 Usage event envelope

Every normalized usage event should state its accounting mode.

```json
{
  "schema": "agent-workflow.usage-event.v1",
  "event_id": "01JZ7G6AJXVPWQG2K9T7C6Q9AC",
  "trial_id": "trial-0042",
  "attempt_id": "attempt-0003",
  "request_id": "req-provider-or-local-id",
  "executor": {
    "family": "codex-cli",
    "version": "0.137.0-alpha.4",
    "provider": "openai",
    "model": "gpt-5.6-sol"
  },
  "observed_at": "2026-07-23T21:24:07.902183Z",
  "event_role": "usage",
  "usage_mode": "delta",
  "terminal": false,
  "usage": {
    "input_tokens": 320,
    "cached_input_tokens": 2048,
    "cache_write_input_tokens": null,
    "output_tokens": 77,
    "reasoning_output_tokens": 41,
    "total_tokens": null
  },
  "cost": {
    "amount": null,
    "currency": null,
    "basis": null,
    "pricing_catalog_sha256": null
  },
  "source": {
    "source_type": "executor-jsonl",
    "source_event_type": "token_count",
    "source_sequence": 981,
    "raw_event_sha256": "sha256:..."
  }
}
```

Allowed `usage_mode` values:

* `delta`: usage newly incurred since the previous usage event for the same request or attempt;
* `cumulative`: running total through this event;
* `terminal`: authoritative final total for the identified request or attempt.

`terminal` is a lifecycle property. A terminal event may itself use `delta`, `cumulative`, or `terminal` accounting semantics. To reduce ambiguity, providers that emit a final total should use `usage_mode: "terminal"` and `terminal: true`.

### Cumulative example

```json
{
  "schema": "agent-workflow.usage-event.v1",
  "event_id": "01JZ7G7KXKGP0RG1P8PV5Z6J6A",
  "trial_id": "trial-0042",
  "attempt_id": "attempt-0003",
  "request_id": "req-17",
  "observed_at": "2026-07-23T21:24:09.114082Z",
  "event_role": "usage",
  "usage_mode": "cumulative",
  "terminal": false,
  "usage": {
    "input_tokens": 16000,
    "cached_input_tokens": 12000,
    "cache_write_input_tokens": null,
    "output_tokens": 640,
    "reasoning_output_tokens": 201,
    "total_tokens": 16640
  },
  "source": {
    "source_type": "executor-jsonl",
    "source_event_type": "token_count",
    "source_sequence": 982,
    "raw_event_sha256": "sha256:..."
  }
}
```

### Terminal example

```json
{
  "schema": "agent-workflow.usage-event.v1",
  "event_id": "01JZ7G9BDTET1RZBQH5Q4WKGBW",
  "trial_id": "trial-0042",
  "attempt_id": "attempt-0003",
  "request_id": "req-17",
  "observed_at": "2026-07-23T21:24:17.887310Z",
  "event_role": "usage",
  "usage_mode": "terminal",
  "terminal": true,
  "usage": {
    "input_tokens": 18944,
    "cached_input_tokens": 14336,
    "cache_write_input_tokens": null,
    "output_tokens": 982,
    "reasoning_output_tokens": 326,
    "total_tokens": 19926
  },
  "finish": {
    "status": "completed",
    "reason": "end_turn"
  },
  "source": {
    "source_type": "executor-jsonl",
    "source_event_type": "turn.completed",
    "source_sequence": 990,
    "raw_event_sha256": "sha256:..."
  }
}
```

## 2.3 Cached-token field mapping

| Provider/executor field                               | Normalized field                           | Treatment                                                                                    |
| ----------------------------------------------------- | ------------------------------------------ | -------------------------------------------------------------------------------------------- |
| OpenAI `input_tokens_details.cached_tokens`           | `cached_input_tokens`                      | Cache-read subset of input                                                                   |
| Codex `cached_input_tokens`                           | `cached_input_tokens`                      | Preserve as reported                                                                         |
| Codex rollout `total_token_usage.cached_input_tokens` | `cached_input_tokens`                      | Usually cumulative when under `total_token_usage`                                            |
| Codex rollout `last_token_usage.cached_input_tokens`  | `cached_input_tokens`                      | Potential delta, but verify total advancement before accepting                               |
| OpenAI `cache_write_tokens`, when exposed             | `cache_write_input_tokens`                 | Preserve separately; do not merge with cache reads                                           |
| Anthropic `cache_read_input_tokens`                   | `cached_input_tokens`                      | Cache-read input                                                                             |
| Anthropic `cache_creation_input_tokens`               | `cache_write_input_tokens`                 | Cache-created/written input                                                                  |
| Anthropic `input_tokens`                              | `uncached_input_tokens`, if schema adds it | Do not assume it already includes cached fields                                              |
| Gemini `cachedContentTokenCount`                      | `cached_input_tokens`                      | Cache-related input usage                                                                    |
| Gemini `promptTokenCount`                             | provider-total input                       | Determine from API semantics whether cached count is a subset before deriving uncached input |
| Gemini cache storage duration                         | separate cost dimension                    | Never encode as tokens                                                                       |

OpenAI’s Agents SDK uses `input_tokens_details.cached_tokens` and `output_tokens_details.reasoning_tokens`.

Codex public issue records show that `turn.completed.usage` has used `cached_input_tokens`, while rollout records have exposed both `total_token_usage` and `last_token_usage`. They also document a concrete double-counting hazard: rate-limit-only updates may repeat unchanged `last_token_usage` even when cumulative totals do not advance.

Anthropic’s `input_tokens` is not equivalent to total context input when caching is active; total input is `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`.

## 2.4 Double-counting pitfalls

### Mixing cumulative and delta events

Never add every observed token event. For each request or attempt, use one of:

* sum verified deltas;
* take the latest valid cumulative snapshot;
* take the authoritative terminal total.

If a terminal total exists, use it as the trial accounting authority and use earlier deltas only for temporal analysis.

### Repeated cumulative snapshots

A stream may emit the same cumulative value multiple times. Deduplicate by request identity, usage vector, source sequence, and raw digest. Repeated snapshots contribute zero incremental usage.

### Repeated “last usage” records

A field named `last_token_usage` is not sufficient proof of a new delta. Accept it only if:

* the corresponding cumulative total advanced by exactly that amount; or
* the executor specification explicitly guarantees one-time delta emission and the event identity is new.

Codex has had a reported behavior where rate-limit updates re-emitted prior `last_token_usage`, causing consumers that summed those fields to overcount.

### Nested aggregates

Do not add parent-run totals to child-request totals. OpenAI’s Agents SDK aggregate already includes calls made through tools and handoffs.

Store hierarchy:

```text
trial
  attempt
    executor process
      model request
```

Aggregate only from the lowest complete nonoverlapping level, or use one authoritative parent total.

### Cached tokens as both subset and additive category

Provider semantics differ:

* OpenAI-style cached input is generally represented as detail within input tokens.
* Anthropic’s ordinary input, cache creation, and cache read are separate additive fields.
* Gemini fields require API-version-specific interpretation.

Therefore, never calculate:

```text
total input = input_tokens + cached_input_tokens
```

without a provider mapping that declares whether cached tokens are already included.

### Reasoning tokens

Reasoning tokens may be a subset of output tokens rather than additional tokens. Store both but do not add reasoning tokens to output unless the provider explicitly defines them as disjoint. Codex JSON output has historically omitted reasoning detail even when it existed in rollout records, demonstrating why absent detail must remain `null`.

### Retries and reconnects

A transport reconnect may replay the terminal event for the same request. Deduplicate by provider request ID and event identity.

A true provider retry is a new request and its usage counts, even when it was automatically initiated and returned no useful answer.

## 2.5 Immutable trial-evidence schema

```json
{
  "schema": "agent-workflow.trial-evidence.v1",
  "trial_id": "trial-0042",
  "cohort_id": "candidate",
  "benchmark_case_id": "case-repo-review-017",
  "replicate": 3,
  "sealed_at": "2026-07-23T21:25:02.117912Z",
  "subject": {
    "implementation_digest": "sha256:...",
    "prompt_pack_digest": "sha256:...",
    "configuration_digest": "sha256:..."
  },
  "environment": {
    "os": "linux",
    "architecture": "x86_64",
    "host_class": "benchmark-standard-8",
    "container_image_digest": "sha256:...",
    "executor_family": "codex-cli",
    "executor_version": "0.137.0-alpha.4",
    "provider": "openai",
    "model": "gpt-5.6-sol",
    "model_revision": null
  },
  "timing": {
    "scheduled_at": "2026-07-23T21:18:00Z",
    "process_started_at": "2026-07-23T21:18:01.104Z",
    "first_output_at": "2026-07-23T21:18:03.890Z",
    "terminal_at": "2026-07-23T21:24:17.887Z",
    "wall_duration_ms": 376783,
    "first_output_latency_ms": 2786,
    "active_executor_ms": null
  },
  "usage": {
    "requests": 7,
    "input_tokens": 82144,
    "cached_input_tokens": 59136,
    "cache_write_input_tokens": null,
    "output_tokens": 6132,
    "reasoning_output_tokens": 1820,
    "total_tokens": 88276,
    "normalization_status": "complete-terminal",
    "accounting_source": "request-terminal-events"
  },
  "cost": {
    "amount": null,
    "currency": null,
    "pricing_catalog_sha256": null,
    "calculation_status": "not-computable"
  },
  "control": {
    "steer_count": 2,
    "acknowledged_steer_count": 2,
    "rejected_steer_count": 0,
    "retry_count": 1,
    "executor_restart_count": 0
  },
  "outcome": {
    "status": "completed",
    "score": 0.86,
    "score_schema": "agent-workflow.eval-score.v2",
    "error_class": null
  },
  "provenance": {
    "raw_event_manifest_sha256": "sha256:...",
    "normalized_usage_jsonl_sha256": "sha256:...",
    "control_jsonl_sha256": "sha256:...",
    "stdout_sha256": "sha256:...",
    "stderr_sha256": "sha256:...",
    "result_artifact_manifest_sha256": "sha256:...",
    "pricing_snapshot_sha256": null,
    "normalizer_version": "usage-normalizer-v1",
    "normalizer_digest": "sha256:..."
  }
}
```

After sealing:

* fields are not edited in place;
* corrections create a superseding evidence object;
* the superseding object identifies the prior digest and correction reason;
* cohort analyses identify the exact evidence-object digests included.

## 2.6 Fields that must remain `null`

Use `null`, not zero, when:

* the executor reports no token information;
* a streaming run terminates before authoritative usage is emitted;
* cached-token semantics cannot be mapped confidently;
* reasoning tokens are not exposed;
* cache-write usage is unavailable;
* model revision is not provided;
* active compute time cannot be distinguished from wall time;
* provider billing is subscription-, quota-, or credit-based and no per-trial cost is attributable;
* the pricing catalog is not pinned;
* a price tier depends on undisclosed provider-side context;
* taxes, discounts, committed-use pricing, batch discounts, regional premiums, or negotiated rates are unknown;
* the terminal event was missing and deltas are incomplete.

Zero means “observed and equal to zero.” Null means “unknown or not applicable.”

## 2.7 Currency and cost rules

Provider pricing is time-variable and may distinguish ordinary input, cached input, output, cache storage, service tier, batch mode, context length, or modality. Official OpenAI, Anthropic, and Gemini pricing pages expose differing categories and rates.

Recommendations:

1. Store provider-reported billed cost when available, separately from locally estimated cost.
2. Store currency as ISO 4217 uppercase, normally `USD`.
3. Do not convert currencies inside immutable trial evidence.
4. Store the original amount and currency; perform FX conversion only in a derived report with a separately pinned FX source and date.
5. Calculate cost only from a captured pricing catalog containing:

   * provider;
   * exact model identifier;
   * effective timestamp;
   * service tier;
   * token category;
   * unit size;
   * currency;
   * context-length thresholds;
   * batch or priority modifiers;
   * source digest.
6. Round only for display. Preserve calculation precision in decimal form.
7. If any priced category is unknown, total estimated cost remains `null`; a partial-cost field may be reported explicitly as partial.

## 2.8 Retry, re-steer, and error accounting

### Retry

Every provider request attempt receives a distinct `request_id` or local surrogate. All billable usage from failed and successful attempts counts toward resource evidence.

Trial fields should distinguish:

```json
{
  "attempt_count": 3,
  "successful_attempt_count": 1,
  "failed_attempt_count": 2,
  "retry_count": 2
}
```

Do not report only the successful attempt’s cost.

### Re-steer

A re-steer is a control event, not automatically a new benchmark trial. It remains within the same trial when it is part of the predetermined protocol.

Record:

* durable steer record ID;
* target;
* reason category;
* timestamp;
* acknowledgement record ID;
* first model request causally following the steer;
* whether the protocol allowed that steer.

Unplanned human steering invalidates a fully autonomous cohort comparison unless both cohorts receive an equivalent, preregistered intervention protocol.

### Error

An errored request may still have billable tokens. Preserve usage independently from outcome.

Recommended status vocabulary:

```text
completed
failed-executor
failed-provider
timed-out
cancelled
killed
evidence-incomplete
invalid-protocol
```

A timeout should record both the benchmark deadline and the eventual process termination time.

## 2.9 Baseline/candidate cohort semantics

A cohort comparison must use paired benchmark cases wherever possible.

For each case:

* run baseline and candidate against the same immutable input;
* use the same executor family/version, model, tool policy, resource limits, environment image, and evaluator;
* randomize or alternate run order;
* use multiple independent replicates;
* record warm/cold cache policy;
* avoid sharing conversational state across trials;
* define timeout and retry policy before execution;
* seal evidence before scoring aggregation.

Primary comparisons:

```text
paired score difference
paired wall-time ratio
paired token ratio
paired attributable-cost ratio
success-rate difference
steer/retry/error-rate difference
```

Report distributions and confidence intervals, not just grand totals. Token and cost comparisons should exclude neither failures nor retries; instead present:

* unconditional cost per scheduled trial;
* cost per successful trial;
* success-adjusted utility;
* failure-specific resource consumption.

Do not merge trials with materially different models or pricing epochs into one homogeneous cost cohort. Stratify them or normalize only in a clearly labeled derived analysis.

## 2.10 Real-executor cohort protocol

1. Freeze benchmark case inputs and expected scoring rules.
2. Freeze baseline and candidate artifact digests.
3. Pin executor version, model ID, environment image, tool permissions, and timeout.
4. Capture executor capability metadata before trials.
5. Run a telemetry calibration case to determine:

   * whether usage events are delta, cumulative, or terminal;
   * cached-token semantics;
   * whether reasoning tokens are included in output;
   * behavior on reconnect, retry, cancellation, and errors.
6. Execute at least one cold-cache and one warm-cache block where caching matters.
7. Use randomized paired order across cases.
8. Preserve raw streaming events, stdout, stderr, control events, and produced artifacts.
9. Normalize only after raw evidence is sealed.
10. Reject or mark incomplete any trial whose usage accounting cannot be reconciled.
11. Run the evaluator from sealed artifacts, not from mutable working directories.
12. Publish the exact cohort manifest containing every included and excluded trial digest and exclusion reason.

---

# 3. Prioritized actionable recommendations

## Priority 0 — protect the source-of-truth boundary

**Recommendation:** Declare fsynced append-only control records authoritative and every notifier advisory.

**Falsifying evaluation:** Kill producers and consumers at every boundary around append, flush, `fsync`, signal, read, execute, and cursor commit. The recommendation fails if a durably accepted record can become permanently undiscoverable or if a non-durable record is executed as accepted.

## Priority 1 — use tmux only for present-day wakeups

**Recommendation:** Add tmux `wait-for` only as a post-`fsync` accelerator, with reconciliation polling.

**Falsifying evaluation:** Repeatedly signal before wait, during tmux-server restart, during consumer restart, and during bursts of thousands of appends. The design fails if final execution differs from pure replay of the durable journal.

## Priority 2 — require idempotent consumers and durable cursors

**Recommendation:** Identify every control record globally and commit each consumer cursor only after successful handling or durable terminal disposition.

**Falsifying evaluation:** Replay every record multiple times, crash during handling, and reorder advisory wakeups. The design fails if externally visible effects occur more than once where the control contract requires once-only behavior.

## Priority 3 — standardize usage-mode semantics before adding providers

**Recommendation:** Require every usage event to declare `delta`, `cumulative`, or `terminal`; reject ambiguous aggregation.

**Falsifying evaluation:** Feed the normalizer duplicated cumulative events, replayed terminal events, Codex-style repeated `last_token_usage`, and mixed nested aggregates. The recommendation fails if normalized totals differ from authoritative terminal totals.

## Priority 4 — preserve raw events and immutable evidence

**Recommendation:** Seal raw executor evidence before normalization and identify all derived artifacts by digest.

**Falsifying evaluation:** Re-run normalization from sealed raw evidence on a clean machine. The design fails if normalized evidence is nondeterministic without an explicitly recorded environmental dependency.

## Priority 5 — treat unknown evidence as null

**Recommendation:** Prohibit conversion of missing token, reasoning, cache, time, or cost data to zero.

**Falsifying evaluation:** Use executors that omit terminal usage, cache-write details, reasoning detail, or price metadata. The design fails if reports imply a measured zero or rank such trials as cheaper solely because evidence was absent.

## Priority 6 — introduce distributed messaging only for a demonstrated need

**Recommendation:** Delay Redis Streams or NATS JetStream until workers must cross a host boundary or local journal scan/wakeup behavior fails an explicit service objective.

**Falsifying evaluation:** Measure end-to-end steering latency, CPU wakeups, missed-advisory recovery time, and operational incidents on the single-host design. This recommendation is falsified if local mechanisms cannot meet the defined latency or availability objective without broker semantics.

## Priority 7 — prefer JetStream for a future general control plane

**Recommendation:** If multi-host orchestration becomes necessary and no existing broker is mandated, evaluate NATS JetStream first; retain a Redis Streams adapter boundary.

**Falsifying evaluation:** Prototype identical workloads under fault injection: broker restart, network partition, duplicate publication, consumer crash, slow consumer, credential revocation, retention pressure, and replay. Reject JetStream if it cannot meet recovery and operational objectives more simply than Redis within the project’s actual deployment environment.

---

# 4. Open questions

1. Is the authoritative JSONL journal stored on a local disk, network filesystem, or immutable object/artifact store?
2. Does `fsync` durability need to survive only process and OS crashes, or also host/power/storage-controller failures?
3. Is strict global order required, or only order per orchestration scope or target agent?
4. May multiple producers append to one journal, and what assigns the sequence?
5. Which control operations require exactly-once external effects rather than idempotent at-least-once processing?
6. What maximum steering-detection latency is acceptable without a wakeup?
7. Will multi-host workers share an artifact store from which durable records can be fetched?
8. Must records be cryptographically signed across trust domains, or is host-level access control sufficient?
9. Which real executors are required in the first benchmark cohort: Codex CLI, OpenAI Agents SDK, Claude Code/Agent SDK, Gemini-based agents, or others?
10. Are trials billed through direct APIs, subscriptions, enterprise quotas, or mixed arrangements?
11. Should benchmark cost represent list-price estimate, invoice-attributed spend, or both?
12. Are warm-cache trials a target production condition or merely a diagnostic cohort?
13. What minimum replicate count and practical effect threshold should gate candidate acceptance?
14. How should interrupted or human-assisted trials affect the primary score?

# Final decision statement

Adopt **durable-log-first orchestration**: fsynced JSONL records, durable consumer cursors, idempotent replay, tmux wakeups today, and transport-neutral broker adapters later. Notifications optimize latency; they never establish truth.

Adopt **raw-first immutable benchmark evidence**: explicit delta/cumulative/terminal usage semantics, provider-specific cache mapping, null-preserving normalization, pinned pricing provenance, complete retry and error accounting, and paired real-executor cohorts built from sealed trial artifacts.
