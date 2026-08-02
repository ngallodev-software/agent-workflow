# REL-INSTALL-GATE-01 — Independent installer gate

## Delegation metadata

- Ticket: `REL-INSTALL-GATE-01`
- Recommended tier: A
- Dependencies: `REL-008`
- New terminal session required: yes
- Implementation risk: review-only

## Objective

Independently review REL-008 without changing implementation scope.

## Required reading

- repository root README and package metadata;
- this phase README and master prompt;
- `EXECUTION_PROTOCOL.md`;
- relevant included references.

## Writable paths

Only the phase completion/evidence directory designated by the operator. Do not modify production source.

## Procedure

1. Verify the sealed REL-008 handoff, complete diff, scope, and release artifacts.
2. Independently rerun the package build, installer unit tests, workflow validation,
   and one isolated installed-product journey.
3. Confirm bootstrap URLs are immutable release/tag URLs, checksum failure is
   fail-closed, and no real release was published by a test.
4. Inspect wheel and each runtime bundle inventory; reject Jenkinsfile, Jenkins server-job scripts/XML, or `.github/workflows/`.
5. Verify the base profile does not require MCP and the MCP profile is explicit.
6. Recommend accept or reject; the host records disposition.

## Acceptance criteria

- all supported platform bundle labels are present;
- unsigned or checksum-mismatched artifacts are rejected;
- workflow publishing is tag-only;
- no scope or trust-boundary drift exists.

## Necessary tests

No new tests. Validate evidence with Git and filesystem commands only.

## Stop and escalate conditions

Stop if the repository or required references cannot be located, the worktree contains unexplained changes, or a later ticket would overwrite clearly newer architecture.

## Required completion report

Use `templates/TICKET_COMPLETION.md` and mark this ticket as read-only.
