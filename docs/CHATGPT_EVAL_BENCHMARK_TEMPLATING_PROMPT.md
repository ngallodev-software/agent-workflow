# ChatGPT developer prompt: evaluation and benchmark templating

Use this prompt with the source archive produced from the `agent-workflow` repository.

## Initial prompt

You are the implementation owner for the next bounded phase of `agent-workflow`.
The repository already contains durable delegation contracts, sealed-run evidence,
two-way messaging foundations, and an interactive-first launch policy. Implement
the missing evaluation and benchmark templating system so that future delegated
runs can be planned, executed, assessed, compared, and recorded consistently.

The earlier starting request was:

> Codify the launch policy: implementation work starts interactively by default;
> exploration, research, and similar work is non-interactive by default. If the
> interactive pane limit is full, report the count and explicitly offer closing
> idle interactive sessions, running a structured non-interactive implementation,
> or cancelling. Do not silently downgrade an implementation launch. Commit and
> push the policy, keep the repository clean, and prepare a detailed handoff for
> implementing evaluation and benchmark templates.

Treat the checked-out source, `docs/BACKLOG.md`, and the selected active prompt-pack
manifest as authoritative. Do not copy ticket status from an archive, overlay, or
external assessment. Do not undo the interactive launch policy, sealed-evidence
contracts, two-way messaging behavior, checksum-ignore policy, or existing user
changes merely to simplify implementation.

## Required discovery and boundaries

Before editing:

1. Read `AGENTS.md`, `docs/BACKLOG.md`, `docs/references/DELEGATION_RUNBOOK.md`,
   and `docs/references/EXECUTION_PROTOCOL.md`.
2. Use codebase-memory-mcp for structural discovery first. If its index is stale,
   refresh or record that limitation before falling back to text search.
3. Read the applicable output standards in `templates/` and any active pack
   `templates/` directory. At minimum, use the schemas and fields in
   `templates/TICKET_COMPLETION.md` and `templates/PHASE_GATE_REPORT.md`.
4. Establish a dedicated implementation worktree, stable ticket/pack identity,
   and an evaluation plan. Keep the coordinator out of ticket implementation.
5. Keep live target collection opt-in and out of unit/e2e tests. Use deterministic
   fixtures and fake providers for tests.

The implementation must remain compatible with the existing process environment
allowlist, RTK command policy, codebase-memory discovery requirement, hook/reminder
layer, and provider evidence rules. `MANIFEST.sha256` and all `*.sha256` files are
transfer/archive artifacts only and must remain ignored by the repository; do not
make a prompt-pack checksum a tracked implementation input.

## Deliverables

Build the smallest complete system that covers these feature surfaces:

- Evaluation-plan template: objective, hypothesis, ticket/pack identity, model and
  provider, cohort, controls, task set, metrics, stopping rules, cost limits,
  privacy constraints, and reproducibility inputs.
- Benchmark/cohort manifest template: stable case IDs, prompt/input digests,
  expected evidence class, oracle/reference identity where applicable, fixture
  provenance, allowed writable scope, and explicit unavailable-data markers.
- Sealed-run assessment template: receipt verification, completion handoff,
  structured stream validation, score/report/collection paths, scope audit, ledger
  row, failures, unresolved contradictions, and accept/reject disposition.
- Benchmark result/report template: baseline/candidate definitions, per-case
  results, aggregate metrics, uncertainty or missingness, token/time/cost data,
  regressions, and reproducible commands.
- Ledger template and renderer inputs: one durable row per run/ticket/case with
  source revision, pack checksum reference, run receipt digest, evaluation result,
  disposition, and evidence paths. Never invent a score when evidence is absent.
- Lifecycle/archive template: retention class, sealed-run export contents,
  transfer checksum instructions, and cleanup/archival status. Checksums may be
  generated beside an archive during transfer but must not be required as tracked
  repository files.

Prefer existing schemas, CLI commands, and rendering patterns. Extend them only
where the templates reveal a real missing contract. Keep generated outputs
deterministic: stable ordering, normalized paths, explicit timestamps/IDs, and no
ambient environment values unless an allowlist records them.

## TDD and end-to-end acceptance

Write tests before or alongside implementation. Add focused unit tests for schema
validation, missing-evidence handling, digest/reference validation, aggregation,
ledger row rendering, deterministic output, and checksum-ignore behavior. Add
end-to-end tests that use a fake structured provider and exercise at least:

1. create and validate an evaluation plan and benchmark manifest;
2. launch or import a sealed structured run;
3. verify receipt, completion handoff, evaluation collection, and writable scope;
4. render an assessment, benchmark report, and ledger row;
5. reject a tampered receipt, mismatched source/pack identity, malformed score,
   missing required evidence, or out-of-scope change;
6. represent an unavailable evaluation as `not_verified`/`unavailable` rather than
   a fabricated pass or score;
7. prove repeated rendering/archive preparation is deterministic;
8. prove `MANIFEST.sha256`/`*.sha256` are not required for repository validation.

Use the repository's supported environment and package metadata so one environment
can build, test, lint/check, install, and verify a release. Do not introduce a
second ad-hoc virtual-environment workflow. Run the focused tests, then the full
release gate and package build. Record exit codes and relevant artifact paths.

## Evidence and completion requirements

Before declaring the phase complete, provide a filled completion report using
`templates/TICKET_COMPLETION.md` and an independent gate report using
`templates/PHASE_GATE_REPORT.md`. The sealed-run acceptance bar is cumulative:

- completion handoff is present and schema-valid;
- sealed receipt is present and verifies against the final evidence;
- structured provider events are available; native TUI text is not evaluation
  evidence;
- evaluation score/report/collection exists, or the result is explicitly marked
  unavailable/not verified;
- writable-scope and source-baseline checks pass;
- the ledger row is written and points to durable local evidence;
- the session is terminated through agent-workflow, and its tmux pane/session is
  confirmed closed;
- no unrelated backlog status is changed.

Include a machine-readable summary when the existing CLI supports it. Report model,
provider, version, source revision, pack identity, run IDs, evidence digests, test
commands, and any blocked/deferred work. Do not claim benchmarks were gathered if
only fixtures were run.

## Stop conditions

Stop and report a concrete blocker if the required MCP/index, provider stream,
receipt, oracle, package dependency, or tmux capacity cannot be made available
without maintainer authorization or a new external choice. Do not bypass evidence
gates, silently convert an implementation launch to interactive/non-interactive,
or mutate an authoritative backlog status to make a gate pass.

At handoff, summarize changed files, tests, release artifacts, unresolved issues,
and the exact next ticket/pack identity. Leave the worktree clean apart from
deliberately ignored transient artifacts.
