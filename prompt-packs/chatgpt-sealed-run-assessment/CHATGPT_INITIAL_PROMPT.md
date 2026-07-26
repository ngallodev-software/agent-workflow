# ChatGPT initial prompt

You are assessing the `agent-workflow` repository as an independent evidence and test-design reviewer. Current source, `BACKLOG.md`, sealed run artifacts, and public contracts are authoritative.

## Prior starting prompt

Treat current source, [`BACKLOG.md`](../../docs/BACKLOG.md), the [feature assessment](../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md), and the [hardening plan](../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md) as authoritative.

1. Run the deterministic release drift audit and validate this pack.
2. Confirm all external prerequisites and prior phase gates.
3. Launch independent tickets concurrently only when the manifest has no dependency edge between them; use separate worktrees and durable sessions.
4. Require installed-product acceptance evidence first and retain only compact security/state invariant matrices.
5. Integrate completed tickets, rerun shared journeys, then delegate the gate to an independent reviewer using both `phase-gate-review` and `release-drift-auditor`.
6. Stop on backlog ownership collisions, newer conflicting architecture, missing security prerequisites, or guidance that is being mislabeled as deterministic enforcement.

Do not add an alternate scheduler, daemon, database, web UI, remote transport, memory layer, persona taxonomy, autonomous routing, or unrelated cleanup.

## New continuation mission

Analyze the sealed evidence in `references/sealed-runs/` and `references/sealed-run-evidence.md`, together with the current evaluation implementation and the empty ledger in `references/deterministic-foundation-ledger.tsv`.

1. Determine which evidence contracts are present, missing, contradictory, or not comparable. Explicitly distinguish completion validity, lifecycle sealing, evaluation score/report/collection, ledger rows, and phase acceptance.
2. Update the evaluation system only where the sealed evidence demonstrates a real contract gap. Add evidence-first schemas, collectors, scorers, reports, or focused tests as needed; do not invent scores or provider usage.
3. Preserve unavailable evidence and environment limitations as explicit outputs. A missing evaluation plan must remain a missing evaluation plan.
4. After the eval-system changes are reviewed, generate strict TDD installed-product journeys under `tests/future/` for future planned work, including deterministic hardening follow-ups and orchestrator messaging. Tie each test to the relevant backlog ID and make it an honest `xfail(strict=True)` until the implementation and acceptance prerequisites exist.
5. Update only the relevant backlog/docs/pack manifests and include a completion report with exact commands, exit codes, changed files, evidence references, and unresolved issues.

Do not implement the planned HARD/MSG runtime features in this assessment pack. Do not mark future tests as passing. End with a concise assessment of what a later independent phase gate must verify.
