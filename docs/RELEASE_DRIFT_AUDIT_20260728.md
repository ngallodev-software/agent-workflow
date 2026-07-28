# Release drift audit — MCP command context overlay

Date: 2026-07-28

## Revision and state

- Base revision: `2e2557b` (`Record Jenkins wheel deployment evidence`)
- Audit state: dirty working tree containing the requested `agent-workflow-0.2.5-mcp-command-context-incremental-20260727.tar.zst` overlay and this report
- Target version: `0.2.5`

## Deterministic checks

| Check | Result |
|---|---:|
| `python3 scripts/audit-release-assets.py` | 0 |
| `agent-workflow pack validate prompt-packs/deterministic-enforcement-foundations` | 0 |
| `agent-workflow pack validate prompt-packs/execution-isolation-and-secrets` | 0 |
| `agent-workflow pack validate prompt-packs/public-beta-trust-and-release` | 0 |
| `agent-workflow pack validate prompt-packs/mcp-server-next` | 0 |
| Focused MCP tests | 7 passed, 2 expected failures |
| Full pytest suite | 95 passed, 2 skipped, 5 expected failures |
| `python3 -m build` | 0 |

## Inventory compared

- Canonical `docs/BACKLOG.md` and active pack ownership.
- MCP server, shared MCP services, parser-derived command catalog, contracts, and schemas.
- CLI command reference, MCP documentation, security/architecture claims, man page, and repository diagrams.
- MCP prompt-pack handoff, README, phase prompt, and orchestrator skill guidance.
- Acceptance, invariant, and future MCP journeys.
- Source distribution and wheel contents, including the three new MCP schemas.

## Findings

No reproducible authority, task, behavior, security, evidence, release, or diagram drift remained in the inspected overlay surfaces.

The external overlay contained stale backlog status and was not copied wholesale. The canonical BKL-001 completed state and its evidence reference were preserved. MCP-003 remains blocked on HARD-004, HARD-005, and HARD-007; that is an intentional backlog prerequisite, not an overlay defect.

The two MCP mutation future tests remain expected failures because mutation tools are not implemented. The five other expected failures are existing planned-work journeys. None was converted to a passing claim.

## Fixes applied

- Added schema-validated capability and role-catalog MCP resources.
- Added verified per-run command-context and bounded command-card resources with redacted executable identity and fail-closed digest checks.
- Reused parser-derived catalog and launch-contract boundaries rather than creating an MCP command registry.
- Updated documentation, man page, diagrams, skills, and MCP pack guidance to describe the read-only discovery boundary and preserve launch-contract v2 for future mutation work.
- Added acceptance and invariant coverage and recorded the integrated capability in the canonical backlog history.

## Deferred work

- MCP-003 mutation tools remain blocked by the canonical prerequisites and require a separately gated implementation.
- No dynamic MCP tool generation, HTTP transport, lifecycle authority, or direct state mutation was added.

## Recommendation

Accept the overlay for integration. The post-commit repository should be clean, and the MCP-003 blocked state should remain unchanged until its prerequisites are accepted.
