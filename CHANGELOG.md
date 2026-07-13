# Changelog

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

