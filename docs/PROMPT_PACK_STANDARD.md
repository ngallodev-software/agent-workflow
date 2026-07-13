# Prompt-Pack Standard

A prompt pack is a self-contained implementation plan intended to remain usable when delegated to smaller models.

## Required root files

```text
README.md
EXECUTION_PROTOCOL.md
DELEGATION_RUNBOOK.md
templates/TICKET_COMPLETION.md
templates/PHASE_GATE_REPORT.md
templates/source-baseline.example.json
```

## Required phase structure

```text
phase-N/
├── README.md
├── MASTER_IMPLEMENTATION_PROMPT.md
├── task-manifest.yaml
└── tickets/
    └── PN-XX-description.md
```

## Ticket minimum

Every implementation ticket states:

- objective and non-goals;
- recommended model/delegation tier;
- dependencies;
- required reading and current paths;
- writable paths;
- implementation procedure;
- code structure or interface outline where useful;
- acceptance criteria;
- necessary tests and explicitly unnecessary tests;
- stop/escalation conditions;
- completion-report requirements.

## Reference requirements

References should contain current revisions, verified source excerpts, authority/ownership boundaries, code shapes, compatibility decisions, and test policy. Smaller models must not be asked to infer architecture that the pack author could have specified.

## Portable versus installed operation

Packs may vendor compatibility scripts so the archive is self-contained. The global `agent-workflow` CLI is authoritative when installed. Vendored scripts should be generated or copied from a named workflow release, not edited independently.

## Integrity

`MANIFEST.sha256` covers every regular file except itself. The outer archive receives `<archive>.sha256`. Archive creation sorts paths, fixes timestamps, and normalizes ownership to reduce nondeterminism.
