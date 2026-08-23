# Execution Protocol

## 1. Source-of-truth hierarchy

Use this order when sources disagree:

1. current checked-out source and public argument parsers;
2. current schemas, migrations, package metadata, and sealed evidence contracts;
3. installed-product acceptance journeys and focused security/state invariants;
4. verified review findings and source excerpts;
5. current README, man pages, skills, and prompt-pack guidance;
6. historical plans and progress notes.

Never implement a historical “completed” claim without confirming that the behavior exists on the checked-out revision. Mutable status projections and terminal text are not authorities when a journal, contract, or receipt exists.

## 2. Required preflight for every ticket

For a new agent worktree, perform the repository procedure in
`docs/references/WORKTREE_PREFLIGHT.md` before structural code discovery or
editing. Generate and verify a full index
for the exact worktree, record its identity and counts, and refresh it before
the completion handoff. This is an agent/operator procedure; codebase-memory
MCP remains optional to the application runtime.

Record:

```bash
pwd
git status --short
git rev-parse --show-toplevel
git rev-parse HEAD
git branch --show-current
python3 --version
```

For a multi-repository workspace, record the same data for every repository touched. Inspect every path named by the ticket before editing it. If a path moved, locate the current equivalent and record the mapping; do not recreate removed files merely to match an old prompt.

Before launching any repository-owned prompt pack, run the release drift audit and validate the pack:

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate /path/to/prompt-pack
```

## 3. Drift and collision handling

- If source matches the reviewed shape, implement the ticket.
- If source already contains a correct implementation, verify it and limit work to missing acceptance evidence.
- If source partially changed, adapt narrowly and document the delta.
- If the ticket would overwrite newer architecture, schema, migration, backlog ownership, or another active prompt pack, stop and escalate.
- Never broaden writable paths or task ownership without explicit authorization.
- Every repository-owned implementation ticket declares one canonical `backlog_id`. Review/gate tasks declare `task_type: gate` and do not claim backlog ownership.
- Use the `release-drift-auditor` skill at every phase gate and before packaging.

## 4. New-terminal and observability rule

Every delegation runs in a fresh named `tmux` session. The session name includes project/pack, phase, and ticket identity. The session must be foregroundable and must write a live persistent log.

A delegation is only **potentially** stalled when its terminal is alive and the live log has not changed for the configured interval. Foreground and inspect before interrupting it. Never automatically kill a session merely because a timer elapsed.

### Launch-mode rule

Implementation work starts interactive unless the operator explicitly chooses a
structured non-interactive fallback. Exploration, research, and review work is
non-interactive by default. At the configured pane limit, report the capacity
and idle candidates, then offer close-idle, structured non-interactive, or
cancel. Do not silently change the launch mode. A structured provider stream is
required for post-run evaluation; native TUI output is operational context only.

## 5. Implementation discipline

- Read before editing.
- Make the smallest coherent change.
- Prefer deterministic enforcement over adding more prompt guidance.
- Prefer removing a contradictory authorized surface over adding compatibility indirection.
- Do not add a framework, service, database, UI, worker, or build system unless the ticket requires it.
- Do not rename public interfaces outside ticket scope.
- Do not silently change storage formats.
- Use synthetic data and reserved domains such as `example.test`.
- Do not perform live collection unless a separately marked live test explicitly requires it.
- Preserve the distinction between nondeterministic producers and deterministic authority: agents may propose work, but code and authenticated human decisions control authoritative state.

## 6. Test discipline

Start with the intended installed-product outcome or future acceptance journey. Prefer, in order:

1. one black-box acceptance journey through the installed executable for a supported capability;
2. one compact parameterized invariant matrix for a security, replay, accounting, or path boundary that cannot be covered exhaustively through the public journey;
3. an opt-in live compatibility journey for real tmux/provider/MCP behavior;
4. a narrowly matched strict future xfail tied to one approved backlog item.

A supported capability should normally have one assertion-dense installed journey that reuses a single lifecycle to verify related commands, durable artifacts, state transitions, and cleanup. Extend that journey instead of adding one test per command, module, or helper. Keep destructive, tamper, race, and invalid-input permutations in a compact invariant matrix when folding them into the live journey would make execution order-dependent or obscure the failing authority.

Do not add tests for line coverage, private parser shape, mock-call choreography, exact internal dictionaries, duplicated CLI help, prose wording, user-created local files, or broad snapshots. A low-level test must state why an end-to-end journey cannot protect the same boundary efficiently.

## 7. Completion evidence

Use `templates/TICKET_COMPLETION.md`. Claims without command output and exit status are not verified. Failed and skipped commands remain visible. Preserve unresolved contradictions rather than inventing certainty.

Completion evidence must identify:

- the backlog item and prompt-pack ticket;
- changed paths and explicit non-targets;
- installed-product acceptance journeys added or updated;
- invariant matrices retained and why they are necessary;
- security boundaries changed;
- documentation, diagrams, schemas, help, man pages, skills, and manifests reviewed for drift.

## 8. Reviewer protocol

The reviewer must inspect the complete diff, enforce writable scope, reject unrelated cleanup, independently rerun the smallest gates, inspect migration and secret handling manually, confirm tests map to real user outcomes, and merge only after dependencies are satisfied.

The reviewer must also run the `release-drift-auditor` skill and reject:

- duplicate or unowned backlog IDs;
- active prompt packs claiming the same work;
- completed or blocked work described as executable;
- docs, diagrams, help, man pages, skills, schemas, tests, and release metadata that disagree with code;
- new prompt-only policies that should be deterministic controls.
