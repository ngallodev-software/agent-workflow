# release-installers

## Purpose

Maintain the immutable-tag bootstrap, deterministic Linux/WSL2/macOS runtime bundles, checksum verification, uninstall behavior, and independent installer gate owned by `REL-008`.

The implementation exists and is in review. New work is limited to verified defects, tagged-release evidence, and boundary enforcement.

## Distribution boundary

- Base installation contains the CLI, libraries, schemas, man pages, skills, and selected runtime assets.
- MCP is an optional `mcp` install profile and is registered only when requested.
- `Jenkinsfile`, `scripts/jenkins-local-job.sh`, `scripts/jenkins-local-job.xml`, and `.github/workflows/` are core repository CI/CD source but must not be copied into wheels or runtime bundles.
- Native Windows remains out of scope; WSL2 uses the Linux runtime contract.

## Phase map

| Phase | Objective | Complexity | Exit dependency |
|---|---|---|---|
| 0 | Verify/fix REL-008 installers and artifact boundaries | High | Integrated source and release metadata |
| 1 | Independently rerun installer and inventory gates | Review | Accepted REL-008 evidence |

## Universal delegation rules

- Execute every ticket in a fresh named terminal session and isolated worktree unless review-only.
- Use current source and release metadata as authority; do not recreate superseded installer designs.
- Preserve immutable version selection and fail-closed checksum behavior.
- Inspect wheel and runtime-bundle inventories, not only installer output.
- Produce a ticket completion report and preserve command output.

## How to execute

See `EXECUTION_PROTOCOL.md`, `DELEGATION_RUNBOOK.md`, and each phase README.
