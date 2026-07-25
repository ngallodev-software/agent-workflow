# BKL-003-RESEARCH — provider evidence and usage envelope

Perform a bounded research phase before implementation. Read
`BACKLOG.md`, `docs/Durable_Orchestration_Delivery_Benchmarks.md`,
`docs/ORCHESTRATOR_MESSAGING_AND_EVALS_PLAN.md`, `docs/ARCHITECTURE.md`, the
current executor adapters, event schemas, receipts, and evaluation code.

Verify current official primary-source behavior for every supported executor
and model surface that can emit usage, cost, retry, or stream events. Record
source URLs/access dates and distinguish facts from inference. Define the
minimum evidence contract for raw immutable provider events and sealed hashes;
`delta`, `cumulative`, and `terminal` usage semantics; cached/reasoning/input/
output token fields; retries, restarts, duplicate events, missing telemetry,
and partial runs; provider-billed versus locally estimated cost, currency,
price-catalog version, and unknown/null handling; and schema compatibility
and comparison exclusions.

Produce a durable research memo and implementation checklist. Do not change
runtime behavior in this ticket. Validate references and run only read-only
structural checks. Stop if a required provider fact cannot be verified;
document the gap instead of inventing a value.

Completion requires a valid handoff, exact commands, source list, explicit
open questions, and an independent research review before BKL-003 begins.

Writable paths: research memo, evidence references, and directly related
planning documentation only. Acceptance: cited primary sources, explicit
facts/inferences/open questions, and no runtime changes. Stop on unverifiable
provider claims. Tests: validate the pack, verify every cited reference path,
and run the repository’s read-only structural checks.
