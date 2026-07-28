# Release drift audit — specification/plugin design overlay

Date: 2026-07-28

## Revision and state

- Base revision: `fa00941` (`Add MCP command context resources`)
- Audit state: dirty working tree containing the re-extracted design overlay and the DEC-004 status correction
- Target version: `0.2.5`

## Checks

| Check | Result |
|---|---:|
| `python3 scripts/audit-release-assets.py` | 0 |
| Four active prompt-pack validations | 0 |
| Full pytest suite | 95 passed, 2 skipped, 5 expected failures |
| `python3 -m build` | 0 |

## Reconciliation

- Added the collaborative specification compiler/plugin-first architecture design.
- Preserved BKL-001 completion and all prior 0.2.5 history; the overlay backlog was stale and was not copied wholesale.
- Recorded maintainer direction as `DEC-004: decided`.
- Kept PLUG-001 and SPEC/ARC tasks separately gated and non-executable; no implementation pack or plugin code was added.
- Kept future `agent-workflow spec` and `plugins` command examples marked as design text so release checks do not advertise unimplemented installed commands.
- Preserved the existing MCP read-only capability/catalog and launch-contract v2 boundaries.

## Recommendation

Accept the documentation/design overlay for integration. No runtime plugin implementation is authorized by this commit; PLUG-001 remains a separately gated follow-up.
