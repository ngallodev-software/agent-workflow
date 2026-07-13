# Delegated implementation

Use this skill when executing a bounded implementation ticket from an agent-workflow prompt pack.

## Required behavior

1. Read the ticket, phase README, master prompt, execution protocol, and named references.
2. Verify current source before editing.
3. Stay inside writable paths.
4. Implement the smallest coherent change.
5. Add only tests tied to explicit acceptance criteria or a demonstrated regression.
6. Preserve failed commands and unresolved contradictions in the completion report.
7. Do not merge, broaden scope, or claim phase acceptance.

## Terminal contract

The operator launches each delegation in a fresh foregroundable session. Do not spawn a replacement coding agent inside the ticket session unless the ticket explicitly assigns coordinator behavior.

## Stop conditions

Stop rather than guess when current source would make the ticket destructive, a required dependency is absent, a migration cannot be made recoverable, or secrets/real target data would be exposed.
