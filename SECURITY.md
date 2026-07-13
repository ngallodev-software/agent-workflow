# Security and Trust Boundaries

`agent-workflow` executes operator-selected coding agents and arbitrary explicit commands. Treat every delegated command, prompt pack, target repository, and generated patch as untrusted until reviewed.

## Guarantees in v0.1

- Commands are stored as argv arrays and rendered with shell-safe quoting.
- Session, ticket, and pack identifiers are restricted to safe filesystem and tmux characters.
- Prompts are copied into durable state and hashed before execution.
- Source revision, branch, and dirty state are recorded before launch.
- Status files are updated atomically.
- A delegation receives a fresh named tmux session; existing session and run-state names are rejected.
- Interrupt, terminate, kill, and restart preserve prior logs and evidence.
- The workflow never merges branches, deletes failed worktrees automatically, or kills a merely suspected stalled process.

## Operator responsibilities

- Review prompt packs before execution.
- Run agents with the least filesystem and network access appropriate to the ticket.
- Keep credentials out of prompts, logs, repositories, and command arguments.
- Inspect diffs before running project tests or merging.
- Treat model-generated shell commands, dependency changes, and network calls as untrusted.
- Use separate operating-system accounts or containers for higher-risk repositories.

## State sensitivity

The state directory can contain source paths, prompts, model output, and code fragments. Its default location is:

```text
~/.local/state/agent-workflow
```

Protect it with normal user-only filesystem permissions and do not publish it as part of a source repository.

## Reporting

This initial package does not prescribe a public vulnerability-reporting address. Add one before publishing the repository beyond trusted collaborators.
