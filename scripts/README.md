# Repository maintenance scripts

Scripts in this directory support repository bootstrap, release validation/evidence, CI integration, version synchronization, test-authority auditing, and other maintainer workflows. Durable product lifecycle behavior belongs in `src/agent_workflow/`, not in shell wrappers maintained as a second implementation surface.

Prompt-pack helper scripts are packaged only in `src/agent_workflow/assets/prompt-pack-root/` and are materialized by `agent-workflow pack scaffold`. The repository no longer keeps byte-identical compatibility copies under `scripts/` or `templates/`.

## Release evidence

`release-check.sh` is the consolidated technical validation entrypoint. It records pytest JUnit XML and invokes `release-evidence.py` on both success and failure. The evidence generator validates `release/release-policy.json` and `release/dependency-lock.json`, writes CycloneDX SBOM and build-provenance files, and summarizes technical and governance status in `release-evidence.json`.

Use `AGENT_WORKFLOW_ENFORCE_RELEASE_BLOCKERS=1` only for a release authorization gate; development validation records open blockers without converting them into a failed technical check. See [`docs/RELEASE_EVIDENCE.md`](../docs/RELEASE_EVIDENCE.md).

## Version and documentation synchronization

Use `python3 scripts/bump-version.py --bump patch|minor|major` for active version authorities, then run `python3 scripts/bump-version.py --check` and the release tests. The version helper does not replace documentation auditing: installation examples, optional MCP statements, repository-only Jenkins packaging claims, skills, and generated command behavior must remain synchronized.

`audit-release-assets.py` also validates executable `agent-workflow` examples in shell-fenced skill blocks against the live core parser with plugins disabled. This keeps the parser authoritative for skill syntax without treating inline prose references or plugin commands as normal agent-facing contracts.

## Test-authority drift audit

`audit-test-suite.py` enforces `tests/test-authority.json`: layer and per-invariant function budgets, collected-case ceilings, explicit invariant rationales, mock/private-import exceptions, subprocess and wheel-build site budgets, and an optional JUnit runtime ceiling. `release-check.sh` runs the audit before tests and records `test-suite-audit.json` from the completed JUnit run.

## Agent-efficiency baseline

`measure-agent-efficiency.py` records the Phase 0 agent-facing baseline from the live parser, role cards, launch-context generator, primary skill, and documented multi-command journeys. It is deliberately provider-neutral and does not launch Codex or Claude. The committed `release/agent-efficiency-baseline.json` is the comparison point for the 0.9 skill-first simplification; dynamic setup/finalization timing should be taken from existing installed-product journeys rather than by adding measurement-only test files.
