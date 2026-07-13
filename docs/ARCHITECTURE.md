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
        ├── command.json
        ├── output.log
        ├── completion.md
        ├── run.sh
        └── update_status.py
```

A worktree-local `.delegations/<session-id>` symlink points to the durable run directory. The tool adds `.delegations/` to Git's local exclude metadata, so observability does not create a source change. Worktree cleanup therefore does not destroy evidence.

## Process boundary

The CLI creates one detached tmux session whose process is a generated runner. The runner:

1. atomically marks the run `running`;
2. changes to the worktree;
3. pipes the immutable prompt copy to the selected executor;
4. tees output to the persistent log;
5. records completion, interruption, or failure on exit.

Commands are stored as argv arrays and rendered using shell-safe quoting. The generated script is checked with `bash -n` before tmux launches it.

## State model

```text
prepared -> launched -> running -> completed
                              \-> failed
                              \-> interruption_requested -> interrupted
operator kill -------------------------------------------> killed
```

`possibly_stalled`, `orphaned`, and `terminal_unavailable` are observed states, not durable lifecycle states.

## Security posture

- Session IDs are restricted to safe filesystem/tmux characters.
- Status writes are atomic.
- Prompt SHA-256 and source revision are recorded before execution.
- The workflow stores no external-service credentials.
- No automatic merge, branch deletion, or failed-worktree cleanup occurs.
- Interrupt, terminate, and kill preserve logs and source trees.
