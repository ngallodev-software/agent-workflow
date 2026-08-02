---
name: release-drift-auditor
description: Audit agent-workflow for backlog and prompt-pack collisions, documentation-to-code drift, stale security claims, and release-surface inconsistencies before phase gates or packaging.
---

# Release drift auditor

Use this skill after parallel ticket integration, before every phase gate, and before producing a source or release archive. It specializes the broader review duties in [`phase-gate-review`](../phase-gate-review/SKILL.md); it does not replace independent security or implementation review.

## Deterministic preflight

Run from the repository root:

```bash
python3 scripts/audit-release-assets.py
for pack in prompt-packs/*/pack.yaml; do
  agent-workflow pack validate "$(dirname "$pack")"
done
agent-workflow index verify --full
```

Treat a failing audit as a release blocker. Do not waive duplicate task IDs, unknown `backlog_id` values, cross-pack ownership, broken links, stale mirrors, invalid checksums, or missing active-pack documentation through prose.

## Review inventory

Compare the live implementation with:

- `BACKLOG.md` state, dependencies, and prompt-pack ownership;
- active pack manifests, ticket IDs, prerequisites, and checksums;
- public CLI help, command reference, man pages, shell completion, and examples;
- schemas, migrations, packaged assets, version markers, and rebuildable SQLite projection provenance;
- README, architecture, operations, testing, MCP, security, support, and release-readiness claims;
- skills and portable execution/runbook copies;
- chart-pack authority, trust-boundary, test, and release diagrams;
- strict future tests and their referenced backlog IDs;
- release manifest, dependency metadata, source/wheel contents, and generated artifacts.
- active version authorities and current release examples across package metadata, CLI/doctor output, man pages, installers, release policy, prompt-pack minimum versions, and tests;
- optional MCP claims and repository-only Jenkins claims across README/install/help/man/wheel/runtime-bundle surfaces.

## Drift classes

Classify every finding:

1. **Authority drift** — docs or code treat a projection, path reopen, terminal capture, or agent claim as authority.
2. **Task drift** — duplicate IDs, conflicting packs, completed work still active, unowned tickets, or missing prerequisites.
3. **Behavior drift** — docs/help/man/examples describe a command, option, state, or capability that code does not expose.
4. **Security drift** — guidance claims preventative enforcement when implementation is only advisory or detective.
5. **Evidence drift** — tests, reports, or completion claims are not derived from sealed/verified evidence.
6. **Release drift** — version, manifest, packaging, dependency, support, license, or vulnerability-reporting claims disagree.
7. **Index drift** — SQLite schema/query claims, source provenance, freshness, or privacy exclusions disagree with the authoritative artifacts.
8. **Diagram drift** — architecture or trust-boundary diagrams omit or misclassify a changed authority path.

## Agent review procedure

- Read the complete integrated diff, not only completion reports.
- Generate inventories from code where possible; do not manually compare a few remembered commands.
- Search for stale ticket IDs and removed prompt-pack names across all tracked text.
- Confirm every active pack is listed once in `docs/PROMPT_PACKS.md` and owns only backlog items declared in `BACKLOG.md`.
- Confirm blocked packs cannot be mistaken for executable-ready work.
- Confirm base installs do not require MCP or edit MCP client configuration, and confirm Jenkins/GitHub workflow assets cannot enter wheels or runtime bundles.
- Confirm each new security statement names whether it is enforced, detected post-run, or guidance-only.
- Reject broad cleanup that is unrelated to a concrete drift finding.
- Record unresolved drift explicitly in the phase-gate report; do not rewrite history to make it disappear.

## Required output

Produce a bounded drift report containing:

- revision and clean/dirty state;
- deterministic audit commands and exit codes;
- inventories compared;
- findings by drift class and severity;
- exact files and claims affected;
- fixes applied versus deferred backlog IDs;
- pack ownership/collision result;
- final accept/reject recommendation.

A clean report means no reproducible drift was found in the inspected surfaces. It is not proof that the software is vulnerability-free or that an external reviewer approved it.
