---
name: release-drift-auditor
description: Audit release artifacts for version, schema, command, documentation, skill, packaging, and architectural drift.
---

# Release Drift Auditor Skill

Audit the release artifact against the current headless Agent Run architecture.

Verify version consistency, wheel contents, schemas, command catalog, docs, skills, examples, release policy, dependency lock, and test evidence. Flag any stale command or configuration surface that reintroduces a removed interactive-runtime dependency or the obsolete broad `session` execution noun.

Treat current architecture, schemas, parser-derived commands, release policy/evidence, installed acceptance journeys, and `docs/BACKLOG.md` as the active authorities. Phase 0–2 planning/acceptance records are temporary closeout evidence only and must not become permanent product authority.
