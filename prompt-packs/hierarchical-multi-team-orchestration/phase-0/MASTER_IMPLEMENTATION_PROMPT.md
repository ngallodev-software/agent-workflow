# Phase 0

Implement hierarchy authority, team delegation capability validation, journals,
and receipt construction first. Preserve all current direct-orchestrator behavior.

Implement hierarchy-specific policy and state inside the dedicated hierarchy feature package. Touch core modules only through the smallest stable facade/registration seam required by this phase; direct orchestration must remain the default and must pass unchanged acceptance journeys.
