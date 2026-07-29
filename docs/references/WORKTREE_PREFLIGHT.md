# Agent worktree preflight

This is an agent/operator procedure, not an `agent-workflow` runtime
dependency. The application must remain buildable and usable when the
optional codebase-memory MCP service is unavailable.

## Recommended first action

Before structural code discovery or implementation in a new worktree:

1. Confirm the exact worktree root, branch, baseline revision, and initial
   dirty state.
2. Probe the optional `codebase-memory-mcp` service once. If it is available,
   generate a **full** index for that exact worktree. Do not reuse an index for
   the main checkout or another worktree. Use the available client with:

   ```text
   index_repository(
       repo_path=<absolute worktree root>,
       mode="full",
       persistence=true,
   )
   ```

3. When indexing succeeds, confirm readiness with `index_status` for the
   project returned for that exact root. Record the project identity,
   node/edge counts, readiness, and any artifact or digest in the progress
   record or completion handoff.
4. When the service is unavailable, permission-gated, stale, or errors once,
   record the exact limitation and continue immediately with bounded RTK-
   wrapped `rg`/file inspection. Do not retry, wait for approval, or treat
   missing graph data as an implementation or review blocker.
5. Use the graph when present for definitions, callers, dependencies, and
   impact. Use RTK-wrapped shell inspection for exact literals, configuration,
   scripts, documents, and verification commands in every case.

An exact-worktree index is useful evidence but is never a prerequisite for
implementation, review, build, tests, release checks, or acceptance. A main
checkout index is not evidence for a child worktree; if the exact index cannot
be produced, record that fact and use the documented fallback.

## After implementation

Before the completion handoff, refresh or incrementally update the index for
the same worktree when the service is available and record final
readiness/counts. Otherwise record `codebase_memory: unavailable` and the
fallback searches used. Never claim graph-backed discovery or impact analysis
when it was not performed.

## Optional-service boundary

The MCP service is an operator tool, not a package prerequisite. Do not add it
to `requirements.txt`, `pyproject.toml`, runtime imports, `doctor`, launch
gates, installer behavior, or release health checks. Do not add repository MCP
configuration merely to hide an unavailable service.

If the service is unavailable, record the unavailable result and proceed with
the documented local tools. Shell searches are not equivalent indexed
analysis, so label the fallback honestly; they are nevertheless sufficient to
continue bounded implementation, review, testing, and release work.

## Tool failure budget

Each optional tool gets one availability probe per run. Classify the result as
`available`, `unavailable`, `permission_denied`, `stale`, or `error`. After a
non-available result, continue with the fallback and do not loop on the same
tool. Required repository commands use the command catalog and RTK; their
failure is handled as a real task result, not converted into an MCP retry.

## Minimum preflight record

```text
worktree_root:
branch:
baseline_revision:
dirty_before:
index_project:
index_attempted: true|false
index_available: true|false
index_mode: full|not_run
index_status:
index_nodes:
index_edges:
index_artifact_or_digest:
index_limitation_or_reason:
fallback_discovery_commands:
```
