# Public release readiness

The repository is technically substantial but is not yet ready to publish as a supported open-source project. The remaining release boundary is no longer the deterministic foundation: it is preventative isolation, sensitive-data policy, authenticated identity, supported-host evidence, supply-chain closure, and maintainer governance.

Canonical task state is in [BACKLOG.md](BACKLOG.md). The detailed threat and determinism findings remain in [Feature determinism and security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md), with sequencing in [Determinism and security hardening plan](DETERMINISM_SECURITY_HARDENING_PLAN.md).

## Current strengths

- installed-wheel acceptance journeys cover the primary CLI, workflow, lifecycle, prompt-pack, evaluation, and benchmark paths;
- immutable JSON/JSONL authority is separated from rebuildable status, tmux, rendered, and SQLite projections;
- bounded process, path/schema, immutable-launch, MCP read-boundary, and executor/config trust foundations are accepted;
- deterministic archives, packaged schemas, release evidence, installer bundles, checksums, and tag-only publication workflow exist;
- prompt-pack ownership and dependency lanes are explicit and release-audited;
- the comparative benchmark has a complete synthetic paired journey and truthful external-evidence gates;
- CI configuration covers the declared Python versions.

Local Jenkins results are development-host evidence only. They do not establish a supported public compatibility matrix or replace clean-host release evidence.

## Accepted technical foundations

| Canonical task | Accepted capability |
|---|---|
| HARD-001 | Bounded process execution, cancellation, output/environment limits, and evidence |
| HARD-002 | Artifact/path/schema integrity and no-follow boundaries |
| HARD-004 | Immutable launch and final-receipt authority independent of mutable status |
| HARD-005 | Metadata-minimal, bounded, path-safe read-only MCP boundary |
| HARD-008 | Configuration/executor trust, executable identity, and sanitized host environment |

These items remain in the completed backlog history and must not be reopened by old blocker inventories.

## Active technical blockers before a public preview

| Priority | Blocker | Canonical task | Current state and exit evidence |
|---|---|---|---|
| P0 | Preventative execution isolation | HARD-003 | `ready`: enforce write/read/network/resource policy through supported platform backends and fail closed when none is available |
| P1 | Sensitive-content handling | HARD-006 | `ready`: classification, redaction, explicit disclosure, retention, export, and deletion evidence |
| P1 | Authenticated review identity | HARD-007 | `ready`: immutable principal evidence and enforceable independent-review policy |
| P1 | Generated drift gate | HARD-009 | blocked on HARD-003/HARD-006/HARD-007: source-derived inventories plus backlog state/prerequisite consistency and stale-artifact detection |
| P1 | Supply-chain integrity | HARD-010 | blocked on the isolation gate: transitive locks/audit, standards-based SBOM/provenance, reproducibility, and authenticated signing/attestation |

## Governance and compatibility blockers

The primary vulnerability channel decision is complete: use GitHub Private Vulnerability Reporting and the repository `SECURITY.md` policy. REL-002 remains in review until an administrator enables the repository setting and records a successful private notification drill.

| Priority | Blocker | Canonical task | Current state and exit evidence |
|---|---|---|---|
| Complete | Select and add an open-source license | REL-001 | Apache-2.0 configured in `LICENSE`, package metadata, and release policy |
| P0 | Establish vulnerability reporting | REL-002 | `in-review`: GitHub Private Vulnerability Reporting and `SECURITY.md` are selected; administrator enablement plus a private notification drill remain open |
| P0 | Supported host/executor matrix | REL-003 | `ready`: approve Linux/Python/tmux/executor versions and record representative clean-host live compatibility evidence |
| P1 | Installer release proof | REL-008 | `in-review`: run a real immutable tag/release and representative bundle install/uninstall journeys |
| P1 | Public-preview decision | REL-004 | blocked: independent clean-artifact gate with explicit go/no-go, supported boundary, signatures, and rollback/advisory ownership |

Until the P0 technical and governance blockers close, distribute source archives only to trusted collaborators and do not describe the project as a supported public release.

## Deliberately non-blocking future work

State-mutating MCP, remote transport, multi-host orchestration, the bounded hierarchy feature, tmux dashboards/sidebar, the spec-authoring sibling, governed analytical exports, host-routing enforcement, and evidence-informed routing are not prerequisites for the first public CLI preview. They must remain separately gated and may not bypass the hardening sequence.

`MCP-003` now waits on HARD-007; HARD-004 and HARD-005 are accepted. The existing prompt pack remains separate so authenticated mutation cannot be smuggled into read-only MCP work.

## Release gate

REL-004 runs only after every prerequisite is accepted. The technical lane writes structured evidence on success and failure:

```bash
AGENT_WORKFLOW_RELEASE_EVIDENCE_DIR=build/release-evidence \
  ./scripts/release-check.sh
python -m build
```

Pass the wheel and source distribution into provenance, then enforce every declared blocker:

```bash
AGENT_WORKFLOW_RELEASE_ARTIFACTS='dist/agent_workflow.whl:dist/agent_workflow.tar.gz' \
AGENT_WORKFLOW_ENFORCE_RELEASE_BLOCKERS=1 \
  ./scripts/release-check.sh
```

REL-005 is implemented: the gate emits JUnit XML, a CycloneDX SBOM, source/build provenance, direct-lock and policy digests, and machine-readable release evidence. The current policy intentionally keeps REL-001, REL-002, and REL-003 open. Full transitive locking with vulnerability audit, independent reproducibility, and authenticated signing/attestation remain HARD-010.

Before a public preview, complete the active P0 controls in the canonical [BACKLOG.md](BACKLOG.md) and the detailed [determinism/security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#6-prioritized-change-plan).

## Documentation policy

Public documentation describes current behavior, supported boundaries, and active plans. Historical blocker inventories, implementation plans, completion receipts, session checkpoints, changed-file ledgers, and cleanup reports belong in Git history or release attachments—not as executable-looking current guidance.
