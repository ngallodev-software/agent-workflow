# Contributing

This repository is pre-public-release. Contributions should stay within the current headless-core scope and begin with an issue or backlog entry before substantial implementation.

## Development setup

```bash
./scripts/bootstrap-dev.sh
.venv/bin/python -m pytest -q
```

Run the complete release gate before submitting changes:

```bash
./scripts/release-check.sh
```

## Change rules

- Preserve one canonical execution path shared by CLI and MCP surfaces.
- Treat status files, SQLite, host bindings, and terminal output as projections, not authorities.
- Add tests through the acceptance-first structure in [Testing](TESTING.md).
- Extend an installed-product journey before adding a narrow invariant when the stronger journey can economically prove the behavior.
- Do not add completed prompt packs, one-off implementation reports, generated caches, vendored SDK source, or local paths.
- Update [BACKLOG.md](BACKLOG.md) for unfinished work and the changelog for user-visible completed work.
- Keep documentation links, CLI help, man pages, examples, schemas, and skills aligned with behavior.

Security-sensitive changes should include adversarial path, symlink, replacement, replay, and crash/restart analysis where applicable.

## Versioning

`agent-workflow` uses semantic versions: `MAJOR.MINOR.PATCH`.

- **MAJOR**: incompatible public CLI, API, state-format, or lifecycle-contract change. Before `1.0.0`, use the next minor version for an incompatible change.
- **MINOR**: a backward-compatible user-visible capability, new command, workflow behavior, or durable contract.
- **PATCH**: a backward-compatible bug fix, test-only change, documentation change, or internal repair with no new public capability.

Apply a maintainer-selected version change with:

```bash
python3 scripts/bump-version.py --bump major|minor|patch
```

The tool updates `VERSION` and `pyproject.toml` together. It deliberately does not infer release significance from commit messages. CI runs `python3 scripts/bump-version.py --check` and rejects a mismatch between the two version authorities.

## Jenkins and repository-only CI assets

Jenkins is a maintained repository development/release workflow, not an installed application feature.

Repository-owned CI assets include `Jenkinsfile`, `scripts/jenkins-local-job.sh`, `scripts/jenkins-local-job.xml`, and `.github/workflows/`. They remain versioned and release-gated in a source checkout, but must not appear in installed Python wheels or runtime bundles.

The default runtime install is the base CLI. A Jenkins job may explicitly install an optional feature profile such as `mcp`; that CI choice does not make the optional dependency part of the base runtime.

Release tests inspect built-wheel/runtime inventories and fail if repository-only CI assets leak into installed distributions.

## Scope

Automatic merging, autonomous model selection, remote execution, web UI, daemonization, and network MCP transport are out of scope unless [BACKLOG.md](BACKLOG.md) records an explicit maintainer decision.
