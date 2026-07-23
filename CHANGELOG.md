# Changelog

## Unreleased

- Add versioned evaluation, completion, provenance, command, score, lifecycle, and final-receipt contracts with packaged JSON Schemas.
- Preserve Codex/Claude structured event streams, separate stderr, enforce time/token budgets, capture patches, and seal validated run evidence.
- Add baseline/post scope and command collectors, JUnit regression attribution, deterministic receipt-backed scorers, external oracle boundaries, public fixtures, ledgers, and reports.
- Add explicit review/accept/reject receipts, append-only lifecycle events, multi-signal diagnostics, paired comparison statistics, and stable failure categories.
- Reuse Inspect SWE adapters behind an optional Docker evaluation seam; add optional SWE-bench, OpenTelemetry, MLflow, and shell-completion integrations.
- Correct live Codex non-Git and Claude structured-output command requirements and preserve structured executor settings across retries.

## 0.1.2

- Add collector-owned worktree completion handoffs, sealed completion-collection
  receipts, and acceptance enforcement for valid collected completion evidence.
- Repair installed schema discovery and preserve structured explicit Codex/Claude
  executor metadata.

## 0.1.1

- Add required YAML frontmatter to every shipped agent skill.
- Make all YAML templates syntactically valid before placeholder substitution.
- Add comprehensive release-asset auditing for skills, templates, schemas, links, versions, duplicate portable assets, and manifest coverage.
- Add regression tests for skill metadata and parseable template assets.
- Scope release auditing to distributable files and enforce complete manifests.
- Reject prompt traversal and malformed configuration types.
- Preserve terminal run evidence and requested worktree-base provenance.
- Pass durable prompt-pack/session context to Codex and Claude executors.
- Make install/uninstall symlink handling portable and ownership-safe.
- Remove inert source-root, prompt-pack-root, and failed-worktree config knobs.

## 0.1.0

Initial terminal-first workflow release.

### Included

- XDG configuration and persistent run state
- isolated Git worktree creation/removal/listing
- fresh named tmux session per delegation
- prompt and command provenance with SHA-256 hashes
- live logs and structured session status
- attach, tail, capture, interrupt, terminate, kill, and retry controls
- conservative potential-stall observation
- prompt-pack scaffolding and validation
- deterministic tar.zst archives and SHA-256 output
- compatibility shell wrappers
- reusable skills, schemas, templates, examples, and documentation
- natural placement for global `--json` and `--config` options
- dirty-worktree launch guard with an explicit `--allow-dirty` escape hatch
- release validation, security guidance, roadmap, and consolidated release checks

### Intentionally excluded

- automatic merging
- automatic stall termination
- daemon or web UI
- remote execution
- GitHub synchronization
- automatic model selection
- multiple terminal backends
