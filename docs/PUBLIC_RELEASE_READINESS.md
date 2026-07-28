# Public release readiness

The repository is moving toward a public release, but it is not ready to publish as a supported open-source project. This document distinguishes product readiness from repository polish so the project does not accumulate release-shaped artifacts without resolving actual blockers.

The detailed findings are in [Feature determinism and security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md). Canonical task state remains in [BACKLOG.md](BACKLOG.md), with sequencing in [Determinism and security hardening plan](DETERMINISM_SECURITY_HARDENING_PLAN.md).

## Current strengths

- installed-wheel acceptance tests exercise primary CLI and workflow journeys;
- security, replay, and provider-accounting invariants are compact and explicit;
- deterministic archives, packaged schemas, release manifests, and install/uninstall paths exist;
- architecture, operations, security, testing, prompt-pack, evaluation, MCP, and command documentation are consolidated;
- active prompt-pack ownership is explicit and release-audited;
- CI configuration exists for supported Python versions;
- completed prompt packs, ticket ledgers, and one-off audit reports are removed from the public source surface.

The local Jenkins pipeline is currently operational: build #23 on `master` at `5de662c` passed the installed-product suite, release checks, wheel build, and global wheel install. This is development-host CI evidence only; it does not establish public support or clean-host compatibility.

## Technical blockers before a public preview

| Priority | Blocker | Canonical task | Exit evidence |
|---|---|---|---|
| P0 | Bounded process execution | HARD-001 | Uniform timeout, process-group cancellation, output caps/spooling, environment policy, executable evidence, and redaction across owned call sites |
| P0 | Artifact/path/schema integrity | HARD-002 | No symlink/special-file ambiguity, content-complete pack archives, no-follow native/MCP paths, unique authoritative schema IDs |
| P0 | Preventative execution isolation | HARD-003 | Native/evaluation commands cannot write/read/connect outside policy and fail closed without a supported backend |
| P0 | Immutable launch/receipt authority | HARD-004 | Runners and evaluators consume immutable contracts/verified digests, never mutable status as authority |
| P0 | MCP read privacy/path safety | HARD-005 | Metadata-minimal default responses, stable no-follow reads, bounded outputs, opaque errors |
| P1 | Sensitive-content handling | HARD-006 | Classification, redaction, opt-in disclosure, and retention/deletion evidence |
| P1 | Authenticated review identity | HARD-007 | Principal evidence and enforceable independent-review policy |
| P1 | Config/executor trust | HARD-008 | Ownership/mode checks, executable identity, compatibility policy, sanitized host environment |
| P1 | Generated drift gate | HARD-009 | Commands/schemas/services/packs/docs/skills/diagrams/future tests remain source-derived and collision-free |
| P1 | Supply-chain integrity | HARD-010 | Locks, SBOM, provenance, reproducible artifacts, and authenticated signing/attestation |

## Governance and compatibility blockers

| Priority | Blocker | Canonical task | Exit evidence |
|---|---|---|---|
| P0 | Select and add an open-source license | REL-001 | Maintainer-approved `LICENSE` and matching package metadata/distribution policy |
| P0 | Establish vulnerability reporting | REL-002 | Real monitored contact or private reporting mechanism in `SECURITY.md` |
| P0 | Supported host/executor matrix | REL-003 | Approved Linux/Python/tmux/executor versions and clean-host live compatibility evidence |
| P1 | Public-preview decision | REL-004 | Independent clean-artifact gate with explicit go/no-go, supported boundary, signatures, and rollback/advisory ownership |

Until P0 technical and governance blockers are closed, use source archives with trusted collaborators rather than describing the project as a supported public release.

## Non-blocking future work

The state-mutating MCP phase, remote transport, multi-host orchestration, host routing enforcement, reconstructable indexes, and evidence-informed routing are not prerequisites for the first public CLI preview. They retain their existing MCP/BKL/DEC/ARC/WF backlog ownership and must not be duplicated by hardening packs.

`MCP-003` is specifically blocked on HARD-004, HARD-005, and HARD-007. Its existing prompt pack remains separate so security foundations cannot be bypassed by execution order.

## Release gate

REL-004 runs only after all prerequisites are accepted. The technical lane writes structured evidence on both success and failure:

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

REL-005 is implemented: the gate emits JUnit XML, a CycloneDX 1.5 SBOM, source/build provenance, direct-lock and policy digests, and a machine-readable `release-evidence.json`. The current policy intentionally reports REL-001, REL-002, and REL-003 as blocked. See [Release evidence](RELEASE_EVIDENCE.md).

The Jenkins local job must also complete its build, test, wheel, and local-install stages. Run the opt-in live compatibility lane on every combination that will be marked supported and bind those results into the release policy. CI success alone is not provider compatibility or release authorization.

Before a public preview, also complete the P0 controls in [RELEASE_BLOCKERS_AUDIT.md](RELEASE_BLOCKERS_AUDIT.md#determinismsecurity-p0-controls) and the detailed [determinism/security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#6-prioritized-change-plan). Full transitive locking with hashes, independent reproducibility, and authenticated signing/attestation remain HARD-010 rather than REL-005.

## Documentation policy

Public documentation describes current behavior, supported boundaries, and active plans. Historical implementation plans, completion receipts, session checkpoints, changed-file ledgers, and cleanup reports belong in Git history or release attachments—not as permanent top-level documentation.
