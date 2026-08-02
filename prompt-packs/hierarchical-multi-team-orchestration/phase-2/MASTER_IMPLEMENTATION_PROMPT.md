# Phase 2

Implement the team lead as a bounded canonical session and route durable messages across both hierarchy edges.

Implement hierarchy-specific policy and state inside the dedicated hierarchy feature package. Touch core modules only through the smallest stable facade/registration seam required by this phase; direct orchestration must remain the default and must pass unchanged acceptance journeys.
