# Index the exact worktree before worker launch

For every newly created implementation worktree, complete this preflight before
starting any headless worker, native child/forked agent or interactive Herdr agent.
`cbm` is the shortcut for `codebase-memory-cli`.

1. Create the isolated worktree and verify its canonical Git root, branch and
   source revision. Capture `git status --porcelain` before indexing.
2. Launch a separate `cbm index` process against that exact worktree, in full mode
   with repository-local persistence disabled. Use a distinct project identity
   for that worktree; never index the primary checkout or reuse its graph as the
   worker's baseline. Check the installed CLI help if syntax differs:

   ```sh
   cbm index --repo-path "$WORKTREE_PATH" --mode full --persistence false --json
   ```

3. Wait for successful process completion. Verify `cbm projects --json` and
   `cbm status --project "$WORKTREE_PROJECT" --json` identify the canonical
   worktree root and a ready graph. Record project identity, generation/freshness,
   node/edge counts, parse/coverage limitations, command/exit/log and Git revision.
   Launching the index process or seeing a graph for another checkout is not enough.
4. Capture Git porcelain again and compare it with the baseline. Do not discard
   unrelated edits. Unexpected repository residue blocks launch; record the issue
   before targeted cleanup. Do not enable `.codebase-memory/` persistence unless
   that directory is pre-authorized disposable scope with host-owned cleanup.
5. Put the verified index receipt and limitations into the initial task prompt
   before Agent Run preparation/digest capture. Keep evidence in durable launch
   staging, then attach/reference it in run-owned evidence/provenance. Prepare the
   run, and only then spawn/start its worker. Pass explicit project selection to
   the worker; it must still verify coverage for its actual evidence paths.

If indexing fails, is incomplete/not ready, points at the wrong root, or cannot
remain usable for the worker, do not launch the worker as though indexed. Record
observed CLI issues in `/lump/apps/codebase-memory-cli/BACKLOG.md` (parent-owned
updates during parallel work) and retain diagnostics. Do not stop a shared daemon,
switch account cache roots, widen allow-root or add an unrequested service merely
to force success. Resolve the actual blocker before launch.

When a combined create-and-start facade has no indexing boundary, split the flow
into worktree creation, index preflight, prompt/Agent Run preparation and worker
start. Indexing is an operator launch preflight, not a new dependency of the
Agent-Workflow core, and does not replace build/test/review/acceptance gates.
