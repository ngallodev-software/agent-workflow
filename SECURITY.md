# Security policy

`agent-workflow` executes operator-selected coding agents and explicit commands against source repositories. Treat prompts, prompt packs, delegated processes, provider output, generated patches, and target repositories as untrusted until reviewed.

## Supported status

The project is pre-public-release and does not yet have a monitored public vulnerability-reporting channel. This is a release blocker tracked as `REL-002` in [BACKLOG.md](BACKLOG.md). Do not publish sensitive reports in a public issue tracker.

## Security boundaries

- Commands are preserved as argv arrays and rendered with shell-safe quoting.
- IDs are restricted before they become paths, tmux names, or evidence keys.
- Configured roots are resolved and traversal/symlink escapes are rejected.
- Prompts, source state, commands, streams, artifacts, and receipts are hashed.
- Status files, logs, and terminal capture are projections, not authorities.
- Final, lifecycle, score, and workflow receipts are regular read-only files verified through stable descriptors.
- Workflow state is reconstructed from an immutable snapshot and append-only journal.
- Approval is explicit and binds actor, reason, revision, and sealed evidence.
- Provider usage fails closed on mixed modes, conflicting identities, malformed totals, or incomplete cost metadata.
- MCP is optional, local stdio, bounded to configured roots, and currently read-only.
- The project does not automatically merge, delete failed worktrees, terminate suspected stalls, expose remote execution, or authorize network MCP transport.

## Operator responsibilities

- Run agents with the least filesystem, network, and tool access needed.
- Keep credentials and private data out of prompts, argv, logs, repositories, and state bundles.
- Review patches and evidence before executing project code or accepting a run.
- Use separate operating-system accounts, containers, or disposable hosts for higher-risk targets.
- Protect the XDG state directory; it can contain source paths, prompts, model output, provider streams, and code fragments.
- Do not publish a receipt bundle without reviewing every sealed artifact it references.

The default state location is:

```text
~/.local/state/agent-workflow
```

## Reporting before public release

Trusted collaborators should contact the maintainer through an existing private channel and provide the smallest safe reproduction. Include version, platform, command category, and whether the issue affects path containment, evidence authority, process control, or provider accounting. Do not include secrets or private state bundles unless a secure transfer path has been agreed.
