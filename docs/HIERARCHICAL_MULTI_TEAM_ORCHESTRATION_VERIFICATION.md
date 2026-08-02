# Historical hierarchical design-overlay verification

- **Date:** 2026-07-30
- **Baseline:** `agent-workflow-0.3.0-e9e5b95-source.tar.gz`
- **Scope:** historical corrected design-only overlay; superseded for current implementation status by `docs/BACKLOG.md` and `HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_PACKAGE.md`

## Corrections made

1. Renamed the hierarchy decision from colliding `DEC-002` to unique `DEC-005`; the existing `DEC-002` benchmark-policy backlog item remains unchanged.
2. Added an explicit dependency-order section to `docs/BACKLOG.md`, including the critical path, external acceptance gates, and optional terminal-adapter branch.
3. Replaced the non-schema `depends_on` keys in all new task manifests with the supported `dependencies` field and added cross-phase gate edges.
4. Split Phase 1 review into the core topology gate (`HIER-GATE-1`) and optional external-terminal gate (`HIER-GATE-1A`), so `HIER-004` no longer blocks `HIER-005`.
5. Added the new prompt pack to `docs/PROMPT_PACKS.md`, which is required by the repository release drift audit.
6. Added explicit dependencies and execution lanes to every implementation and gate ticket.
7. Corrected the canonical decisions table to use a consistent five-column layout and linked `DEC-005` to its decision record.

## Verification matrix

| Check | Result |
|---|---|
| Hierarchy decision ID is unique and all hierarchy links use `DEC-005` | PASS |
| Existing benchmark-policy `DEC-002` remains unchanged | PASS |
| No hierarchy manifest uses unsupported `depends_on` | PASS |
| Prompt-pack DAG is acyclic and validates | PASS — 4 phases, 13 tasks |
| Optional terminal branch does not gate `HIER-005` | PASS |
| Repository release-asset audit passes | PASS |
| Focused source-level invariant suite | PASS — 77 tests |
| Complete pytest suite | ENVIRONMENT-BLOCKED — see below |
| Repository payload contains only files changed or added relative to the supplied baseline | PASS |
| Apply script works on both clean source and a tree containing the prior overlay | PASS |

## Commands and results

### Prompt-pack validation

```text
PYTHONPATH=src python -m agent_workflow pack validate \
  prompt-packs/hierarchical-multi-team-orchestration
```

Result:

```text
pack: .../prompt-packs/hierarchical-multi-team-orchestration
phases: 4; tasks: 13; valid: True
```

### Release-asset audit

```text
PYTHONPATH=src python scripts/audit-release-assets.py
```

Result:

```text
release assets: valid
```

### Focused invariant suite

```text
PYTHONPATH=src pytest -q tests/invariants \
  --ignore=tests/invariants/test_orchestrator_inbox.py \
  --ignore=tests/invariants/test_release_evidence.py
```

Result:

```text
77 passed
```

### Complete-suite attempt

The complete suite was attempted. It could not provide a meaningful repository certification in this execution environment because:

- the configured package mirror does not provide the pinned `mcp==1.28.1` dependency required by the installed-product fixture;
- `tmux` is not installed, blocking tmux-dependent inbox and live-product tests;
- the supplied source archive intentionally contains no `.git` metadata, blocking tests that require `git rev-parse HEAD`.

The partial run reached `89 passed, 5 xfailed` before those environment prerequisites produced collection/setup errors and three environment-dependent failures. No failure was caused by the overlay's Markdown, YAML, manifest DAG, decision records, or release-asset integration.

### Overlay application verification

The packaged `APPLY_OVERLAY.sh` was executed against:

1. a clean copy of the supplied source baseline; and
2. a copy with the earlier hierarchy overlay already applied.

In both cases the script removed `docs/DECISIONS/DEC-002-HIERARCHICAL-ORCHESTRATION.md` when present, installed the corrected `DEC-005` record, and then passed prompt-pack validation and the release-asset audit. The package-level `MANIFEST.sha256` also verified every staged file.

## Dependency graph verified

```text
DEC-005
  → HIER-001 → HIER-002 → HIER-GATE-0
  → HIER-003 → HIER-GATE-1
  → HIER-005 → HIER-006 → HIER-GATE-2
  → HIER-007 → HIER-008 → HIER-GATE-3

External accepted gates:
  PROC-006 before HIER-003
  MSG-001 + PROC-001 + PROC-002 before HIER-005
  BKL-002 before HIER-006

Optional branch:
  HIER-003 → HIER-004 → HIER-GATE-1A
```

The optional branch has no dependency edge into `HIER-005` or any later core-path task.
