# Migrating Existing Workflow Assets

The original durable set consisted of:

```text
scripts/
templates/
EXECUTION_PROTOCOL.md
DELEGATION_RUNBOOK.md
```

This repository incorporates and supersedes those assets.

## Procedure

1. Extract this repository into its permanent source location.
2. Compare any local edits to the versions here.
3. Preserve project-specific edits inside the relevant project prompt pack.
4. Install this repository with `./install.sh`.
5. Stop copying the old scripts independently; use this CLI or its compatibility wrappers.
6. Keep project-specific phases, tickets, source excerpts, and code outlines out of the global repository.

## Ownership after migration

- lifecycle behavior: `src/agent_workflow/`;
- human policy: root protocol/runbook and `docs/`;
- reusable forms: `templates/`;
- agent-discoverable instructions: `skills/`;
- old helper names: thin wrappers under `scripts/`.
