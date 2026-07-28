# BKL-001 evidence recovery — 2026-07-28

The original `bkl-001-implementation-luna-20260727` run remains an
`interrupted` historical run. Its placeholder completion sidecar was not
rewritten. A separate structured recovery run was launched against the same
dedicated worktree:

`bkl-001-evidence-recovery-20260728`

## Recreated evidence

Run state:

`/home/nate/.local/state/agent-workflow/runs/bkl-001-evidence-recovery-20260728/`

The recovery produced all required artifact classes:

- valid completion handoff and completion collection;
- sealed `final-receipt.json` (29 sealed artifacts);
- structured provider evidence and execution metrics;
- evaluation runtime, score set, markdown report, and trial collection;
- verified evaluation ledger row;
- baseline/post scope snapshots and sealed-run assessment.

Receipt SHA256: `28ab8523957f97a6885d950e6ffe8599f0aee6d111dd9a9f3750cf73070640c0`

Evaluation plan SHA256:
`73dfa6e3286622df6ba97151206276700b6c8bea32f2693deab221805caae60e`

## Result

The run is not accepted. The durable result is `partial`; lifecycle status is
`failed` with `budget_exhausted` because the provider consumed
`1,155,304` input tokens against the declared `100,000` budget.

Criterion evidence: 15 pass, 3 not verified. The missing evidence includes a
real process restart journey, an independently sealed original-run receipt,
explicit redaction-output evidence, and a separate cursor-deletion exercise.

The exact focused command passed its runner-collected baseline receipt:

```text
python3 -m pytest -q tests/invariants/test_consumer_cursors.py tests/acceptance/test_consumer_cursor_journey.py
6 passed in 12.62s
```

The provider’s later rerun recorded `5 passed, 1 error`: the installed-product
fixture could not install `mcp==1.28.1` from the configured package index. This
environment discrepancy is preserved rather than normalized away. Compileall
passed. The evaluation score is `fail`: `schema_validity=pass`,
`writable_scope=fail` because `.pytest_cache/v/cache/lastfailed` changed outside
the declared scope. BKL-001 remains `ready` in `docs/BACKLOG.md`; no backlog
status was changed by recovery.

The recovery session was terminated through `agent-workflow`; verification
found `tmux_alive=false` and no remaining pane for the recovery session.

## Existing prompt-pack remedies

The failure modes are already addressed by the communication-reliability pack:

- [PROC-001 authoritative preflight](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-001-authoritative-preflight.md)
  requires stable identity, baseline, and scope authority before launch.
- [PROC-002 control handshake](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-002-control-handshake.md)
  requires correlated durable outcomes and prohibits child mutation of a
  read-only parent projection.
- [PROC-003 run observability](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-003-run-observability.md)
  treats silent logs or panes as an observable failure condition and preserves
  retry lineage.
- [PROC-004 completion validation](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-004-completion-validation.md)
  rejects placeholder handoffs and keeps completion, receipt, evaluation, and
  ledger artifacts separate.

The original BKL-001 run failed before these controls could produce complete
evidence. The recovery demonstrates that the controls now create durable
artifacts, but it also exposes two follow-up fixes: bound provider inspection
work to the evaluation budget, and declare test/cache output as disposable or
prevent it from modifying the worktree.

## Final acceptance

The later bounded verification run `bkl-001-completion-verification-20260728-r7`
closed those evidence gaps and was accepted. Its sealed receipt SHA256 is
`347e37c7d292cfaf2f3a27409db7c59584554d9de80679ce7a799efe6a9311d8`.

The run recorded a valid completed handoff, two passing acceptance commands
(8 focused tests and compileall), zero evidence-fidelity contradictions, zero
writable-scope violations, a verified report/trial collection/ledger, and an
accepted lifecycle receipt. The runtime scope collector fix is in commit
`28c2af7`; the BKL implementation remains in `63e953b`.
