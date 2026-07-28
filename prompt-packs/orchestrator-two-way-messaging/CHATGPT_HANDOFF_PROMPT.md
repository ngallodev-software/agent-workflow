# ChatGPT handoff — orchestrator two-way messaging

Treat current source, [`BACKLOG.md`](../../docs/BACKLOG.md), the [messaging design](../../docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md), and this pack’s collision matrix as authoritative.

1. Before starting this pack, use [`CHATGPT_BLOCKER_CLEARANCE_PROMPT.md`](CHATGPT_BLOCKER_CLEARANCE_PROMPT.md) to clear or explicitly disposition the deterministic, identity, content-safety, and executor-trust prerequisites. Then run the deterministic release drift audit and validate this pack.
2. Confirm `DEC-001` and every ticket-specific `HARD-*` prerequisite before editing.
3. Launch dependency-free tickets concurrently only in separate worktrees and durable sessions.
4. Keep per-session journals and sealed lifecycle evidence authoritative. The aggregate inbox is a delivery record; tmux signals are hints.
5. Require installed-product acceptance journeys first. Retain only compact replay, security, and adapter normalization matrices.
6. Never inject child-controlled text into the orchestrator pane. Wake/resume adapters receive fixed application-owned text and opaque event IDs only.
7. Integrate completed tickets deliberately, rerun shared journeys, then delegate `MSG-GATE-01` to an independent reviewer using `phase-gate-review` and `release-drift-auditor`.
8. Stop on backlog ownership collision, unresolved prerequisite, duplicate scheduler/state machine, prompt-level policy presented as enforcement, or any design that advances cursors before durable side effects commit.

Do not add remote transport, a broker, a web UI, autonomous model routing, a memory layer, terminal scraping, or unrelated cleanup.
