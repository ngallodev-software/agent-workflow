# Execution protocol

## 1. Preserve historical meaning

The existing `priority-picker-v1` suite, v1 evaluator, sealed receipts, and reports define the meaning of historical scores. Do not edit old point semantics in place. A changed allocation, check behavior, browser requirement, human-review rule, composite, or winner rule requires a new benchmark major version and new identities.

Original receipts remain immutable. Optional rescoring is additive, versioned, and lineage-linked.

## 2. Use the 0.7.8 owners

Start from `references/LOCATION_DISCOVERY_AND_MAPPING.md`. Verify the current relative paths and record any moved owner before editing. The expected write flow is:

1. corrected suite source under a new sibling of `benchmarks/specs/priority-picker-v1/`;
2. built-in contract/scoring/review/report support under `src/agent_workflow/benchmarking/`;
3. schema additions under `schemas/`;
4. synchronized installed suite under `src/agent_workflow/assets/benchmarks/`;
5. focused acceptance/invariant tests;
6. docs/man/help and release-drift validation.

Do not restore an obsolete path or write new behavior into `agent_workflow.cli` when the dedicated benchmark handler/service owns it.

## 3. Respect the plugin boundary

Benchmarking remains a built-in feature for this correction program. The 0.7.8 plugin API is a trusted top-level-command and digest-bound-resource boundary, not an internal scorer hook framework.

- Do not add a second plugin registry.
- Do not make core benchmark authority depend on an enabled plugin.
- Do not add generic hooks to `plugin_api.py` or `plugins.py` solely for this task.
- Keep pure scoring-contract loading and evaluator-result interpretation isolated from worktree, process, receipt, and review authority so a later ARC-004 extraction remains possible.
- Any future plugin extraction must preserve a fully functional base installation and requires a separate accepted decision and migration pack.

## 4. Contract-first rule

No corrected scorer implementation begins until phase 0 produces an accepted machine-readable contract with:

- unique dimension and check IDs;
- exact per-check maximums and partial-credit semantics;
- exact dimension and 100-point totals;
- evidence producer and evidence reference for each check;
- explicit duplicate-credit decisions;
- benchmark-task, scorer-contract, evaluator, report-schema, fixture, policy, and runtime identities;
- v1 compatibility and mixed-version rejection rules;
- explicit efficiency/winner interaction policy.

The phase-0 decision must also resolve the current `1.1.0` specification versus `1.0.0` matrix contradiction.

## 5. Test discipline

Prefer installed-product and exported-suite journeys. Use compact invariants for arithmetic, schema validation, version separation, evidence integrity, blinding, plugin independence, and mutation isolation.

Required test classes:

- exact contract arithmetic and unique IDs;
- missing, unknown, duplicate, and over-awarded check rejection;
- scorer harness failure versus solution failure;
- full-score golden and frozen partial solutions;
- one controlled mutation per weighted check;
- browser-state, keyboard, visible-focus, responsive, invalid/empty, and verified-download assertions;
- reviewer aggregation and blocking-defect adjudication;
- source/installed-suite byte equivalence;
- mixed-version comparison rejection;
- old v1 report rendering and verification;
- core benchmark commands functioning with `--no-plugins` and with no enabled plugin.

Do not add broad snapshots, private-call choreography, or tests that merely duplicate help text.

## 6. Experimental validity

Keep these concepts separate:

- solution quality points;
- eligibility guardrails;
- human visual scoring;
- efficiency/cost metrics;
- cohort winner/value policy;
- publication eligibility.

A guardrail failure must not become a partial quality score. A missing provider cost must not become zero. Browser runtime attestation must not earn UI-quality points.

## 7. Packaging and drift

`benchmarks/specs/<corrected-suite>/` is the authoring source. `src/agent_workflow/assets/benchmarks/<corrected-suite>/` is the installed/exported mirror. The release audit must compare exact inventories and bytes or generate the mirror deterministically.

Any changed contract must update or generate the matrix, explanation, man-page tables, schema identifiers, example reports, package mirror, and release checks. A wheel installed outside the checkout must export and score the same suite bytes.

## 8. Completion evidence

Use `templates/TICKET_COMPLETION.md`. Every completion includes:

- 0.7.8 path ownership touched;
- old and new benchmark/scorer/evaluator/report versions;
- exact changed semantics;
- tests and installed-product commands with exit status;
- calibration score deltas;
- source/mirror/package digests;
- plugin-independence evidence;
- explicit non-targets;
- unresolved contradictions.

## 9. Independent review

The gate reviewer independently inspects the complete diff and reruns the smallest acceptance set. Reject:

- in-place v1 semantic changes;
- point totals that do not reconcile exactly;
- undocumented duplicate credit;
- weighted checks without controlled mutations;
- browser labels that overstate what is proven;
- treatment identity leaks;
- mixed-version winner calculations;
- source/package suite drift;
- benchmark commands requiring a plugin;
- documentation tables that can diverge silently from the contract.
