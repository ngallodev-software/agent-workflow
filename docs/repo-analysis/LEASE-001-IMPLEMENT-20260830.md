# LEASE-001 implementation

Implement the bounded design in `COMP-001-FINDINGS-20260830.md`: an explicit,
auditable, idempotent retirement action only for unbound external prepared
runs; make durable retirement authority precede name release. Refuse bound,
running, completed, and self-retire cases. Do not add timeout expiry or edit
historical records. Add focused tests, update backlog status, commit, and
publish a valid structured completion.
