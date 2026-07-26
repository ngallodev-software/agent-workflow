# Public release readiness

The repository is moving toward a public release, but it is not ready to publish as a supported open-source project yet. This document distinguishes product readiness from repository polish so the project does not accumulate release-shaped artifacts without resolving actual blockers.

## Current strengths

- installed-wheel acceptance tests exercise the primary CLI and workflow journeys;
- security, replay, and provider-accounting invariants are compact and explicit;
- deterministic archives, packaged schemas, release manifests, and install/uninstall paths exist;
- architecture, operations, security, testing, prompt-pack, evaluation, MCP, and command documentation are consolidated;
- CI configuration exists for supported Python versions;
- completed prompt packs, ticket ledgers, and one-off audit reports are removed from the public source surface.

The local Jenkins pipeline is currently operational: build #16 on `master` passed the installed-product suite, release checks, wheel build, and local install. This is development-host CI evidence only; it does not establish public support or clean-host compatibility.

## Blocking decisions

| Priority | Blocker | Exit evidence |
|---|---|---|
| P0 | Select and add an open-source license | Maintainer-approved `LICENSE` and matching package metadata |
| P0 | Establish a vulnerability-reporting channel | Real monitored contact or private reporting mechanism in `SECURITY.md` |
| P0 | Decide the first supported host/executor matrix | Recorded Linux/Python/tmux/Codex/Claude versions and successful live compatibility evidence |
| P0 | Define release ownership and signing | Named maintainer process, protected tags, checksums, and release notes |
| P0 | Close deterministic execution/security controls | Bounded subprocesses, preventative execution scope, prompt-pack file-type integrity, MCP privacy/path hardening, and immutable launch authority |
| P1 | Publish package/repository metadata | Final project URLs, license classifier, support policy, and distribution target |
| P1 | Run a clean-machine install/uninstall trial | Evidence from a representative host outside the development checkout |
| P1 | Run a real workflow/provider cohort | Sealed, reviewable evidence with no unsupported performance claims |
| P1 | Verify local Jenkins commit triggering | A commit to the local repository causes a build of the matching master revision; manual build success alone is insufficient |

Until the P0 blockers are closed, use source archives with trusted collaborators rather than describing the project as a supported public release.

## Non-blocking future work

The state-mutating MCP phase, remote transport, multi-host orchestration, and host routing enforcement are not prerequisites for the first public CLI release. They must not delay a focused release or be pulled in merely to appear complete.

## Release gate

A release candidate should pass:

```bash
pytest
./scripts/release-check.sh
python -m build
```

The Jenkins local job must also complete its build, test, wheel, and local-install stages. In addition, run the opt-in live compatibility lane on each declared supported host/executor combination and review the resulting sealed evidence. CI success alone is not sufficient for provider compatibility.

The release-check audit currently identifies missing automated gates for license metadata, a real vulnerability channel, the declared compatibility matrix, structured test evidence, and authenticated release provenance. Track those as REL-005 rather than treating the default script as a complete public-release gate.

Before a public preview, also complete the P0 controls in [RELEASE_BLOCKERS_AUDIT.md](RELEASE_BLOCKERS_AUDIT.md#determinismsecurity-p0-controls) and the detailed [determinism/security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#6-prioritized-change-plan).

## Documentation policy

Public documentation describes current behavior, supported boundaries, and active plans. Historical implementation plans, completion receipts, session checkpoints, changed-file ledgers, and cleanup reports belong in Git history or release attachments—not as permanent top-level documentation.
