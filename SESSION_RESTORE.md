# Session restore

**Repository:** `/lump/apps/agent-workflow`  
**Snapshot date:** 2026-07-26  
**Coordinator branch:** `master`  
**Coordinator revision at start of this handoff:** `8b937a021f8940da61adfb8b0afec63f2cf12d2e` (`ci: force Jenkins tests to install current wheel`)
**Handoff baseline commit:** `747b9f8` (`docs: record release blockers and session handoff`)
**Current handoff revision:** `1dec2cf` (`docs: finalize session handoff metadata`)

## Work completed in this session

- Terminated the orphaned Claude Sonnet run `pr-1-sonnet-fix-20260725` with the workflow CLI.
- Removed its shared-window pane `0:0.1` after the run was interrupted.
- Verified no matching Claude Sonnet or agent-workflow runner process remains.
- Stopped the stale `workflow-demo-coordinator-20260725-r2` run and its four orphaned Claude child runners; their deleted worktrees had no commits or completion handoffs to merge.
- Updated `BACKLOG.md` with release-governance, deterministic-security, release-evidence, and Jenkins-trigger tasks.
- Updated `docs/RELEASE_BLOCKERS_AUDIT.md`, `docs/PUBLIC_RELEASE_READINESS.md`, and `docs/RELEASE_CHECK_AUDIT.md` with the new task mappings and current Jenkins evidence.

## Verified Jenkins state

Job: `agent-workflow-local`  
Build: `#16`  
Revision: `8b937a0` from `origin/master`  
Result: `SUCCESS`

Evidence from the Jenkins log:

- `35 passed, 2 skipped, 1 xfailed`
- `release checks passed`
- wheel `agent_workflow-0.2.2-py3-none-any.whl` built
- local install completed at the Jenkins workspace virtualenv

Important limitation: the Jenkins job configuration still has no SCM trigger (`<triggers/>`). Build #16 was manually triggered for verification. Finish `REL-006` by configuring and proving a local commit-trigger/polling path; keep it local-only.

## Current terminal state

The primary tmux session now contains only the orchestrator pane:

- `0:0.0` — live orchestrator pane
- Removed: `0:0.1` — Claude Sonnet PR #1 repair pane

The separate session `workflow-demo-coordinator-20260725-r2` was removed after its five panes were confirmed stale. Its durable run records remain as interrupted historical evidence; no worktree or branch remains for those runs.

## Workspace state

The documentation changes and the determinism/security assessment artifacts are committed. The repository has no uncommitted changes and has only the primary worktree:

- `master` at `1dec2cf`
- one worktree: `/lump/apps/agent-workflow`
- no agent-workflow feature branches or registered agent worktrees

The branch is ahead of `origin/master` by two local documentation commits. Push them before treating the remote as the canonical fresh-session baseline.

The Markdown assessment is the source for the new `SEC-001` through `SEC-004` backlog tasks; the HTML export is tracked alongside it.

## Next work, in order

1. Resolve P0 governance decisions: `REL-001`, `DEC-001`, `REL-002`, and `REL-004`.
2. Implement and evidence `SEC-001` through `SEC-004` before a public preview:
   bounded subprocesses; preventative scope and pack file-type integrity; MCP privacy/path/receipt hardening; immutable launch authority.
3. Implement `BKL-001`, then `BKL-002`; existing journeys cover parts of these behaviors, but the backlog remains open and the late-steering test is an expected failure.
4. Complete `REL-005` automated blocker gates and durable release evidence.
5. Complete `REL-006` Jenkins local commit triggering and verify the checked-out revision matches the triggering commit.
6. Complete `REL-003` and `REL-007`: clean-host compatibility, install/uninstall, and controlled real-provider/workflow evidence.
7. Keep `MCP-003` behind the current read-only boundary until the P0 security controls and authorization/idempotency design are complete.

## Safe restart commands

```bash
cd /lump/apps/agent-workflow
git status --short --branch
git log -3 --oneline
agent-workflow doctor
tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index}\t#{pane_title}\t#{pane_current_command}\tdead=#{pane_dead}'
agent-workflow list
```

Before claiming release readiness, rerun the installed-product gates and verify the Jenkins job from a fresh build. Do not modify test files unless the user explicitly changes the standing instruction; the current work intentionally made no test changes.
