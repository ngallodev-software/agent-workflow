# Compatibility scripts

These filenames preserve the helper interface used by earlier prompt packs. They are intentionally thin wrappers around the installed `agent-workflow` CLI. Do not add independent lifecycle logic here; durable behavior belongs in `src/agent_workflow/`.

## Release evidence

`release-check.sh` remains the consolidated technical validation entrypoint. It now records pytest JUnit XML and invokes `release-evidence.py` on both success and failure. The evidence generator validates `release/release-policy.json` and `release/dependency-lock.json`, writes CycloneDX SBOM and build-provenance files, and summarizes technical and governance status in `release-evidence.json`.

Use `AGENT_WORKFLOW_ENFORCE_RELEASE_BLOCKERS=1` only for a release authorization gate; development validation records open blockers without converting them into a failed technical check. See [`docs/RELEASE_EVIDENCE.md`](../docs/RELEASE_EVIDENCE.md).

## Version and documentation synchronization

Use `python3 scripts/bump-version.py --bump patch|minor|major` for active version authorities, then run `python3 scripts/bump-version.py --check` and the release tests. The version helper does not replace the documentation audit: current installation examples, prompt-pack minimum versions, restore instructions, optional MCP statements, and repository-only Jenkins packaging claims must remain synchronized.

## Test-authority drift audit

`audit-test-suite.py` enforces `tests/test-authority.json`: layer and per-invariant function budgets, collected-case ceilings, explicit invariant rationales, mock/private-import exceptions, subprocess and wheel-build site budgets, and an optional JUnit runtime ceiling. `release-check.sh` runs the audit before tests and records `test-suite-audit.json` from the completed JUnit run.
