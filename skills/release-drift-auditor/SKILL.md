---
name: release-drift-auditor
description: Audit release artifacts for version, schema, command, documentation, skill, packaging, and architectural drift.
---

# Release Drift Auditor Skill

Audit the release artifact against the current headless Agent Run architecture.

Verify version consistency, wheel contents, schemas, command catalog, docs, skills, examples, release policy, dependency lock, and test evidence. Flag any stale command or configuration surface that reintroduces a removed interactive-runtime dependency or the obsolete broad `session` execution noun.

Treat current architecture, schemas, parser-derived commands, release policy/evidence, installed acceptance journeys, `docs/SKILL_FIRST_SIMPLIFICATION_PLAN.md`, and `docs/BACKLOG.md` as the active authorities. Completed implementation-phase records belong in source-control/release history rather than the active product tree.
