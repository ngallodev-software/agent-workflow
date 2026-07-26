# Sealed-run assessment completion

## Scope

Completed `CHATGPT-EVAL-001` and `CHATGPT-TDD-001` without implementing HARD/MSG/MCP runtime features.

## Findings

- All six exported completion objects are structurally valid and their bytes match the `completion.json` digest listed in the paired final receipt.
- The export contains only completion/final-receipt pairs. Most receipt-listed artifacts, lifecycle dispositions, evaluation plans, score sets, reports, and trial collections are absent, so full portable seal verification, phase acceptance, and cohort comparability are unavailable.
- A missing evaluation plan remains `missing-plan`; no score, provider usage, or comparison result is fabricated.
- The retained zero-row ledger explanation was incorrect. Ledger rows come from discovered task manifests, not evaluation plans. Zero rows means no task manifests were discovered at the supplied pack root (or the wrong root was supplied); retained evidence cannot distinguish those causes.

## Implementation

- Added `agent-workflow assess-sealed-runs ROOT [--output PATH]`.
- Added evidence-first per-run and collection contracts that separate completion, lifecycle seal portability, evaluation state, phase acceptance, limitations, and comparability.
- Updated ledger rows with `evaluation_required` and `evaluation_state`; an unplanned evaluation no longer recommends `eval score`.
- Added focused invariants and strict future journeys tied to `HARD-004`, `MSG-005`, `BKL-004`, `MCP-003`, and `HARD-007`.
- Updated README, sealed-evidence documentation, backlog, and relevant skills.

## Unresolved

- Full seal verification requires the complete run directories, not the compact exported pairs.
- Phase acceptance requires lifecycle disposition receipts that are not in the assessment pack.
- No evaluation plan, score set, report, trial collection, or provider-usage conclusion exists for these six runs.
- The original ledger invocation/path was not retained, so the exact zero-row operational cause cannot be narrowed beyond manifest discovery failure.

## Verification commands

| Command | Exit | Result |
|---|---:|---|
| `bash scripts/validate-pack.sh` (assessment pack, before repository install) | 1 | Environment limitation: `/opt/pyvenv/bin/python3: No module named agent_workflow`. |
| `PYTHONPATH=src python -m agent_workflow assess-sealed-runs ... --output /tmp/sealed-assessment.json` | 0 | 6 runs; 6 valid completions; 0 portable full-seal verifications; 0 comparable runs. |
| `python -m pytest -q tests/invariants/test_sealed_run_assessment.py tests/invariants/test_ledger_evaluation_semantics.py tests/future` | 0 | 5 passed, 5 expected strict xfails in the original assessment run; independent review reran 7 focused tests, 5 expected strict xfails. |
| `python scripts/audit-release-assets.py` | 0 | Release assets valid; mutable checksum manifests are not required. |
| `python -m pytest -q` | 2 | Environment limitation during collection: optional `mcp` package unavailable. |
| `bash scripts/release-check.sh` | 2 | Reached the same optional-`mcp` collection limitation after release-asset validation. |

## Independent later phase gate

A later reviewer must use complete run directories to verify every sealed artifact, verify immutable lifecycle dispositions independently from completion, confirm any evaluation plan/score/report/trial collection as a complete matched set, rerun installed-wheel acceptance with the MCP extra available, and ensure future tests are still strict expected failures until their owning runtime work and prerequisites are accepted.

## Independent overlay review

The overlay was applied from `agent-workflow-0.2.3-chatgpt-sealed-run-assessment-changes-20260726.tar.zst`. Review found and corrected one evidence-classification defect: receipt-listed evaluation artifacts now count as present only when the exported files are actually present, and completion validity requires a receipt digest. The focused rerun passed 7 tests with 5 strict expected failures; the live export assessment remains 6 valid completions, 0 portable seals, and 0 comparable runs. This review accepts the assessment changes with the unresolved lifecycle/evaluation follow-ups above; it does not accept the deterministic-foundation runtime phase.
