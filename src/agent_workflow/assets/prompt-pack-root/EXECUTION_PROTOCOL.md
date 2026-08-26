# Execution Protocol

## 1. Source-of-truth hierarchy

Use this order when sources disagree:

1. current checked-out source and public argument parsers;
2. current schemas, package metadata, and sealed evidence contracts;
3. installed-product acceptance journeys and focused security/state invariants;
4. verified review findings and source excerpts;
5. current README, man pages, skills, and prompt-pack guidance;
6. historical plans and progress notes.

Mutable runtime observations are not authorities when a durable journal, contract, or receipt exists.

## 2. Required preflight for every ticket

Apply `docs/references/WORKTREE_PREFLIGHT.md` to the exact Agent Run worktree before editing. Record repository identity, baseline revision, and porcelain state. Agent-Workflow owns the worktree/source baseline for the run.

Before launching a repository-owned prompt pack:

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate /path/to/prompt-pack
```

## 3. Drift and collision handling

- If source matches the reviewed shape, implement the ticket.
- If source already contains a correct implementation, verify it and limit work to missing acceptance evidence.
- If source partially changed, adapt narrowly and document the delta.
- If the ticket would overwrite newer architecture, schema, backlog ownership, or another active prompt pack, stop and escalate.
- Never broaden writable paths or task ownership without explicit authorization.
- Every active implementation ticket declares one canonical `backlog_id` in root `pack.yaml`; the root `backlog_items` list must match the implementation tickets owned by the pack.

## 4. Agent Run and worker rule

Every delegation is represented by an Agent Run with a durable execution contract. A worker is an execution actor attached to that Agent Run; it is never identified by a terminal, pane, or UI object.

Agent-Workflow supports two execution modes:

- `headless`: Agent-Workflow starts and owns the worker process group;
- `external`: Agent-Workflow prepares the Agent Run and an external host starts/presents the worker.

A host may provide live interaction, but host state does not determine durable completion, acknowledgement, review, or acceptance.

## 5. Messaging rule

Workflow communication is persist-first:

1. persist the message in Agent-Workflow;
2. optionally attempt immediate external-host delivery;
3. require the worker to record acknowledgement separately.

A successful live prompt delivery is not an acknowledgement.

## 6. Implementation discipline

- Read before editing.
- Make the smallest coherent change.
- Prefer deterministic enforcement over adding prompt guidance.
- Prefer removing contradictory authorized surfaces over compatibility indirection.
- Do not add a framework, service, database, UI, worker, or build system unless the ticket requires it.
- Do not silently change storage formats outside approved scope.
- Preserve the distinction between nondeterministic producers and deterministic authority.

## 7. Test discipline

Prefer, in order:

1. one black-box acceptance journey through the installed executable for a supported capability;
2. one compact parameterized invariant matrix for a security, replay, accounting, or path boundary that cannot be covered efficiently through the public journey;
3. an opt-in provider/MCP integration journey where external dependencies are genuinely required;
4. a narrowly matched strict future xfail tied to one approved backlog item.

Do not add tests for line coverage, private parser shape, mock-call choreography, duplicated CLI help, prose wording, or broad snapshots. A low-level test must state why an end-to-end journey cannot protect the same boundary efficiently.

## 8. Completion evidence

Use `templates/TICKET_COMPLETION.md`. Claims without command output and exit status are not verified. Failed and skipped commands remain visible. Preserve unresolved contradictions rather than inventing certainty.

Completion evidence identifies:

- backlog item and prompt-pack ticket;
- changed paths and explicit non-targets;
- acceptance journeys added or updated;
- invariant matrices retained and why they are necessary;
- security boundaries changed;
- documentation, diagrams, schemas, help, man pages, skills, and manifests reviewed for drift.

## 9. Reviewer protocol

The reviewer inspects the complete diff, enforces writable scope, reruns the smallest relevant gates, verifies evidence and source provenance, confirms tests map to real user outcomes, and records an independent disposition recommendation. Acceptance remains an authoritative workflow action, not a worker self-declaration.
