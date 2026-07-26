# ChatGPT sealed-run assessment review — 2026-07-26

## Decision

Accepted with follow-up for `CHATGPT-EVAL-001` and `CHATGPT-TDD-001`. The deterministic-foundation runtime phase remains rejected pending complete lifecycle evidence, immutable disposition evidence, and shared installed-product acceptance.

## Overlay provenance

- Input: `agent-workflow-0.2.3-chatgpt-sealed-run-assessment-changes-20260726.tar.zst`
- Applied against: `d5a1980` on `master`
- Changed surfaces: exported-run assessor, ledger semantics, CLI, evidence/backlog/docs, skills, and focused/future tests
- Full-tree overlay manifest was not copied; repository `MANIFEST.sha256` was regenerated after merge.

## Independent evidence

The assessor was rerun against `prompt-packs/chatgpt-sealed-run-assessment/references/sealed-runs`:

| Measure | Result |
|---|---:|
| Exported runs | 6 |
| Valid completion digests | 6 |
| Portable lifecycle seals | 0 |
| Comparable evaluation cohorts | 0 |
| Evaluation state | `missing-plan` for all six |

The compact export proves completion-object digest matches where the paired receipt lists it. It does not prove the complete lifecycle seal or phase acceptance because the receipt-listed run artifacts and disposition evidence were not exported. The prior zero-row ledger result cannot be attributed to missing evaluation plans; ledger rows depend on discovered task manifests, and the original invocation/root was not retained.

## Review correction

Receipt-listed-but-absent evaluation files were initially counted as present by the overlay assessor. The implementation now requires actual exported `evaluation-runtime.json`, score-set, report, and trial files. Completion validity also requires an actual receipt digest match.

## Verification

- `python3 scripts/audit-release-assets.py`: passed.
- Focused assessment/ledger/future tests: `7 passed, 5 strict xfailed`.
- Live assessor: `6 valid completions, 0 portable seals, 0 comparable runs`.
- Existing future tests remain strict expected failures for `HARD-004`, `MSG-005`, `BKL-004`, `MCP-003/HARD-007`, and `BKL-002`.

## Follow-up required

1. Retain complete run directories or an independently verifiable portable seal bundle.
2. Export lifecycle disposition/phase-gate evidence separately from completion receipts.
3. Supply matched evaluation plans, score sets, reports, trial collections, and provider evidence before claiming comparability.
4. Keep future tests strict until their owning runtime implementation and phase gates are accepted.
