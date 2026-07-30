# Backlog blocker reduction — 2026-07-30

## Scope

This pass implemented the highest-value ready work that could be completed
without maintainer policy approval or pretending unsupported external executor
capabilities exist. It does not approve `DEC-005`, authenticate principals for
`HARD-007`, or claim native live Codex/Claude steering support.

## Implemented work

### BKL-002 — cooperative late steering foundation

- Added a typed `control-file-v1` adapter and explicit `unsupported` default.
- Publishes immutable bounded steering requests under the verified run handoff.
- Records append-only `queued`, `delivered`, `applied`, `rejected`,
  `unsupported`, `expired`, and `failed` evidence in
  `steering-delivery.jsonl`.
- Correlates child acknowledgements to the original immutable message ID.
- Prevents terminal acknowledgement replay and prevents a host/runner race from
  appending stale `queued` evidence after delivery.
- Promoted the late-steering specification to an installed-product acceptance
  journey using a deterministic cooperative executor fixture.

Remaining before acceptance: authenticated principal/recipient enforcement
from `HARD-007`, evidence for every real executor adapter claimed as supported,
and the owning phase gate. Unverified modes remain durably unsupported.

### PROC-004 — substantive completion validation

- Added semantic validation after JSON Schema validation.
- A completed result now requires matching session/ticket/pack identity,
  substantive base/head revisions, acceptance criteria with evidence, command
  receipts, at least one successful command, and no unresolved items.
- Partial/failed/blocked results preserve nonzero command evidence and must
  explain unresolved work.
- Invalid collection is written durably and forces a failed terminal run.

Remaining before acceptance: owning pack review/gate and the broader supported
executor matrix.

### PROC-007 — exact-root source snapshot reliability

- Preserves the operator's normal system/global Git exclude view for the fresh
  exact-root cleanliness command.
- Continues to disable pagers, editors, external diff helpers, and prompts.
- Records bounded command provenance without retaining the unbounded status
  filename list.
- Installed and invariant journeys prove globally ignored state stays clean and
  a real untracked file remains dirty.

Remaining before acceptance: pack review and broader host/wrapper compatibility
coverage.

### PROC-003 — independent communication-channel observation

- Reports tmux liveness, pane death, heartbeat age, output-log growth, and
  executor-event growth independently.
- A fresh executor event prevents a false stall even when heartbeat and plain
  log output are old.
- `possibly_stalled` remains advisory and requires all communication channels
  to be stale.

Remaining before acceptance: complete installed terminate/retry closeout matrix
and the owning pack gate.

## Additional fixes

- Added ticket/pack identity to the bounded child execution environment so
  completion evidence can match immutable launch authority.
- Fixed installed-product dependency-path setup for the wheel test environment.
- Corrected the release-evidence invariant so exported source archives verify the schema-supported `null` Git revision/dirty provenance instead of requiring an unavailable `.git` directory.
- Added `ack --outcome applied|rejected` and documented the adapter support
  boundary.
- Sealed `steering-delivery.jsonl` when present.

## Validation summary

Passed:

- Focused source invariant slice: 30 tests.
- New completion/Git/steering/observation invariant matrix: 5 tests.
- Focused installed-wheel journeys: 6 tests.
- Repository invariant/release/preflight suite: 98 tests.
- Release-asset audit and all four affected prompt-pack validations.
- Existing consumer cursor installed journey.
- Individual restart/tampered-projection journey.

Environment-limited or intentionally not claimed:

- Native MCP behavior was not tested because the configured environment lacks
  the pinned real `mcp==1.28.1` SDK; a metadata-only stub was used solely to
  build and exercise non-MCP installed-wheel journeys.
- Native live tmux and Codex/Claude adapter compatibility were not claimed.
- A single broad acceptance invocation exceeded the aggregate timeout; focused
  files and journeys were rerun independently to isolate product behavior.
- Ruff was not available in the supplied environment; Python compilation,
  `git diff --check`, invariant/release tests, and the repository release audit
  were used instead.
