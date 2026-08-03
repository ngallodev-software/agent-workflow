# Delegation runbook

This pack is primarily an operator/evidence workflow. Parallel work is allowed only where it cannot share benchmark runs, tmux windows, ports, review identities, or evidence paths.

## Roles

- **Host operator:** owns tmux, provider authentication, run launch, process intervention, and raw host evidence.
- **Evidence collector:** runs monitoring scripts, hashes files, and completes machine-readable check records without changing implementation.
- **Browser reviewer:** performs blinded live-application review without private mappings.
- **Repair implementer:** works only after a preserved failure identifies an implementation defect.
- **Independent gate reviewer:** inspects complete evidence and diff; does not implement repairs in the gate worktree.

The same person may be host operator and evidence collector. The final gate reviewer must be independent of any repair implementation and must not score a blinded UI after viewing its treatment mapping.

## Worktree and session isolation

- Use one source worktree for any repair.
- Use separate disposable benchmark fixture/worktree roots per run ID.
- Use a separate tmux window or session for each provider run; never run two benchmark coordinators in the same invoking window concurrently.
- Use unique reviewer IDs and evidence directories.
- Never reuse a failed pair's worktrees.

## Checkpoints

After each ticket, write a task result conforming to `contracts/task-result.schema.json`. A phase gate may proceed only when all dependencies are accepted or explicitly blocked by an external prerequisite.

## Repair escalation

A review task may not silently become implementation work. Preserve the failure, record a defect, open a narrow repair worktree, implement/test, then return to a fresh review run. The final gate reviews both the defect and repair lineage.
