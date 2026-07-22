# Architecture

## Ownership model

```text
agent-workflow repository
  owns execution, terminal sessions, state, templates, validation, and workflow policy

prompt pack
  owns project phases, tickets, references, code outlines, and acceptance gates

target repository/worktree
  owns implementation source and legitimate project tests
```

## Runtime state

The authoritative state root is XDG-based:

```text
~/.local/state/agent-workflow/
└── runs/
    └── <session-id>/
        ├── status.json
        ├── source-baseline.json
        ├── prompt.md
        ├── launch-prompt.md
        ├── command.json
        ├── run-provenance.json
        ├── executor-events.jsonl
        ├── executor-stderr.log
        ├── output.log
        ├── completion.md
        ├── completion.json
        ├── patch.diff
        ├── final-status.json
        ├── final-receipt.json
        ├── heartbeat.json
        ├── events.jsonl
        ├── collections/       # evaluation runs only
        ├── scope/             # evaluation runs only
        ├── receipts/          # review lifecycle only
        ├── run.sh
        └── scores/            # generated after sealing
```

A worktree-local `.delegations/<session-id>` symlink points to the durable run directory. The tool adds `.delegations/` to Git's local exclude metadata, so observability does not create a source change. Worktree cleanup therefore does not destroy evidence.

## Process boundary

The CLI creates one detached tmux session whose process is a generated runner. The runner:

1. atomically marks the run `running` and emits a lifecycle event;
2. starts the executor as its own process group and forwards interrupts;
3. passes `launch-prompt.md` on stdin and preserves stdout JSONL plus stderr separately;
4. writes heartbeat records and enforces evaluation time/token budgets;
5. captures post-agent scope before running post-agent acceptance commands;
6. finalizes provenance, captures the patch, validates every core contract, and seals the fixed artifact set;
7. records the final-receipt hash in mutable status and makes sealed evidence read-only.

The generated `run.sh` is a thin, shell-quoted invocation of the Python runner and is checked with `bash -n`. Process ownership, stream parsing, collection, and sealing exist only in reusable Python modules.

## State model

```text
prepared -> launched -> running -> completed
                              \-> failed
                              \-> interruption_requested -> interrupted
operator kill -------------------------------------------> killed
```

Review is an independent dimension: `null -> reviewed -> accepted|rejected`. Review receipts reference immutable final-receipt and deterministic score-set hashes; execution success never implies acceptance.

`possibly_stalled`, `orphaned`, and `terminal_unavailable` are observed states, not durable lifecycle states.

## Security posture

- Session IDs are restricted to safe filesystem/tmux characters.
- Status writes are atomic and lifecycle transitions are append/fsync-before-snapshot events.
- Prompt SHA-256 and source revision are recorded before execution.
- The workflow stores no external-service credentials.
- No automatic merge, branch deletion, or failed-worktree cleanup occurs.
- Interrupt, terminate, and kill preserve logs and source trees.

## Evaluation topology

The accepted topology is documented in `docs/adr/0001-inspect-evaluation-topology.md`: host `agent-workflow` owns tmux and local evidence, while Inspect owns the Docker sandbox, model bridge, transcripts, and adapter lifecycle. Public `inspect_swe.codex_cli()` and `inspect_swe.claude_code()` adapters are reused whole; private Inspect internals are not copied.
