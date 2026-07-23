# Messaging Prior Art and Local Control Contract

## Decision

Use the run directory as the sole authority, with an append-only JSONL log protected by
an advisory file lock and `fsync`. A waiter always replays durable records. `tmux wait-for`
may later be used only as a latency accelerator; it cannot become the source of truth.
The message UUID is the idempotency identity, sequence is contiguous within a run, and a
steer remains pending until a child appends a correlated acknowledgement after applying it.

## Decision matrix

| Option | Durable replay | Multiwriter behavior | Operational cost | Fit |
|---|---|---|---|---|
| Filesystem JSONL + `flock`/`fsync` | Yes, by replay | Serialized local writers | None beyond the CLI | **Selected** |
| `tmux wait-for` / control mode | No durable history by itself | Synchronization only | Already available | Wakeup accelerator only |
| SQLite WAL | Yes | Strong transactions, one writer at a time | Schema/database lifecycle | Unnecessary for one small log |
| Redis Streams | Yes, consumer groups and acknowledgements | Server-mediated | Requires a service | Reject for local-only CLI |
| NATS JetStream | Yes, durable consumers and explicit acknowledgements | Server-mediated | Requires a service | Reject for local-only CLI |
| Temporal Signals/Updates | Workflow-history durability | Service-mediated | Requires Temporal | Reject for local-only CLI |

## Frozen contract

- **Authority:** `<run>/messages.jsonl`; lifecycle `events.jsonl` remains separate.
- **Wakeup:** optional `tmux wait-for` signal. After every wakeup, replay from the last
  accepted sequence. Lost or coalesced wakeups therefore do not lose records.
- **Identity:** canonical UUID `message_id`; consumers deduplicate by UUID.
- **Ordering:** writers hold an exclusive lock, validate the complete existing log,
  allocate the next contiguous sequence, append one line, flush, and `fsync`.
- **Acknowledgement:** only a child-to-parent `ack` may correlate to an existing
  parent-to-child `steer`; duplicate acknowledgements are rejected.
- **Retention:** records are bounded per run and sealed with the run. Compaction is not
  performed while active.
- **Recovery:** restart replays from sequence zero or the consumer's last durable cursor.
  A malformed or partial tail blocks further append rather than silently truncating data.

## Delivery boundary

`tmux send-keys` injects terminal input. It does not prove that an opaque one-shot executor
accepted, parsed, applied, or semantically associated that input with a steering request.
A genuine live adapter must name the executor capability, submit through its supported
control interface, and append an acknowledgement containing the request UUID only after
application. Where stdin closes after the initial prompt, the safe state is durable and
pending—not “delivered.”

## Threat model and mitigations

| Threat | Mitigation |
|---|---|
| Traversal or symlink redirection | Fixed filename, validated session IDs, real run directory, regular non-symlink log |
| Concurrent writers | `flock(LOCK_EX)` around validation, sequence allocation, append, flush, and `fsync` |
| Partial write or corrupt tail | Strict line-by-line JSON and contiguous-sequence validation; reject append on corruption |
| Duplicate delivery | UUID idempotency key and explicit correlated acknowledgement |
| Oversized or malformed payload | Bounded content and closed direction/kind/field sets |
| False local authority | Disk replay is authoritative; wakeups and terminal output are advisory |

## Primary references

- tmux manual and source: `https://github.com/tmux/tmux/blob/master/tmux.1`
- tmux control mode: `https://github.com/tmux/tmux/wiki/Control-Mode`
- SQLite WAL: `https://www.sqlite.org/wal.html`
- Redis Streams: `https://redis.io/docs/latest/develop/data-types/streams/`
- NATS JetStream consumers: `https://docs.nats.io/nats-concepts/jetstream/consumers`
- Temporal message passing: `https://docs.temporal.io/develop/python/message-passing`

The service-backed options offer valuable cross-host consumer state, ACLs, replication,
and server-managed redelivery, but those properties do not justify introducing a daemon
or network dependency for the current single-host CLI. Redis and JetStream explicitly use
pending/acknowledgement models, reinforcing the selected at-least-once plus idempotency
contract. SQLite WAL adds transactional storage but also a database schema and checkpoint
lifecycle that the bounded append-only control stream does not need.
