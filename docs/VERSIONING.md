# Versioning

`agent-workflow` uses semantic versions: `MAJOR.MINOR.PATCH`.

- **MAJOR**: incompatible public CLI, API, state-format, or lifecycle-contract change. Before `1.0.0`, use the next minor version for an incompatible change.
- **MINOR**: a backward-compatible user-visible capability, new command, workflow behavior, or durable contract.
- **PATCH**: a backward-compatible bug fix, test-only change, documentation change, or internal repair with no new public capability.

Use `python3 scripts/bump-version.py --bump major|minor|patch` to apply a
maintainer-selected bump. The tool updates `VERSION` and `pyproject.toml` as
one change. It deliberately does not infer release significance from commit
messages. CI runs `python3 scripts/bump-version.py --check` and rejects a
mismatch between the two version authorities.
