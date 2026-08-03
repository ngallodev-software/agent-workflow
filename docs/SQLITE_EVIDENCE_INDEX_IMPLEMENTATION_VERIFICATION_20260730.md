# SQLite evidence index implementation and verification

Date: 2026-07-30  
Baseline: `agent-workflow-0.3.0-e9e5b95` plus the cumulative hierarchical, blocker-reduction, and self-healing work  
Decision: [`DEC-007`](DECISIONS/DEC-007-REBUILDABLE-SQLITE-PROJECTION.md)

## Outcome

The repository now has a host-local SQLite operational projection for searchable cross-run evidence. JSON, JSONL, immutable workflow snapshots, and sealed receipts remain authoritative. The database can be deleted and reconstructed; it cannot authorize execution, lifecycle, permission, remediation, review, acceptance, merge, or deletion decisions.

Implemented backlog scope:

- `IDX-001`: schema, migrations, ownership, locking, and provenance — **implemented, in review**;
- `IDX-002`: deterministic rebuild and incremental reconciliation — **implemented, in review**;
- `IDX-003`: normalized operational projections and curated views — **implemented, in review**;
- `IDX-004`: public CLI, help, man pages, README, and operator documentation — **implemented, in review**;
- `IDX-005`: foreground-supervisor and archive integration — **implemented, in review**;
- `IDX-006`: policy-governed analytical export — **blocked and sequenced**;
- `IDX-007`: measured-scale checkpoints and capacity proof — **blocked and sequenced**.

The in-review state is intentional. Independent prompt-pack gates, live compatibility evidence, privacy/retention policy, and measured-scale proof remain separate acceptance requirements.

## Authority and storage boundary

Authoritative evidence remains under:

```text
$XDG_STATE_HOME/agent-workflow/runs/<session-id>/
$XDG_STATE_HOME/agent-workflow/archive/<session-id>/
```

The disposable projection is:

```text
$XDG_STATE_HOME/agent-workflow/index/agent-workflow.sqlite3
```

Controls include:

- SQLite application ID `AWF1` and schema version validation;
- refusal of foreign, unowned, newer, symlinked, or irregular database paths;
- owner-only index directory, database, WAL, shared-memory, and lock files;
- one exclusive indexer writer lock;
- WAL mode, `synchronous=FULL`, foreign keys, and bounded busy timeout;
- read-only URI connections for queries and verification;
- fixed parameterized query templates; no arbitrary SQL surface;
- no-follow regular-file source reads;
- shared locks for append-only JSONL reads;
- known contract-schema validation;
- per-file and per-record SHA-256 provenance;
- per-run transactional replacement;
- corrupt-run quarantine without rolling back healthy runs;
- full source-digest verification on demand.

## Implemented data model

The projection contains:

- runs and source files;
- generic structured events;
- health samples;
- permission, incident, and remediation events;
- process results;
- execution metrics;
- workflows, nodes, and edges;
- index metadata, migrations, and errors;
- curated run, incident, permission, and performance views.

The index deliberately excludes raw prompts, output/stderr logs, terminal bodies, message bodies, completion prose, credentials, unrestricted provider payloads, and free-form remediation reasons. Incident summaries are bounded. Remediation reasons are represented by digest only.

Provider-billed and locally estimated costs remain separate. Mixed-currency groups return null averages and null currencies rather than a false combined value.

## Reconciliation behavior

`agent-workflow index rebuild` removes the projection database and its WAL/shared-memory companions, applies the current schema, discovers active and archived runs, validates structured evidence, and rebuilds each run in an independent transaction.

`agent-workflow index sync` computes a per-run change fingerprint from structured paths, size, modification/change times, file identity, and mode metadata. Unchanged current runs are skipped. Changed runs are replaced. Full-scope synchronization prunes projections whose source run no longer exists.

Every query is wrapped in `agent-workflow/index-query/v1`, which exposes:

- database path and authority label;
- `current`, `stale`, or `incomplete` freshness;
- current and stale run counts;
- index error count;
- query kind and rows.

This prevents machine consumers from receiving rows without the projection state needed to interpret them.

## Public product surface

Implemented commands:

```bash
agent-workflow index status
agent-workflow index sync [--run SESSION] [--active-only]
agent-workflow index rebuild [--run SESSION] [--active-only]
agent-workflow index verify [--full] [--review SESSION]
agent-workflow index query runs|incidents|permissions|performance|workflows|workflow-nodes|repairs|errors
```

Curated filters include session, state, category, executor, model, prompt pack, and bounded result count where supported.

The command catalog, root help, subcommand help, README, command reference, operations guide, security guide, testing guide, evidence/evaluation guide, installation guide, architecture, changelog, skills, man pages, release audit, and version-bump script were updated. Scoped review verification reports `review_valid` separately from global `valid`; it fails closed for unsealed or invalid final receipts, missing or invalid direct completion evidence, active or noncanonical runs, and runs without a canonical reviewed lifecycle receipt.

## Supervisor and archive integration

Foreground supervisor cycles synchronize the projection by default. An index failure is reported in the supervisor result but does not suppress health collection, incident detection, or bounded remediation.

Successful archive moves trigger a best-effort index synchronization. Projection failure cannot invalidate or roll back an already-completed authoritative archive operation.

## Verification performed

### Source-level tests

```text
109 passed
12 expected future xfails
```

The expected failures correspond to genuinely open authority, privacy, resource-control, live compatibility, hierarchy, analytical-export, and measured-scale work. They are not regressions hidden as passes.

Focused SQLite, supervisor, and durable-state verification:

```text
19 passed
```

Additional release checks:

```text
3 release-schema/shell/static tests passed
release assets: valid
Python compileall: passed
Markdown relative links: valid across README, docs, and the SQLite prompt pack
All light/dark SVG assets: valid XML and rendered successfully
```

### Prompt-pack validation

Every active prompt pack validated as an acyclic dependency graph. The new SQLite pack reports:

```text
phases: 4
tasks: 11
valid: True
```

### Wheel-installed product journey

A wheel was built with no source-tree import path, installed into an isolated target, and exercised through the public CLI. The journey proved:

1. packaged index schemas are installed;
2. full rebuild indexes one active run;
3. status reports `current` and WAL mode;
4. run and incident queries return `agent-workflow/index-query/v1` with source provenance;
5. `verify --full` passes;
6. deleting the database, WAL, and shared-memory files produces `missing` freshness;
7. rebuilding restores the same authoritative query fields and event provenance;
8. only the operational `indexed_at` timestamp changes, as designed.

Result:

```text
installed-wheel rebuild/query/delete/rebuild journey: PASS
```

### Security and failure tests

Coverage includes:

- foreign application-ID refusal;
- newer-schema refusal;
- database symlink and broken-symlink refusal;
- source evidence unchanged after database rejection;
- corrupt-run quarantine while healthy runs remain queryable;
- terminal-content and remediation-reason exclusion from the database;
- same-size/same-mtime content change detection;
- stale query-envelope reporting;
- source digest mismatch detection;
- active-to-archive location reconciliation;
- provider/local cost separation and mixed-currency nulling;
- workflow-node and edge materialization;
- public help/query/status/rebuild/verify behavior.

## Environment limitations

The configured package mirror does not provide the repository-pinned `mcp==1.28.1` dependency. The repository's shared installed-product pytest fixture therefore cannot be completed in this container because it intentionally fails before test execution when that exact distribution is absent.

The SQLite wheel journey was run independently using the built wheel and the available base `jsonschema` dependency; it did not import from the source checkout. This verifies the SQLite installed surface but does not substitute for the full MCP-inclusive acceptance suite.

A live supported tmux/executor/host matrix is also unavailable here. No claim is made that `REL-003`, live hierarchy recovery, authenticated authority, policy-governed export, or measured scale has been accepted.

## Remaining work and sequencing

The canonical backlog and [`sqlite-evidence-index`](../prompt-packs/sqlite-evidence-index/) pack own the remaining work:

```text
DEC-007 → IDX-001 → {IDX-002 ∥ IDX-003} → IDX-GATE-0
                                           ↓
                          {IDX-004 ∥ IDX-005} → IDX-GATE-1
                                                   ↓
       [HARD-006 + SUP-003 + BKL-004] → IDX-006 → IDX-GATE-2
                                                   ↓
                             [measured scale] → IDX-007 → IDX-GATE-3
```

No Parquet/DuckDB export or byte-offset checkpoint optimization should be added before its stated governance or measured-need gate. Full reconstruction from source evidence remains mandatory in every future design.

## Cumulative overlay verification

The v5 deliverable is cumulative against the untouched `0.3.0-e9e5b95` source and includes the earlier hierarchy, blocker-reduction, README, and self-healing work.

Overlay checks performed:

- 189 exact repository payload paths;
- two explicit superseded-file deletions;
- transfer manifest verified before application;
- successful application to the untouched source;
- successful application to the prior v4 tree;
- successful repeat application to prove idempotence;
- stale hierarchy decision cleanup verified;
- byte-for-byte and mode-for-mode comparison of all 189 payload paths in both applied trees.

The untouched-source applied tree independently passed:

```text
109 source invariant/future tests passed
12 expected future xfails
3 release schema/shell/static checks passed
release assets: valid
all active prompt-pack DAGs: valid
all checked Markdown relative links: valid
all SVG assets: valid XML
Python compileall: passed
```

A wheel was then built from the applied tree, installed outside the source checkout, and reran the delete/rebuild/query/full-verification journey successfully:

```text
applied-tree wheel-installed delete/rebuild/query/verify journey: PASS
wheel SHA-256: ddc380630b92ff2e3f6443f401526e3fdc25e47ac7f4b5c7d108806fbd2781d3
```
