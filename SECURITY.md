# Security policy

`agent-workflow` executes operator-selected coding agents and explicit commands against source repositories. Treat prompts, prompt packs, delegated processes, provider output, generated patches, and target repositories as untrusted until reviewed.

The repository-wide security classification and residual-risk inventory is [Feature determinism and security assessment](docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md). Canonical remediation state is in [BACKLOG.md](BACKLOG.md) and the dependency plan is [Determinism and security hardening plan](docs/DETERMINISM_SECURITY_HARDENING_PLAN.md).

## Supported status

The project is pre-public-release and does not yet have a monitored public vulnerability-reporting channel. This is a release blocker tracked as `REL-002`. Do not publish sensitive reports in a public issue tracker.

## Implemented security boundaries

- Commands are represented as argv arrays rather than shell command strings in governed launch paths.
- IDs are restricted before they become paths, tmux names, or evidence keys.
- Many authority files are regular read-only files verified through stable descriptors and content digests.
- Status files, logs, and terminal capture are projections, not authorities.
- Workflow state is reconstructed from an immutable snapshot and append-only journal.
- Approval is explicit and binds an actor label, reason, revision, and sealed evidence.
- Provider usage fails closed on mixed modes, conflicting identities, malformed totals, or incomplete cost metadata.
- MCP is optional, local stdio, bounded to configured roots, and currently read-only.
- Repository-owned subprocesses use one argv-only substrate with process-group timeout/cancellation, per-stream caps, controlled environments, executable identity, and configured-value/secret-argument redaction.
- The project does not automatically merge, delete failed worktrees, terminate suspected stalls, expose remote execution, or authorize network MCP transport.

## Known pre-public limitations

These are active release blockers, not theoretical future hardening:

- prompt-pack/native-job/schema/MCP path integrity is not yet uniformly no-follow and content-complete (`HARD-002`, `HARD-005`);
- writable-path policy for untrusted commands is primarily post-run detection rather than a preventative OS sandbox (`HARD-003`);
- some runner/evaluation decisions still depend on mutable status projections rather than one immutable launch authority (`HARD-004`);
- default sensitive-content classification, redaction, and retention controls are incomplete (`HARD-006`);
- actor strings are not authenticated principals, so reviewer independence is procedural rather than cryptographically or OS-authenticated (`HARD-007`);
- config/executable ownership and compatibility evidence are incomplete (`HARD-008`);
- release artifacts are checksummed but not yet backed by the full lock/SBOM/provenance/signing path (`HARD-010`).

Do not describe these controls as complete until their backlog exit evidence exists.

## Operator responsibilities

- Run agents with the least filesystem, network, and tool access needed.
- Keep credentials and private data out of prompts, argv, logs, repositories, and state bundles.
- Review patches and evidence before executing project code or accepting a run.
- Use separate operating-system accounts, containers, or disposable hosts for higher-risk targets.
- Protect the XDG state directory; it can contain source paths, prompts, model output, provider streams, and code fragments.
- Do not publish a receipt bundle without reviewing every sealed artifact it references.
- Treat current actor labels as commentary, not proof of reviewer identity.

The default state location is:

```text
~/.local/state/agent-workflow
```

## Reporting before public release

Trusted collaborators should contact the maintainer through an existing private channel and provide the smallest safe reproduction. Include version, platform, command category, and whether the issue affects path containment, evidence authority, process control, identity, information disclosure, or provider accounting. Do not include secrets or private state bundles unless a secure transfer path has been agreed.
