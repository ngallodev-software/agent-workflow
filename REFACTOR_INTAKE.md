# Major refactor intake

This branch is the clean intake point for the incoming major-refactor archive.

- Branch: `refactor/major-refactor-intake-20260824`
- Baseline: merge commit `b581e2e`
- Parent: `master`
- Related work merged: Herdr-boundary documentation and tmux wakeup removal

The incoming archive should be applied from this branch in a separate working
tree. Preserve the archive's transfer manifest and record its source revision,
SHA-256, changed paths, and any explicit deletions before committing the
refactor. Do not apply an archive over `master` or over an unrelated worktree.

The repository transfer standard is a deterministic GNU `tar` plus `zstd`
archive without Git metadata, compiled code, bytecode, virtual environments,
caches, build/dist output, testing output, or local handoff state. The archive
must carry a canonical `TRANSFER_MANIFEST.json` and a sidecar SHA-256 checksum.
