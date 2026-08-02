# Security policy

`agent-workflow` executes operator-selected coding agents and explicit commands against source repositories. Treat prompts, prompt packs, delegated processes, provider output, generated patches, and target repositories as untrusted until reviewed.

The repository-wide security classification and residual-risk inventory is [Feature determinism and security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md). Canonical remediation state is in [BACKLOG.md](BACKLOG.md) and the dependency plan is [Determinism and security hardening plan](DETERMINISM_SECURITY_HARDENING_PLAN.md).

## Supported status

The project is pre-public-release. GitHub Private Vulnerability Reporting is the selected primary disclosure channel, but `REL-002` remains in review until a repository administrator enables it and records a successful private notification drill. Do not publish sensitive reports in a public issue tracker. The repository-root [`SECURITY.md`](../SECURITY.md) is the canonical reporting policy.

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

- writable-path policy for untrusted commands is primarily post-run detection rather than preventative OS-level filesystem/network/resource isolation (`HARD-003`);
- terminal, incident, and searchable index fields use bounded redaction/exclusion, but comprehensive field-level classification, retention, export, deletion, and analytical-release policy remains incomplete (`HARD-006`, `SUP-003`, `IDX-006`);
- process/resource telemetry is observational; preventative CPU/memory/disk/network enforcement and adaptive backpressure remain incomplete (`HARD-003`, `SUP-004`);
- actor strings are not authenticated principals, so reviewer independence and remediation/permission attribution remain procedural rather than cryptographically or OS-authenticated (`HARD-007`, `SUP-005`);
- config/executable ownership and compatibility evidence are enforced by explicit local/governed/release policy; repository-local hooks and filters remain an operator-visible trust decision rather than being silently disabled;
- generated inventory and backlog drift enforcement remains incomplete (`HARD-009`);
- release checks emit a synchronized dependency lock, CycloneDX SBOM, structured test evidence, and source/build provenance, but full transitive hashes, independent reproducibility, and authenticated signing/attestation remain open (`HARD-010`);
- the selected GitHub private reporting channel still requires repository-side enablement and a notification drill (`REL-002`);
- supported clean-host/tmux/executor combinations and a real tagged release remain evidence-gated (`REL-003`, `REL-008`).

Accepted HARD-001, HARD-002, HARD-004, HARD-005, and HARD-008 foundations are no longer listed as open limitations. Do not describe the remaining controls as complete until their canonical backlog exit evidence exists.

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

Use GitHub Private Vulnerability Reporting as described in the repository-root [`SECURITY.md`](../SECURITY.md). Until the repository setting is verified as enabled, trusted collaborators should use an already established private maintainer channel only to request a private advisory path; do not send vulnerability details through public issues or discussions.
