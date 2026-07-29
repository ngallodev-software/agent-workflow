# PROC-007 — exact-root source snapshot reliability

## Objective

Diagnose and fix the observed divergence where native `git status --porcelain`
reports a clean repository while `agent-workflow worktree create` rejects the
same exact root as dirty. Preserve fail-closed behavior for actual changes.

## Required preflight

Perform `docs/references/WORKTREE_PREFLIGHT.md`. Inspect `git.py`, process
execution helpers, worktree creation, launch source snapshots, configuration,
and existing clean/dirty tests before editing. Reproduce the discrepancy or
record an exact environment limitation with executable paths, argv, cwd, exit
status, bounded output digest, and relevant Git environment variables.

## Writable scope

`src/agent_workflow/git.py`, process/config helpers only where needed,
`src/agent_workflow/worktrees.py`, launch provenance schemas if additive
evidence is needed, focused acceptance/invariant tests, and command/operations
documentation. Do not relax `--allow-dirty`, change agent lifecycle authority,
or modify MSG/PROC-006 behavior.

## Required behavior

- Cleanliness comes from a newly executed `git -C <canonical-root> status
  --porcelain` call, not from status projections, prior observations, or a
  different checkout.
- Record enough bounded provenance to diagnose which Git executable, argv,
  root, exit state, and output digest determined the decision; do not expose
  unbounded filenames or sensitive environment content.
- A clean exact root creates a worktree without `--allow-dirty`; a changed or
  untracked root is rejected without the override.
- On command disagreement or ambiguous repository identity, fail closed with a
  diagnostic that distinguishes fresh command failure from dirty evidence.
- Add an installed-product journey covering clean creation, tracked change,
  untracked file, and controlled executable/environment divergence.

## Stop conditions

Stop and report rather than weakening the gate if the discrepancy depends on
an external Git wrapper, host policy, or environment variable that cannot be
captured safely; if canonical-root identity is ambiguous; or if the proposed
fix would cache a cleanliness decision, suppress a real dirty result, or expose
unbounded working-tree paths.

## Validation and handoff

Run focused installed/invariant tests, package validation, release audit, and
the relevant full suite. Use `templates/TICKET_COMPLETION.md`, preserve exact
commands and exit codes, commit only scoped changes, and produce sealed
completion evidence. Do not update `docs/BACKLOG.md` from the child.
