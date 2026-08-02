# Phase 0 — trust, drift, supply chain, and compatibility master implementation prompt

Read current source, `BACKLOG.md`, the feature assessment, the hardening plan, this phase README, every ticket, and the prior accepted gate before editing.

Coordinate only these tickets: `HARD-007`, `HARD-009`, `HARD-010`, `REL-003`. Respect manifest dependencies. Dependency-free tickets may run concurrently in isolated worktrees. Do not merge by taking one agent's branch wholesale; inspect each diff and integrate the smallest compatible changes.

Require installed-product acceptance journeys first. Keep only compact parameterized security/replay invariants. Run the release drift audit after integration. Stop on any task ownership collision, unresolved prerequisite, scope expansion, or implementation that substitutes guidance for enforcement.

Preserve DEC-009 distribution boundaries: test base and optional-extra profiles separately, and fail if Jenkins/GitHub workflow source appears in installed wheels or runtime bundles.
