# Execution Protocol

## 1. Source-of-truth hierarchy

Use this order when sources disagree:

1. current checked-out source and argument parsers;
2. current schemas, migrations, and package metadata;
3. tests that exercise current runtime behavior;
4. verified review findings and source excerpts;
5. current README, man page, and skill claims;
6. historical plans and progress notes.

Never implement a historical “completed” claim without confirming that the behavior exists on the checked-out revision.

## 2. Required preflight for every ticket

Record:

```bash
pwd
git status --short
git rev-parse --show-toplevel
git rev-parse HEAD
git branch --show-current
python3 --version
```

For a multi-repository workspace, record the same data for every repository touched. Inspect every path named by the ticket before editing it. If a path has moved, locate the current equivalent and record the mapping; do not recreate removed files merely to match an old prompt.

## 3. Drift handling

- If the source matches the reviewed shape, implement the ticket.
- If the source already contains a correct implementation, verify it and limit work to missing acceptance gates.
- If the source partially changed, adapt narrowly and document the delta.
- If the ticket would overwrite newer architecture, schema, or migration work, stop and escalate.
- Never broaden writable paths without explicit authorization.

## 4. New-terminal and observability rule

Every delegation runs in a fresh named `tmux` session. The session name includes project/pack, phase, and ticket identity. The session must be foregroundable and must write a live persistent log.

A delegation is only **potentially** stalled when its terminal is alive and the live log has not changed for the configured interval. Foreground and inspect before interrupting it. Never automatically kill a session merely because a timer elapsed.

## 5. Implementation discipline

- Read before editing.
- Make the smallest coherent change.
- Prefer removing a contradictory authorized surface over adding compatibility indirection.
- Do not add a framework, service, database, UI, worker, or build system unless the ticket requires it.
- Do not rename public interfaces outside ticket scope.
- Do not silently change storage formats.
- Use synthetic data and reserved domains such as `example.test`.
- Do not perform live collection unless a separately marked live test explicitly requires it.

## 6. Test discipline

Before writing a test, state the failure or contract it protects. Prefer:

1. pure unit tests for normalization, validation, and migration helpers;
2. contract tests for machine-readable interfaces;
3. one integration test for a complete seam;
4. opt-in live tests under an explicit marker, never as a normal phase exit dependency.

Do not add tests for line coverage, repeat equivalent CLI-help tests, inspect user-created local databases, depend on absolute home paths, or snapshot broad output when a semantic assertion is sufficient.

## 7. Completion evidence

Use `templates/TICKET_COMPLETION.md`. Claims without command output and exit status are not verified. Failed and skipped commands remain visible. Preserve unresolved contradictions rather than inventing certainty.

## 8. Reviewer protocol

The reviewer must inspect the complete diff, enforce writable scope, reject unrelated cleanup, independently rerun the smallest gates, inspect migration and secret handling manually, confirm tests map to acceptance criteria, and merge only after dependencies are satisfied.
