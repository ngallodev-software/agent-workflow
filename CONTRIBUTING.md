# Contributing

This repository is pre-public-release. Contributions should stay within the current terminal-first scope and begin with an issue or backlog entry before substantial implementation.

## Development setup

```bash
python -m pip install -e '.[dev]'
pytest
```

Run the complete release gate before submitting changes:

```bash
./scripts/release-check.sh
```

## Change rules

- Preserve one canonical execution path shared by CLI and MCP surfaces.
- Treat status files and terminal output as projections, not authorities.
- Add tests through the acceptance-first structure in [docs/TESTING.md](docs/TESTING.md).
- Extend an installed-product journey before adding a narrow invariant.
- Do not add completed prompt packs, one-off implementation reports, generated caches, vendored SDK source, or local paths.
- Update the backlog for unfinished work and the changelog for user-visible completed work.
- Keep documentation links, CLI help, man pages, examples, schemas, and skills aligned with behavior.

Security-sensitive changes should include adversarial path, symlink, replacement, replay, and crash/restart analysis where applicable.

## Scope

Automatic merging, autonomous model selection, remote execution, web UI, daemonization, and network MCP transport are out of scope unless the backlog records an explicit maintainer decision.
