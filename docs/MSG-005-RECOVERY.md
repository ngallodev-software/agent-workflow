# MSG-005 recovery matrix

The source child journal and aggregate inbox are authoritative. Registry,
cursor, and supervisor status files are rebuildable projections. A wake signal
only reduces latency; it is never required for correctness.

## Crash windows

| Window | Durable authority | Restart behavior | Semantic effect |
| --- | --- | --- | --- |
| Before source read | child journal | replay reads the same FIFO source | none lost |
| After source read, before inbox append | child journal | cursor remains behind; replay retries | one import |
| Before inbox append | child journal | append is retried | one import |
| After inbox append, before cursor update | inbox event | stable source ID/digest deduplicates | one event |
| After notification attempt | inbox event/cursor and fixed opaque notification receipt | next periodic replay ignores duplicate wake and reuses the event digest | one event |
| After application acknowledgement | acknowledgement journal plus event ID/digest | pending action projection is rebuilt from the inbox and acknowledgement evidence | event remains visible |
| Before action append | inbox and acknowledgement journals | action is still pending after restart | no lost action |
| After action append | action journal plus event ID/digest | action is not replayed; status is rebuilt from the durable action record | one semantic action |

The implementation commits the inbox event and fsyncs it before advancing the
source cursor. If a cursor is absent, malformed, behind, or otherwise
inconsistent, startup reconstructs the highest contiguous source prefix proven
by source records plus inbox event IDs and digests. A malformed projection is
removed only after a bounded, redacted quarantine record is written.

## Ownership and stale locks

`orchestrator watch` takes an exclusive filesystem lock. The lock file retains
bounded owner metadata: PID, boot ID, `/proc` start ticks, and acquisition
time. A second live supervisor fails without writing. After a crash, the next
owner may reuse the still-present lock file only after process identity/start
evidence shows the previous owner is dead or stale; elapsed time is not
authority. If the host cannot establish that evidence, recovery fails closed
unless the operator supplies `--operator-override`. The override is bounded to
that one startup and never edits source journals or lifecycle evidence.

## Timing and fairness

The watch interval is capped at two seconds to meet the normal `DEC-001`
no-wakeup objective. Each cycle replays every active child with a bounded
batch and per-child limit, rotating the starting child from durable cursor
progress. This prevents one noisy child from starving other children during a
downtime backlog.

The optional `acknowledgements.jsonl` and `actions.jsonl` journals are read as
durable evidence on every cycle. Each record must reference an existing inbox
event with its canonical event digest; unknown IDs, digest mismatches, and
conflicting duplicate records fail closed. Events lacking acknowledgement,
and acknowledged events lacking action evidence, remain in the supervisor
report and status projection after restart. The status projection stores both
the pending event IDs and their digests, so a same-length but inconsistent
projection is quarantined with bounded redacted metadata and rebuilt.
