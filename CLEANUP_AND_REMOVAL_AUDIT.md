# Cleanup and removal audit

**Release:** 0.2.1
**Updated:** 2026-07-24

This audit distinguishes material removed in this release from optional historical material and generated files that must not be shipped. Paths are repository-relative.

## Removed in the 0.2.0 workflow-completion pass

| Path | Disposition | Reason |
|---|---|---|
| `src/agent_workflow/mcp/sdk/` | removed, 141 tracked files | Unused vendored copy of the official MCP Python SDK. It was not imported by runtime code, was excluded from package discovery, duplicated upstream maintenance/security work, and added about 1.8 MB of drift. Runtime and tests use the pinned optional dependency through public APIs. |
| `src/agent_workflow/mcp/SDK_SNAPSHOT.md` | replaced by `SDK_DEPENDENCY.md` | The old name implied a maintained vendored snapshot. The replacement records the exact external dependency/tag/commit without carrying third-party source. |


## Reviewed in the 0.2.1 critical repair

- Consolidated workflow journal parsing on the descriptor-safe locked reader instead of maintaining a second receipt-specific parser.
- Retained the workflow lock as a single small durable coordination file; rejected symlink/non-regular substitutions rather than introducing a daemon, database, or broker.
- Removed generated caches and build output before packaging.
- Re-reviewed historical prompt packs and execution evidence. They remain explicit provenance, not runtime dependencies or active task trackers.
- Found no additional vendored dependency, duplicate scheduler, compatibility layer, project-specific adapter, or unused runtime subsystem that could be removed safely.

## Generated material removed before packaging

These paths are safe to delete at any time and are excluded from release archives:

- `.pytest_cache/`
- every `__pycache__/` directory and `*.pyc` file, including those under source, tests, and deterministic fixtures;
- Python build output such as `build/`, `dist/`, and `*.egg-info/` when generated locally;
- editor/OS temporary files and test scratch directories.

## Historical removals retained in Git history

Earlier cleanup passes removed one-off delivery artifacts (`VALIDATION.md`, `IMPLEMENTATION.patch`, and the root `IMPLEMENTATION_REPORT.md`) and an unrelated project-specific adapter/test. They remain absent. They are not repeated as current 0.2.0 source changes.

## Optional archival candidates, not removed

These are not runtime dependencies, but they retain useful provenance or reusable examples. Remove them only under an explicit repository-history policy:

| Path | Why it can be archived | Why it remains now |
|---|---|---|
| `docs/execution-evidence/` | Completed ticket/gate reports are not imported at runtime. | Provides reviewable release provenance and records the original WF-10 rejection and correction boundary. |
| `prompt-packs/agent-workflow-skills-and-mcp/` | Completed historical input pack. | Useful for reproducing the skill/MCP foundation. |
| `prompt-packs/orchestrator-messaging-evals/` | Completed historical input pack. | Preserves the durable messaging/evaluation design lineage. |
| `prompt-packs/workflow-foundations-next/` | Superseded as an execution queue by the completed implementation. | Authoritative ticket contracts and prior independent-review history remain valuable. |
| `prompt-packs/chatgpt-workflow-completion-next/` | Completed input pack. | Retained as the exact implementation instruction set executed for 0.2.0. |
| `examples/three-phase-pack/` | Not runtime code. | Maintained user-facing example and validation fixture. |

## Reviewed and retained intentionally

- `scripts/`: compatibility entry points and release/prompt-pack tooling remain exercised.
- `templates/` and `src/agent_workflow/assets/`: both source and packaged copies are required; release auditing checks synchronization.
- `tests/fixtures/` and `evals/fixtures/`: deterministic regression inputs, not user/runtime debris.
- historical `CHANGELOG.md` and `BACKLOG.md` entries: release history, not stale current-state documentation.
- the read-only MCP implementation under `src/agent_workflow/mcp/`: active code; only the unused vendored SDK subtree was removed.

## Simplification conclusion

No second scheduler, executor launch path, database, broker, daemon, HTTP service, online-learning layer, arbitrary terminal steering mechanism, or compatibility shim was introduced. The largest confirmed drift source was the vendored SDK and it has been eliminated. Remaining optional historical packs/evidence are explicit provenance rather than hidden runtime complexity.
