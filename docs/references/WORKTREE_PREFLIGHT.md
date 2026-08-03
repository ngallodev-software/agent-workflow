# Agent worktree preflight

This is an agent/operator procedure, not an `agent-workflow` runtime
dependency. The application must remain buildable and usable when the optional
codebase-memory MCP service is unavailable.

## Safety invariant

Optional discovery must leave the candidate worktree unchanged by default.
Capture `git status --porcelain=v2 -z` before and after the probe. An exact-
worktree graph is useful evidence, but repository-local persistence is not a
prerequisite and must not be enabled implicitly.

## Recommended first action

Before structural code discovery or implementation in a new worktree:

1. Confirm the exact worktree root, branch, baseline revision, and initial
   porcelain status.
2. Probe the optional `codebase-memory-mcp` service once. If it is available,
   generate a **full, non-persistent** index for that exact worktree:

   ```text
   index_repository(
       repo_path=<absolute worktree root>,
       mode="full",
       persistence=false,
   )
   ```

3. Confirm readiness with `index_status` for the project returned for that
   exact root. Record the project identity, node/edge counts, readiness, and
   worktree identity.
4. Re-run `git status --porcelain=v2 -z`. If the optional tool created any
   repository artifact, stop using it for this run, record
   `unexpected_repository_residue`, and continue with bounded RTK-wrapped
   `rg`/file inspection. Do not ask the child for destructive approval and do
   not wait for steering that the executor cannot receive.
5. When the service is unavailable, permission-gated, stale, or errors once,
   record the exact limitation and continue immediately with the fallback. Do
   not retry or treat missing graph data as an implementation or review
   blocker.
6. Use the graph when present for definitions, callers, dependencies, and
   impact. Use RTK-wrapped shell inspection for exact literals,
   configuration, scripts, documents, and verification commands in every
   case.

A main-checkout index is not evidence for a child worktree. If an exact index
cannot be produced without dirtying the child worktree, record that fact and
use the documented fallback.

## Persistent-index exception

Persistent indexing is allowed only through one of these explicit host-owned
paths:

1. **External cache:** the service exposes an artifact/cache-root parameter and
   the operator points it to a directory outside the repository, preferably
   `$XDG_CACHE_HOME/agent-workflow/codebase-memory/<worktree-id>/`.
2. **Authorized local disposable tree:** the launch/evaluation scope explicitly
   lists `.codebase-memory/` in `disposable_trees`, the host coordinator owns
   cleanup, and the operator accepts a 256 MiB per-worktree limit.

If the service cannot direct persistence outside the worktree and local
`.codebase-memory/` is not already authorized, use non-persistent mode. Never
broaden scope from inside the child merely to retain an optional graph.

For an authorized local disposable tree, the scope collector records:

- owner UID/GID and mode;
- file count and total size;
- deterministic tree SHA-256;
- explicit disposable authorization;
- the host-owned cleanup policy;
- the 256 MiB limit and whether the tree is within it.

A missing, unsafe, unauthorized, or oversized local tree is a tooling
limitation. It is not source work and must not block the ticket. Cleanup is a
host action after evidence collection; a child without deletion authority must
not attempt it.

## After implementation

Before the completion handoff, refresh the same exact-worktree index only when
that can be done non-persistently or through the already authorized external or
disposable location. Record final readiness/counts. Otherwise record
`codebase_memory: unavailable` and the fallback searches used. Never claim
graph-backed discovery or impact analysis when it was not performed.

## Optional-service boundary

The MCP service is an operator tool, not a package prerequisite. Do not add it
to `requirements.txt`, `pyproject.toml`, runtime imports, `doctor`, launch
gates, installer behavior, or release health checks. Do not add repository MCP
configuration merely to hide an unavailable service.

Shell searches are not equivalent indexed analysis, so label the fallback
honestly; they are nevertheless sufficient to continue bounded
implementation, review, testing, and release work.

## Tool failure budget

Each optional tool gets one availability probe per run. Classify the result as
`available`, `unavailable`, `permission_denied`, `stale`, `error`, or
`unexpected_repository_residue`. After a non-available result, continue with
the fallback and do not loop on the same tool. Required repository commands use
the command catalog and RTK; their failure is handled as a real task result,
not converted into an MCP retry.

## Minimum preflight record

```text
worktree_root:
branch:
baseline_revision:
dirty_before_porcelain_v2_sha256:
index_project:
index_attempted: true|false
index_available: true|false
index_mode: full|not_run
index_persistence: non_persistent|external_cache|authorized_disposable|not_run
index_external_artifact_root:
index_status:
index_nodes:
index_edges:
index_artifact_or_digest:
local_artifact_owner_uid_gid:
local_artifact_size_bytes:
local_artifact_tree_sha256:
local_artifact_cleanup_policy:
local_artifact_within_limit: true|false|not_applicable
dirty_after_porcelain_v2_sha256:
unexpected_repository_residue:
index_limitation_or_reason:
fallback_discovery_commands:
```
