# P0-00 — Baseline and preflight

## Delegation metadata

- Ticket: `P0-00`
- Recommended tier: C
- Dependencies: none
- New terminal session required: yes
- Implementation risk: read-only

## Objective

Capture the exact current source baseline and identify material drift from the pack references before implementation begins.

## Required reading

- repository root README and package metadata;
- this phase README and master prompt;
- `EXECUTION_PROTOCOL.md`;
- relevant included references.

## Writable paths

Only the phase completion/evidence directory designated by the operator. Do not modify production source.

## Procedure

1. Record working directory, repository root, branch, revision, and dirty state.
2. Confirm every later ticket path exists or locate its current equivalent.
3. Compare current source with the pack's reviewed baseline.
4. Record contradictions that could invalidate later tickets.
5. Do not solve implementation tickets during this preflight.

## Acceptance criteria

- exact revisions and branches are recorded;
- dirty state is recorded;
- path mappings are explicit;
- blocking source contradictions are visible;
- no production source changed.

## Necessary tests

No new tests. Validate evidence with Git and filesystem commands only.

## Stop and escalate conditions

Stop if the repository or required references cannot be located, the worktree contains unexplained changes, or a later ticket would overwrite clearly newer architecture.

## Required completion report

Use `templates/TICKET_COMPLETION.md` and mark this ticket as read-only.
