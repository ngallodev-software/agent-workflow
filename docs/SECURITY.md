# Security policy

`agent-workflow` executes operator-selected coding agents and explicit commands against source repositories. Treat prompts, prompt packs, delegated processes, provider output, generated patches, and target repositories as untrusted until reviewed.

The repository-wide security classification and residual-risk inventory is [Feature determinism and security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md). Canonical remediation state is in [BACKLOG.md](BACKLOG.md) and the dependency plan is [Determinism and security hardening plan](DETERMINISM_SECURITY_HARDENING_PLAN.md).

## Supported status

The project is pre-public-release and does not yet have a monitored public vulnerability-reporting channel. This is a release blocker tracked as `REL-002`. Do not publish sensitive reports in a public issue tracker.

## Implemented security boundaries

- Commands are represented as argv arrays rather than shell command strings in governed launch paths.
- IDs are restricted before they become paths, tmux names, or evidence keys.
- Many authority files are regular read-only files verified through stable descriptors and content digests.
- Status files, logs, terminal capture, and SQLite index rows are projections, not authorities.
- Workflow state is reconstructed from an immutable snapshot and append-only journal.
- Approval is explicit and binds an actor label, reason, revision, and sealed evidence.
- Provider usage fails closed on mixed modes, conflicting identities, malformed totals, or incomplete cost metadata.
- MCP is local stdio, read-only, metadata-minimal, bounded to configured roots with component-wise no-follow reads, stable bounded errors, parser-derived command discovery, and verified launch-contract command context. Command catalogs are not authorization, absolute executable paths are redacted, and command-artifact drift fails closed.
- Repository-owned subprocesses use one argv-only substrate with process-group timeout/cancellation, per-stream caps, controlled environments, executable identity, and configured-value/secret-argument redaction.
- Configuration is executable policy: schema version 1 rejects unknown keys and reads config without following links. Governed/release mode requires user ownership and no group/world write bits for config, state, repository allowlists, and policy files; local mode exposes the same findings as doctor warnings.
- Named executors are resolved to the actual launched path and probed through the bounded process substrate. Versioned compatibility data supplies adapter versions and explanation codes; unsupported governed adapters fail closed. Doctor and provenance omit credentials.
- Prompt packs, native jobs, prompts, and MCP repository/state roots use component-wise no-follow traversal; irregular entries and content changes during validation are rejected. Pack archives are built from the validated inventory and include a typed canonical manifest.
- Runtime schemas come only from the executing source checkout or installed package asset set; duplicate IDs, malformed assets, and missing packaged assets fail closed.
- Bounded health supervision records changed/redacted terminal snapshots, process/resource samples, permission observations, typed incidents, and remediation outcomes. Mutable status repair is allowed only from immutable authority; safe progress probes are attempt-bounded. Interrupt/restart are disabled by default and cannot widen authority.
- The SQLite evidence index is host-local and rebuildable. A single locked writer imports bounded normalized fields plus source digests; fixed read-only queries cannot mutate authority. Raw prompts, message bodies, terminal bodies, executor output, credentials, and large logs are excluded from the index by design.
- The project does not automatically merge, delete failed worktrees, grant permissions, expose credentials, expand sandbox/network/model policy, accept work, expose remote execution, or authorize network MCP transport.

## Search-index trust boundary

The database at the configured state root is a convenience and analysis surface. It must never be used to authorize launch, steering, permission, review, acceptance, merge, retry, or deletion. Every indexed source row carries a relative source path, record sequence where applicable, schema identity, and SHA-256 provenance. Full verification rehashes those sources; rebuilding from source is the recovery path.

The index deliberately avoids arbitrary SQL through the CLI and does not duplicate high-risk free-form bodies. Any future Parquet export, remote query API, or multi-user database requires the `HARD-006` retention/redaction decision and a separate exposure review. SQLite file ownership and directory permissions remain subject to the same trust checks as the rest of the state root.

## Known pre-public limitations

These are active release blockers, not theoretical future hardening:

- The bounded process substrate is integrated for governed call sites, but shared installed-product acceptance and the foundation phase gate remain open (`HARD-001`); `tmux.attach` remains the documented interactive-only terminal ownership boundary.
- Prompt-pack, native-job, schema, and bounded-path integrity controls are integrated, but filesystem-socket coverage was unavailable on this host and shared phase-gate acceptance remains open (`HARD-002`).
- MCP reads are metadata-minimal, bounded, and component-wise no-follow, but the installed stdio journey remains unverified and phase-gate acceptance remains open (`HARD-005`).
- writable-path policy for untrusted commands is primarily post-run detection rather than a preventative OS sandbox (`HARD-003`);
- some runner/evaluation decisions still depend on mutable status projections rather than one immutable launch authority (`HARD-004`);
- terminal, incident, and searchable index fields use bounded redaction/exclusion, but comprehensive field-level classification, retention, export, deletion, and analytical-release policy remains incomplete (`HARD-006`, `SUP-003`, `IDX-006`);
- process/resource telemetry is observational; preventative CPU/memory/disk/network enforcement and adaptive backpressure remain incomplete (`HARD-003`, `SUP-004`);
- actor strings are not authenticated principals, so reviewer independence and remediation/permission attribution remain procedural rather than cryptographically or OS-authenticated (`HARD-007`, `SUP-005`);
- config/executable ownership and compatibility evidence are enforced by explicit local/governed/release policy; repository-local hooks and filters remain an operator-visible trust decision rather than being silently disabled;
- release checks now emit a synchronized direct-dependency lock, CycloneDX SBOM, structured test evidence, and source/build provenance (`REL-005`), but full transitive hashes, independent reproducibility, and authenticated signing/attestation remain open (`HARD-010`).

Do not describe these controls as complete until their backlog exit evidence exists.

## Operator responsibilities

- Run agents with the least filesystem, network, and tool access needed.
- Keep credentials and private data out of prompts, argv, logs, repositories, and state bundles.
- Review patches and evidence before executing project code or accepting a run.
- Use separate operating-system accounts, containers, or disposable hosts for higher-risk targets.
- Protect the XDG state directory; it can contain source paths, prompts, model output, provider streams, bounded terminal snapshots, process telemetry, permission observations, and code fragments.
- Do not publish a receipt bundle without reviewing every sealed artifact it references.
- Treat current actor labels as commentary, not proof of reviewer identity.

The default state location is:

```text
~/.local/state/agent-workflow
```

## Reporting before public release

Trusted collaborators should contact the maintainer through an existing private channel and provide the smallest safe reproduction. Include version, platform, command category, and whether the issue affects path containment, evidence authority, process control, identity, information disclosure, or provider accounting. Do not include secrets or private state bundles unless a secure transfer path has been agreed.
