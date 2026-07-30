# HIER-GATE-1A — optional external-terminal adapter review

Review only. Verify the configured argv-only adapter, exact tmux target attachment, executable provenance, bounded process evidence, safe failure behavior, and host-specific documentation for `HIER-004`.

## Dependencies and lane

- Depends on `HIER-004`.
- Optional side branch. It does not block `HIER-005` or the core hierarchy path.

## Writable scope

Review reports and evidence artifacts only. Do not implement new behavior or edit the canonical backlog from the gate session.

## Required tests and evidence

Run focused adapter invariants, one opt-in live host journey for the supported adapter, package validation, release asset audit, and documentation/skill drift checks. Record exact argv, executable identity, commands, exit codes, bounded output, and the fallback attach diagnostic.

## Acceptance criteria

Accept only when the external terminal attaches to the exact durable team window, prompt-derived shell input is impossible, terminal closure leaves team state intact, and adapter failure preserves a usable exact attach path.

## Stop conditions

Stop and reject on shell interpolation, untrusted executable selection, positional window targeting, silent fallback, missing host evidence, state rollback after terminal failure, or unresolved release-audit findings.
