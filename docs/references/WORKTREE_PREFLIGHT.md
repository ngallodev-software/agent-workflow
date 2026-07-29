# Agent worktree preflight

This is an agent/operator procedure, not an `agent-workflow` runtime
dependency. The application must remain buildable and usable when the
optional codebase-memory MCP service is unavailable.

## Required first action

Before structural code discovery or implementation in a new worktree:

1. Confirm the exact worktree root, branch, baseline revision, and initial
   dirty state.
2. Generate a **full** codebase-memory index for that exact worktree. Do not
   reuse an index for the main checkout or another worktree. Use the available
   `codebase-memory-mcp` client with:

   ```text
   index_repository(
       repo_path=<absolute worktree root>,
       mode="full",
       persistence=true,
   )
   ```

3. Confirm readiness with `index_status` for the project returned for that
   exact root. Record the project identity, node/edge counts, readiness, and
   any artifact or digest in the progress record or completion handoff.
4. Use the resulting graph for definitions, callers, dependencies, and
   impact. Use RTK-wrapped shell inspection for exact literals, configuration,
   scripts, documents, and verification commands.

The index must be generated before the first structural code edit. A main
checkout index is not evidence for a child worktree because it cannot contain
the worktree's baseline, local changes, or generated files.

## After implementation

Before the completion handoff, refresh or incrementally update the index for
the same worktree and record the final readiness/counts. If the service cannot
index the worktree, state that explicitly and do not claim graph-backed
discovery or impact analysis.

## Optional-service boundary

The MCP service is an operator tool, not a package prerequisite. Do not add it
to `requirements.txt`, `pyproject.toml`, runtime imports, `doctor`, launch
gates, installer behavior, or release health checks. Do not add repository MCP
configuration merely to hide an unavailable service.

If the service is unavailable, record the unavailable result. Documentation,
configuration, and literal-only work may use the documented local tools. For
structural implementation work, pause for operator direction or proceed only
under an explicitly recorded fallback; never silently present shell searches
as equivalent indexed analysis.

## Minimum preflight record

```text
worktree_root:
branch:
baseline_revision:
dirty_before:
index_project:
index_mode: full
index_status:
index_nodes:
index_edges:
index_artifact_or_digest:
index_limitations:
```
