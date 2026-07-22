# Agent Evaluation, Correctness, and Usability Improvement Plan

Status: implemented locally; external benchmark and telemetry lanes remain opt-in
Prepared: 2026-07-17
Primary objective: measure and improve delegated-agent performance without turning `agent-workflow` into a bespoke evaluation platform.

Implementation note (2026-07-17): Phase 0 deterministic contracts, collectors, sealing, scoring, oracle boundary, file-backed reports, and Inspect seam are present. Phase 1 lifecycle/comparison/diagnostic controls and Phase 2 optional SWE-bench, OpenTelemetry, and MLflow seams are also present. Paid Inspect trials, official SWE-bench dataset runs, and shared telemetry services remain operator-run validation lanes rather than release prerequisites.

## Executive recommendation

Keep `agent-workflow` responsible for what it already does well: isolated worktrees, durable prompts and commands, tmux-backed execution, lifecycle control, source provenance, and persistent run evidence. Integrate established evaluation systems around those artifacts instead of building a new dataset engine, trace backend, judge framework, statistics package, or web UI.

Recommended stack:

1. **Inspect AI as the primary evaluation harness after a topology/reuse spike.** Use its tasks, datasets, scorers, metrics, sandboxes, eval sets, log files, log viewer, Agent Bridge, and existing Inspect SWE Codex/Claude agents. Implement only the missing glue selected by an explicit sandbox-boundary ADR.
2. **Existing deterministic tools as first-line scorers.** Consume pytest/JUnit XML, Ruff, ShellCheck, JSON Schema, Git diff data, and optional Semgrep/Bandit/Gitleaks results before using an LLM judge.
3. **SWE-bench's official harness for standardized coding-agent comparison.** Do not reproduce its container construction, patch application, or grading logic.
4. **OpenTelemetry for optional trace export.** Map lifecycle and executor events onto existing GenAI/agent span conventions rather than inventing a telemetry vocabulary.
5. **Inspect logs initially; MLflow only when longitudinal experiment tracking needs a shared service/UI.** Avoid operating two stores before there is a real multi-user requirement.

The most valuable first release is not a dashboard. It is a reproducible local eval set with deterministic scorers, fair run controls, complete provenance, and a regression command that produces an Inspect log plus a concise Markdown/JSON summary.

## Current repository baseline

The current architecture already supplies most raw material required for evaluation:

- [`sessions.launch`](../src/agent_workflow/sessions.py) copies and hashes prompt evidence at launch and creates generated launch context, command receipts, source baselines, logs, and completion reports. It does not yet seal or revalidate those files after execution.
- [`sessions.observe`](../src/agent_workflow/sessions.py) combines durable lifecycle state with tmux liveness and log-growth observations.
- [`manifests.validate_pack`](../src/agent_workflow/manifests.py) validates pack structure, prompt containment, task identity, order-list membership, and checksum completeness. It does not yet enforce dependency or execution-order semantics.
- [`state.py`](../src/agent_workflow/state.py) provides atomic durable status records.
- [`templates/TICKET_COMPLETION.md`](../templates/TICKET_COMPLETION.md) already asks agents to report changed files, acceptance criteria, tests, unresolved issues, and scope drift.
- [`docs/MODEL_TIERS.md`](MODEL_TIERS.md) defines task risk/reasoning tiers without coupling them to vendor model names.
- [`docs/TEST_POLICY.md`](TEST_POLICY.md) correctly prefers contract-driven tests over coverage theater.

What is missing is a scoring and comparison layer. Runs can currently transition through execution outcomes such as completed or failed. `accepted` and `rejected` are reserved status values, but no CLI review/acceptance transitions exist yet. The repository does not yet answer:

- How often does an executor solve the same class of ticket on the first attempt?
- Which agent is more reliable at the same budget and base revision?
- Did the agent respect writable scope, report its work truthfully, and avoid regressions?
- How much wall time, model usage, operator intervention, and retry cost did success require?
- Is a prompt-pack revision measurably better, or merely different?
- Did a new model or CLI version improve median behavior while worsening tail failures?

## Evaluation principles

### Deterministic evidence before model judgment

Tests, schema validation, diff boundaries, command receipts, exit codes, and source revisions are stronger evidence than a judge model's opinion. LLM graders should assess only criteria that cannot be resolved deterministically, such as architectural coherence, explanation quality, or whether a narrow implementation genuinely satisfies an underspecified intent.

### Evaluate the system, not only the final patch

The evaluated unit is the combination of task, prompt pack, agent/executor, model, CLI version, configuration, base revision, environment, allowed tools, budget, and review policy. Reporting only “model X solved task Y” hides the variables most likely to explain a result.

### Preserve blind and fair comparisons

Graders should not see executor names, model labels, or expected winners. Comparative trials should use the same base commit, prompt bytes, worktree state, tool availability, budget, timeout, and acceptance commands. Trial order should be randomized when shared infrastructure or rate limits could bias later runs.

### Separate development, validation, and holdout tasks

Prompt authors will overfit if every failure becomes a visible training example. Maintain a development set for iteration, a validation set for release gating, and a holdout set reviewed on a slower cadence. Public task inputs may live in the repository; holdout oracles, labels, reference patches, and hidden tests must remain in evaluator-only storage outside the agent-visible checkout and sandbox. External benchmarks must never replace repo-specific holdouts.

### Prefer distributions over anecdotes

One successful smoke run establishes connectivity, not agent quality. Report repeated trials, medians, tail latency, confidence intervals, and failure categories. Preserve individual receipts so aggregate metrics remain auditable.

## Prioritized roadmap

| Priority | Improvement | Primary value | Reuse instead of rebuild |
|---:|---|---|---|
| P-1 | Inspect topology and reuse spike | Select viable sandbox boundary | Inspect Agent Bridge and Inspect SWE Codex/Claude agents |
| P0 | Separate JSON eval contract | Reproducible agent scoring | JSON Schema instance validation and Inspect task config |
| P0 | Inspect AI adapter after topology decision | Reproducible agent scoring | Inspect tasks, datasets, scorers, logs, Agent Bridge |
| P0 | Deterministic scorer bundle | Correct, cheap pass/fail signals | pytest/JUnit, Ruff, ShellCheck, JSON Schema, Git |
| P0 | Complete provenance and budget capture | Fair comparisons | Existing receipts plus executor JSON/stream output |
| P0 | Repo-specific golden eval set | Detect real regressions | Inspect datasets and Docker/git fixtures |
| P0 | Evidence-fidelity and scope scorers | Measure trustworthy agent behavior | Git, completion schema, test receipts |
| P1 | Repeated-trial comparison reports | Separate signal from variance | Inspect eval sets/metrics; SciPy or statsmodels if needed |
| P1 | Recovery and fault-injection evals | Measure operational robustness | pytest fixtures, pytest-subprocess, pytest-timeout |
| P2 | Standardized SWE-bench lane | External comparability | Official SWE-bench harness and images |
| P2 | OpenTelemetry export | Cross-tool trace interoperability | OTel SDK, Collector, GenAI semantic conventions |
| P2 | Shared experiment tracking | Longitudinal/team comparison | MLflow tracking and agent evaluation |
| P2 | Operator UX improvements | Faster diagnosis and fewer mistakes | tmux primitives, argcomplete/shtab, existing log viewers |

## Evaluation improvements

### E0. Resolve Inspect topology and existing-adapter reuse first

**Problem.** `agent-workflow` currently launches host tmux sessions and host worktrees. An Inspect sandbox has its own filesystem, process namespace, environment, and artifact boundary. A host launcher cannot safely assume it can operate on an Inspect-owned sandbox path, while installing the full workflow inside the sandbox changes where tmux, XDG receipts, API routing, patches, and logs live. Choosing an adapter before resolving this boundary risks building an integration that cannot preserve either system's guarantees.

**Recommendation.** Run a short Phase -1 spike comparing these concrete options:

1. **Reuse Inspect SWE agents as the benchmark baseline.** Run the existing Inspect SWE Codex CLI and Claude Code agents unchanged. This establishes expected bridge behavior, sandbox images, API routing, patch extraction, and transcript quality before `agent-workflow` is added.
2. **Compose with existing Inspect SWE adapters where possible.** Determine whether their CLI setup/bridge code can be wrapped or configured to invoke an `agent-workflow` runner rather than duplicated. Reuse their Dockerfiles, CLI installation, `sandbox_agent_bridge()` setup, and patch-return conventions when compatible.
3. **Run `agent-workflow` inside the Inspect sandbox.** Install `agent-workflow`, tmux, Git, and the selected CLI into the sandbox image. Invoke it through Inspect's `sandbox_agent_bridge()` and `sandbox().exec()`. Route model APIs through the bridge proxy (for example `OPENAI_BASE_URL` or `ANTHROPIC_BASE_URL` on the bridge's localhost port). Keep worktrees and XDG run receipts inside the sandbox, then explicitly copy the patch and sealed receipt bundle into the Inspect eval log/artifacts before teardown.
4. **Reject host-to-sandbox path control unless proven safe.** Do not let a host `agent-workflow` process manipulate an opaque sandbox worktree. Consider this topology only if the selected Inspect sandbox exposes a supported host path with equivalent isolation and artifact semantics.

The spike must document process/filesystem boundaries, network/API bridge variables, model accounting, tmux behavior, XDG location, patch transfer, receipt extraction, cleanup, and failure recovery for both Codex and Claude. The output is a short ADR selecting one topology and listing which Inspect SWE components are reused unchanged, wrapped, or deliberately not used.

**Acceptance gate.** One tiny task completes through each viable topology candidate; its model calls appear in the Inspect transcript, its patch is returned, and its `agent-workflow` receipt bundle survives sandbox teardown. The ADR selects a topology before E1 implementation begins.

### E1. Make Inspect AI the evaluation control plane

**Problem.** Building a local dataset loader, repetition scheduler, scorer interface, result schema, log viewer, and model-judge pipeline would duplicate mature functionality and create a second orchestration system to maintain.

**Recommendation.** After E0 selects a topology, add an optional `evals/` integration package that exposes `agent-workflow` as an Inspect agent through the selected Inspect bridge. Start from the existing Inspect SWE Codex/Claude agent implementations and retain their bridge, sandbox, and transcript machinery where possible. The adapter should:

1. receive public task input from an Inspect sample while evaluator-only oracle data remains outside the agent sandbox;
2. create or restore the fixture through Inspect's sandbox policy;
3. establish the API bridge using `sandbox_agent_bridge()` and invoke sandbox commands with `sandbox().exec()`;
4. invoke the sandbox-installed `agent-workflow launch` with a unique session ID and selected CLI executor;
5. poll machine-readable session status inside the sandbox rather than scrape terminal output;
6. finalize and seal the receipt bundle, export it and the patch before sandbox teardown, and attach both to the Inspect sample log;
7. let Inspect run one or more host-side scorers and own the canonical eval log.

The adapter should not implement retries, datasets, score aggregation, or a custom UI. Those remain Inspect responsibilities. `agent-workflow` remains the execution/evidence backend.

**Suggested layout.**

```text
evals/
├── README.md
├── inspect_agent_workflow.py
├── tasks/
│   ├── repo_contracts.py
│   └── recovery.py
├── scorers/
│   ├── deterministic.py
│   ├── evidence_fidelity.py
│   └── scope_compliance.py
└── datasets/
    ├── development.jsonl
    ├── validation.jsonl
    └── public-holdout-inputs.example.jsonl
```

Evaluator-only holdout oracles are deliberately absent from this tree. They belong in a separately permissioned host/CI location mounted only for scoring after the agent exits.

**Acceptance gate.** One command runs the same three local fixture tasks against both configured executors in the selected topology, produces valid Inspect eval logs, preserves bridge-captured model calls plus sealed workflow receipts, and can be reopened in Inspect's log viewer without converting formats.

### E2. Define a thin, versioned evaluation contract

**Problem.** Ticket manifests describe execution but not the evaluation oracle, repetition policy, budget, or comparison cohort. Encoding those details only in shell scripts makes results irreproducible.

**Recommendation.** Do not add nested `evaluation:` YAML to `task-manifest.yaml` in the first version. The built-in fallback parser supports nested mappings only under `tasks`; evaluation JSON is validated separately with the established `jsonschema` package.

Use a separate versioned `evals/evaluation.json` file validated as a JSON Schema instance. This avoids expanding the fallback YAML parser, keeps the core small, and maps cleanly onto Inspect task/eval-set configuration. Add an optional scalar `evaluation_file` reference only if prompt packs must discover the file; the fallback parser can already handle a top-level scalar.

Example:

```json
{
  "schema": "agent-workflow/evaluation-plan/v1",
  "dataset_split": "validation",
  "task_ids": ["P0-00"],
  "repetitions": 3,
  "timeout_seconds": 1800,
  "max_retries": 0,
  "scorers": [
    "acceptance_commands",
    "writable_scope",
    "regression_guard",
    "evidence_fidelity"
  ],
  "budgets": {
    "max_wall_seconds": 1800,
    "max_input_tokens": 200000,
    "max_output_tokens": 30000
  },
  "sandbox": "docker"
}
```

Only fields used by the first integration should be admitted. Add explicit instance validation in `pack validate` or a new `eval validate` path using `jsonschema`; testing only `check_schema()` is insufficient. If future requirements genuinely need nested YAML, either make PyYAML an explicit eval extra or extend and test the fallback parser before changing the format. Keep vendor-specific model names in the eval run configuration, not in prompt packs; this preserves the current tier abstraction.

**Acceptance gate.** Ordinary task manifests still validate offline; malformed evaluation JSON fails schema-instance validation; and two evaluators given the same pack, base revision, executor configuration, and dataset split produce equivalent trial plans before any model call occurs.

### E3. Build deterministic scorers first

**Problem.** A single “tests passed” bit misses scope violations, pre-existing failures, unreported regressions, and dishonest completion claims. Conversely, using an LLM judge for objective properties adds cost and nondeterminism.

**Recommendation.** Implement Inspect scorers that wrap existing tools and receipts:

| Scorer | Evidence | Output |
|---|---|---|
| Acceptance commands | Declared commands plus JUnit/exit receipts | pass/fail per criterion |
| Regression guard | Baseline vs post-change test results | introduced/fixed/unchanged failures |
| Writable scope | Complete base/index/worktree/untracked repository delta | violation count and paths |
| Patch applicability | Clean apply against recorded base | pass/fail |
| Repository cleanliness | Git state after completion | expected/unexpected residue |
| Schema validity | `check-jsonschema` or Python `jsonschema` | errors by artifact |
| Static quality | Ruff, ShellCheck, optional mypy | normalized findings |
| Security hygiene | Semgrep/Bandit/Gitleaks where relevant | new findings only |
| Completion presence | Structured completion artifact | pass/fail |
| Evidence fidelity | Claimed commands/files vs receipts/diff | precision, recall, contradictions |

Prefer machine outputs: JUnit XML, JSON, SARIF, and Git's NUL-delimited formats. Do not parse pretty terminal text when the tool has a stable structured output.

The writable-scope collector must union all relevant states, not only the default worktree diff:

- committed changes from recorded base to `HEAD` via `git diff --name-status -z --find-renames BASE..HEAD`;
- staged changes via `git diff --cached --name-status -z --find-renames`;
- unstaged changes via `git diff --name-status -z --find-renames`;
- untracked files via `git ls-files --others --exclude-standard -z`;
- ignored files from both pre-run and post-run `git ls-files --others --ignored --exclude-standard -z` inventories, using the union of both path sets so a changed `.gitignore` cannot hide a file;
- submodule state and dirtiness via `git submodule status --recursive` plus per-submodule deltas;
- nested repositories discovered from `.git` directories/files, each evaluated against its own recorded base;
- both old and new paths for renames/copies, canonicalized relative to the correct repository root.

Git alone cannot reveal mutation of an ignored file that existed before the run. Prefer the Inspect/Docker sandbox's filesystem-layer delta when it is available. Otherwise combine the ignored-path inventory with pre/post size, mode, and SHA-256 receipts for policy-relevant ignored/protected paths. On Linux, use an established process-tree write tracer such as [fsatrace](https://github.com/jacereda/fsatrace) or a narrowly configured [strace](https://strace.io/) as a corroborating signal rather than building a file watcher. Exclude known disposable cache roots only through an explicit, versioned policy; never blanket-exclude `.env`, credentials, workflow receipts, or configuration.

The collector must record ignored/generated-policy decisions explicitly, distinguish expected `.git` metadata writes from worktree content changes, and reject paths that cannot be canonicalized inside an authorized repository root.

**Acceptance gate.** Every deterministic score links to a sealed local receipt. Scope fixtures cover committed changes, staged changes, unstaged changes, untracked files, pre-existing and newly created ignored files, `.gitignore` changes, renames, submodules, and nested repositories. Re-running scorers without rerunning the agent produces identical results.

### E4. Add a structured completion sidecar

**Problem.** [`TICKET_COMPLETION.md`](../templates/TICKET_COMPLETION.md) is useful for humans but expensive and fragile to parse. It cannot reliably support evidence-fidelity scoring, aggregation, or schema migration.

**Recommendation.** Preserve the Markdown report, but add `completion.json` conforming to a versioned JSON Schema. Generate an empty sidecar at launch, expose its durable path in the launch context, and validate it before accepting a run. Fields should include:

- ticket, pack, session, base revision, and head revision;
- result and explicit unresolved conditions;
- changed-file list;
- acceptance-criterion results with receipt paths;
- test commands, exit codes, start/end timestamps, and output receipt hashes;
- claimed non-goals and scope exceptions;
- agent-reported token/cost information when available.

Use the existing Markdown template as the human narrative; render summary tables from JSON where helpful. Use the standard `jsonschema` package or `check-jsonschema` CLI for validation rather than another home-grown parser.

**Acceptance gate.** A completion report with an invented test command, incorrect exit code, or missing receipt fails evidence-fidelity validation even if its prose sounds plausible.

### E5. Capture complete run provenance and resource usage

**Problem.** Prompt and source hashes are recorded, but fair agent comparison also requires model identity, CLI version, effective executor argv, environment, tool versions, budgets, and usage.

**Recommendation.** Extend run evidence with a versioned `run-provenance.json` populated before launch and finalized after exit. Capture:

- executor name and exact argv;
- executor CLI version and model identifier reported by structured output;
- prompt, launch prompt, config, and pack manifest hashes;
- source revision, branch, dirty state, patch hash, and worktree path;
- Python, OS, tmux, Git, tar, zstd, test-tool, and container-image versions;
- start, first-output, last-output, and finish monotonic timestamps;
- input/output/cached/reasoning tokens when exposed;
- estimated or reported cost, with currency and pricing-source date;
- operator interventions, interrupts, restarts, and retry lineage;
- allowed tools, sandbox mode, writable roots, timeout, and budget.

Codex can emit JSONL with `exec --json`; Claude can emit structured streaming output with `--print --output-format stream-json`. Add executor-specific parsers behind a small adapter interface and preserve the raw stream. Never infer token or cost values from terminal prose when structured events are available.

Add an explicit finalization/sealing step after the executor exits and all post-run collectors finish. Write `final-receipt.json` containing paths, sizes, and SHA-256 hashes for the original prompt, launch prompt, command, source baseline, raw structured event stream, output log, completion Markdown/JSON, provenance, patch, and collector outputs. After sealing:

- listed run artifacts are read-only inputs to scorers;
- any hash mismatch makes the trial invalid rather than silently rescoring changed evidence;
- mutable `status.json` remains an operational snapshot and is either excluded from the seal or represented by a separately frozen final-status receipt;
- reviewer, acceptance, rejection, and score receipts are append-only downstream records that reference the final-receipt hash;
- the Inspect adapter exports the entire sealed bundle before sandbox teardown.

**Acceptance gate.** A comparison report refuses to aggregate trials whose base revision, prompt hash, acceptance commands, sandbox, or budget differ unless the user explicitly requests an unpaired analysis. Mutating any sealed artifact after finalization invalidates the trial and cannot change a prior score silently.

### E6. Establish a repo-specific golden evaluation set

**Problem.** External benchmarks cannot measure this repository's distinctive requirements: writable-scope discipline, completion-report fidelity, worktree isolation, recovery controls, and prompt-pack comprehension.

**Recommendation.** Create small, deterministic Git fixtures representing common ticket classes:

1. one-file correctness bug with a clear regression test;
2. multi-file bounded feature with explicit writable paths;
3. stale documentation claim requiring source verification;
4. manifest/path traversal defect;
5. dirty-worktree stop condition;
6. ambiguous requirement that should trigger a stop/escalation rather than a guess;
7. task with a tempting but forbidden unrelated cleanup;
8. failing baseline test that must not be attributed to the agent;
9. interrupted run that must resume or restart without losing evidence;
10. malicious or misleading repository text that should not override the ticket's authority boundary.

Each fixture should have an evaluator-only oracle: acceptance commands, permitted patch envelope, known failure categories, and optional reference patch. Use small repositories or Git bundles so setup is fast and exact. Use Docker/Inspect sandboxes for tasks that need process or dependency isolation.

Keep public task inputs and evaluator-only oracle material in different stores and access domains:

- the agent sandbox receives only the public fixture, prompt, and allowed references;
- hidden tests, labels, reference patches, scorer rubrics, and holdout metadata stay on the Inspect host or in separately permissioned CI storage;
- host-side scorers receive the oracle only after the agent process ends and never copy it into the sandbox, prompt, environment, transcript, or exported worktree;
- dataset manifests store hashes/IDs for cohort reproducibility without embedding secret oracle content;
- periodic leakage checks search prompts, receipts, model transcripts, and repository history for holdout-only canaries;
- contaminated tasks are retired from holdout metrics and recorded as development examples rather than quietly retained.

Do not make the reference patch the only accepted output. Score behavior and contracts, not textual patch similarity.

**Acceptance gate.** Every fixture fails at least one intentionally broken baseline agent or no-op baseline and passes a validated reference solution. A sandbox inspection test proves holdout oracle files and canaries are unreadable to the agent. This prevents “always pass” scorers and oracle leakage.

### E7. Add standardized SWE-bench evaluation without forking the harness

**Problem.** Repo-specific fixtures provide relevance but not external comparability. Reimplementing benchmark environments would be expensive and error-prone.

**Recommendation.** Add a separate optional lane that:

- uses the official SWE-bench dataset and `swebench.harness.run_evaluation`;
- lets the official Docker harness apply patches and determine resolved status;
- uses `agent-workflow` only to produce patches and preserve process evidence;
- starts with a small pinned subset of SWE-bench Lite or Verified for routine development;
- reserves larger runs for scheduled evaluation because of compute and cost.

Record benchmark dataset revision, instance IDs, harness version, image digests, and prediction file hash. Keep benchmark scores separate from repo-specific evals; they answer different questions.

**Acceptance gate.** A generated prediction file is accepted unchanged by the official harness, and the stored resolved/unresolved result matches the harness output.

### E8. Measure agent behavior, not just task success

**Problem.** Two agents can both pass tests while differing dramatically in cost, scope discipline, recoverability, and reviewer burden.

**Recommendation.** Report five metric families:

**Outcome**

- pass@1 and accepted@1;
- pass@k for explicitly permitted retries;
- regression-free success;
- partial/blocked/failure classification accuracy.

**Efficiency**

- wall time, time to first output, and time to first valid patch;
- input, output, cached, and reasoning tokens;
- estimated cost;
- test invocations, repeated failed commands, and retry count;
- patch size and files touched.

**Behavior quality**

- writable-scope violations;
- unrelated edits;
- unnecessary compatibility layers or tests;
- correct use of required reading and references;
- destructive-command attempts and policy denials;
- operator interventions.

**Evidence quality**

- completion-report schema validity;
- claim-to-receipt precision and recall;
- unreported failures;
- incorrect file/test claims;
- provenance completeness.

**Robustness**

- success after controlled interruption;
- behavior with unavailable commands, dirty worktrees, or stale refs;
- variance across repetitions;
- sensitivity to harmless prompt formatting changes;
- tail latency and stall rate.

Do not collapse these into one opaque “agent score.” Present a small primary scorecard and preserve the component metrics. A weighted composite may be useful for gating, but its formula and weights must be versioned and visible.

**Acceptance gate.** A stored trial can regenerate every scorecard value from receipts, includes all failed and interrupted attempts, and cannot be promoted by a composite score when deterministic correctness or scope compliance fails.

### E9. Use statistically defensible comparisons

**Problem.** Agent performance is stochastic. Comparing one run per model rewards luck and encourages overclaiming.

**Recommendation.** For normal development:

- use three repetitions per task/configuration only as a connectivity/variance smoke; report raw trials and medians, not tail percentiles or release significance;
- use at least 10 paired trials per configuration for a routine validation comparison and increase sample size when the expected difference is small or variance is high;
- report p90 only with at least 20 observations and p95 only with at least 40; below those counts, report median, range, and individual trials;
- pair trials by task/base/prompt/budget;
- randomize execution order;
- report pass counts and 95% Wilson intervals for binary metrics;
- use paired bootstrap 95% intervals for score, median time, token, and cost differences;
- include all failed, timed-out, interrupted, and invalid trials in denominators;
- predeclare the primary metric, sample size, non-inferiority margin, minimum effect of interest, and stop rule before running an expensive comparison;
- treat timeout, missing output, invalid receipt, and budget exhaustion as failures for outcome metrics; exclude only independently confirmed harness/infrastructure failures, allow at most one replacement run, and report every exclusion;
- compare against a pinned accepted baseline using the identical cohort/scorer versions; use a rolling historical window only for descriptive drift charts, not release-gate substitution.

Default starting gates, configurable only through a versioned eval policy:

- deterministic correctness, writable scope, and evidence integrity: zero-tolerance failures;
- deterministic pass@1: lower bound of the paired 95% difference interval no worse than -5 percentage points versus baseline;
- median wall time and reported cost: the upper bound of the paired bootstrap 95% interval for relative regression `(candidate / baseline) - 1` must be at most +15%; an interval that includes zero does not waive this bound;
- p95 wall time/cost, only when each cohort has at least 40 observations: the upper bound of the paired bootstrap 95% interval for relative p95 regression must be at most +20%;
- no “winner” label unless the interval excludes the configured non-inferiority/equivalence region and the minimum effect of interest is met.

Use Inspect's metrics and aggregation first. If additional statistics are needed, use SciPy or statsmodels rather than implementing interval and hypothesis-test math locally.

**Acceptance gate.** The comparison report includes trial counts, minimum-N eligibility for each statistic, confidence level, margins, baseline/scorer versions, exclusions with reasons, timeout/missing-result handling, and the exact cohort definition. It never reports p90/p95 below the minimum N or declares a winner from a single trial.

### E10. Calibrate model graders instead of trusting them by default

**Problem.** Model graders can be biased by verbosity, executor identity, style, or their own architectural preferences. They can also agree with a polished but false completion report.

**Recommendation.** Use Inspect or MLflow scorers for qualitative grading only after deterministic evidence is attached. Build a human-labeled calibration set containing strong, weak, deceptive, partially correct, and scope-violating patches. Then:

- blind executor/model identity;
- provide a criterion-specific rubric and deterministic receipts;
- grade each criterion separately;
- require a short evidence citation, not unrestricted chain-of-thought;
- measure agreement with human labels and between independent graders;
- investigate systematic disagreement by failure category;
- version grader prompts and model revisions;
- use multiple graders or human review for high-risk gates;
- periodically re-score the frozen calibration set after model updates.

Never let a model judge override a deterministic failing acceptance test. Record both results if the qualitative assessment still adds context.

**Acceptance gate.** A grader must meet a declared agreement threshold on the frozen calibration set before its scores can block or promote a release.

### E11. Add recovery and fault-injection evaluations

**Problem.** Current happy-path success does not measure orphaned sessions, terminal failures, interrupts, retries, full disks, missing executors, corrupt status, or stalled processes—the cases where durable workflow tooling matters most.

**Recommendation.** Build deterministic fault fixtures with pytest and existing process-test helpers. Consider `pytest-subprocess` for command simulation and `pytest-timeout` for deadlock protection. Cover:

- tmux launch fails after evidence directory creation;
- executor binary disappears between preflight and runner start;
- runner exits before marking `running`;
- output stops while process remains alive;
- status JSON is truncated or has an unsupported schema version;
- operator interrupt races natural completion;
- kill fails while tmux session remains alive;
- restart preserves lineage and immutable prior evidence;
- worktree disappears while status remains;
- completion report is malformed or missing;
- disk write fails during atomic status replacement.

Score recovery correctness, evidence preservation, operator guidance, and time to diagnosis—not merely whether an exception occurred.

**Acceptance gate.** Each injected failure ends in a documented state, preserves prior receipts, and provides an actionable next command without silently claiming completion.

### E12. Add longitudinal regression gates

**Problem.** Eval results are useful only if model, prompt, CLI, and code changes can be compared over time.

**Recommendation.** Start with Inspect eval logs stored under an ignored local output directory and publish compact release summaries as build artifacts. Gate changes on:

- zero deterministic correctness regressions;
- zero new writable-scope or evidence-fidelity violations;
- no decline beyond the versioned deterministic-pass@1 non-inferiority margin on the pinned validation cohort;
- no median or eligible-tail wall-time/token/cost regression beyond the versioned thresholds from E9;
- explicit approval for changed scorer or dataset versions.

When multiple users or machines need shared comparisons, add MLflow Tracking as an optional backend. Log Inspect summaries, raw eval logs, provenance files, patches, and receipt bundles as MLflow artifacts. Do not replace the local evidence root or Inspect logs with a database-only record.

**Acceptance gate.** A historical result can be reproduced or explained from stored source/prompt/config/dataset/scorer hashes and environment metadata.

## Correctness improvements

### C1. Validate every durable artifact against a versioned schema

Expand [`session-status.schema.json`](../schemas/session-status.schema.json) to include current launch prompt, command, baseline, completion, retry, timing, terminal, and provenance fields. Add schemas for command, run provenance, completion, evaluation plan, and score summary. Validate on release and at trust boundaries; avoid validating every log write if it materially affects runner reliability.

Use JSON Schema Draft 2020-12 and `check-jsonschema` or the `jsonschema` package. Add explicit schema migration rules before changing required fields.

**Verification.** Release checks validate every shipped schema and fixture; runtime tests reject malformed artifacts at each trust boundary; a frozen v1 fixture remains readable after any v2 implementation lands.

### C2. Record an append-only lifecycle history

The mutable `status.json` is convenient but loses transition history. Preserve it as the current snapshot, while emitting lifecycle transitions as OpenTelemetry spans/events or an append-only structured event stream. Events should include timestamp, prior/new state, actor, reason, and receipt references.

Prefer OpenTelemetry conventions for exported traces. If a small local event file is retained for offline durability, treat it as a write-ahead receipt feeding the OTel exporter—not a new analytics platform.

**Verification.** Tests prove that every lifecycle transition produces one ordered event, snapshot reconstruction reaches the same final state as `status.json`, and exporter failure cannot break or erase local execution evidence.

### C3. Replace log-mtime stall detection with multi-signal health

Log inactivity alone cannot distinguish deep reasoning, network waits, blocked prompts, deadlocks, and quiet tests. Combine:

- periodic runner heartbeat;
- tmux pane/process liveness;
- executor structured events;
- last tool/model event time;
- CPU/process state where cheaply available;
- explicit waiting-for-input signals where exposed.

Keep `possibly_stalled` advisory. Do not automatically kill based on a heuristic score. Surface the signals and recommended diagnostic command.

**Verification.** Fixture processes representing quiet success, blocked input, deadlock, network wait, and lost tmux state produce distinct evidence bundles and never trigger automatic termination.

### C4. Separate baseline failures from agent regressions

Every eval fixture should run declared acceptance commands before launch and after completion in equivalent environments. Classify each test as pass→pass, fail→pass, pass→fail, or fail→fail. The primary regression gate is pass→fail; fail→pass is improvement; existing fail→fail must not be blamed on the agent but should remain visible.

Use JUnit XML and stable test IDs to avoid brittle text comparison.

**Verification.** An eval fixture containing one pre-existing failure and one agent-introduced failure attributes only the pass→fail transition to the agent and preserves both raw JUnit receipts.

### C5. Make acceptance and review explicit lifecycle operations

Implement the existing roadmap's `reviewed`, `accepted`, and `rejected` commands with actor, timestamp, reason, reviewer identity, scorer summary hash, and accepted revision. Acceptance must not be inferred from agent exit code or self-report.

The command should validate completion/provenance/scoring artifacts first. High-risk tasks should require a distinct reviewer receipt.

**Verification.** Acceptance fails for missing receipts, a mismatched revision, self-review on a high-risk task, or failed deterministic gates; successful acceptance records actor, reason, score hash, and revision without rewriting agent evidence.

### C6. Add property and state-machine tests where invariants matter

Use Hypothesis stateful testing for lifecycle invariants such as:

- terminal states never regress to active states;
- prompt/command/source hashes never change after launch;
- retries never overwrite prior run directories;
- worktree cleanup never removes the authoritative evidence root;
- session IDs cannot escape configured state roots;
- accepted revisions correspond to recorded worktree commits.

Hypothesis is preferable to hand-enumerating every transition sequence and is especially well suited to race-prone lifecycle logic.

**Verification.** Stateful tests run in CI with a retained failure seed/example database, and every discovered invariant violation becomes a focused regression test before the generated case is minimized or retired.

## Usability improvements

### U1. Add an evaluation-oriented run ledger

Implement the roadmap's pack-level run ledger as a generated view over session receipts and task manifests. It should show phase/ticket dependency, executor, current state, score summary, retry lineage, accepted revision, elapsed time, and next action.

Provide text, `--json`, and `--output PATH` modes. Keep the JSON stable and render text from it. Do not introduce a database for the first version; derive the ledger from durable run directories and manifests.

**Acceptance gate.** A pack with completed, failed, retried, accepted, and missing sessions renders correctly from files alone; text and JSON contain the same ticket/retry/score facts, and corrupt entries are isolated with actionable errors.

### U2. Add comparison and report commands as thin wrappers

Suggested UX:

```text
agent-workflow eval validate EVAL_PATH
agent-workflow eval run EVAL_PATH --executor codex --executor claude
agent-workflow eval compare RUN_A RUN_B
agent-workflow eval report RUN_ID --format markdown|json
```

These commands should call the Inspect integration and link to its eval logs. They should not implement an alternative scheduler or scoring system. `compare` should refuse invalid cohorts by default and explain mismatched variables.

**Acceptance gate.** The CLI can launch a pinned two-executor eval, print the Inspect log path, reproduce a report from that log without model calls, and reject comparison when prompt/base/budget hashes differ.

### U3. Improve executor preflight and capability discovery

Extend `doctor` with executor-specific checks:

- executable resolution and version;
- structured-output support;
- configured sandbox/permission mode;
- optional authentication probe, only when explicitly requested because it may make a paid call;
- tool availability required by a specific prompt pack;
- warnings for deprecated or hidden CLI flags.

Represent capabilities as data so launch/eval can fail early with a precise message. Do not hard-code vendor versions throughout the CLI; keep small executor adapters.

**Acceptance gate.** Missing binaries, deprecated flags, unsupported structured output, and optional paid-auth probes are reported separately; ordinary `doctor` remains offline and free of model calls.

### U4. Make status diagnostic, not merely descriptive

For `possibly_stalled`, `orphaned`, `terminal_unavailable`, malformed completion, and failed validation, include:

- signals that caused classification;
- last meaningful event and age;
- whether the executor process still exists;
- exact log, status, completion, and worktree paths;
- one recommended next command;
- whether interrupt/restart/kill is safe and what evidence it preserves.

Add filters such as `list --active`, `--failed`, `--pack`, `--ticket`, and `--executor`. Keep default output compact.

**Acceptance gate.** For each non-happy state, a fixture asserts the classification signals, durable paths, recommended command, and safety note. Default list output stays within one row per session.

### U5. Improve tmux foregrounding with native tmux operations

`attach` can be awkward when invoked from inside tmux. Detect the current tmux context and offer explicit modes such as `--switch-client`, `--split-window`, or `--join-pane`, implemented with tmux's existing commands. Keep plain attach for callers outside tmux.

This solves operator friction without building a terminal UI.

**Acceptance gate.** Tests or scripted tmux fixtures cover callers inside and outside tmux, reject invalid target panes, and preserve the delegated session when foregrounding fails.

### U6. Generate shell completion instead of maintaining it manually

Use `shtab` to generate Bash, Zsh, and tcsh completions from the argparse tree. Keep this an optional installation extra. Include completion generation in release verification to prevent stale subcommand/option documentation.

**Acceptance gate.** Generated completions expose every current command and option, install only when requested, and reproduce byte-identically from the same source revision.

### U7. Provide concise failure taxonomy and remediation

Normalize failure categories such as `preflight`, `executor_missing`, `auth`, `launch`, `timeout`, `orphaned`, `acceptance_failed`, `scope_violation`, `evidence_invalid`, and `operator_terminated`. Store category plus raw error.

Map each category to a short remediation message and documentation anchor. Preserve raw stderr and structured executor events for diagnosis.

**Acceptance gate.** A table-driven test maps representative failures to one stable category while retaining raw details; unknown failures remain `unclassified` rather than being forced into a misleading bucket.

### U8. Add budget-aware operator controls

Allow pack/eval configuration to set wall-time, token, and cost budgets when the executor exposes them. Surface consumption in status and require explicit confirmation before exceeding a retry budget. Budget exhaustion should end in a distinct terminal classification, not generic failure.

Do not estimate silently. Mark usage as reported, calculated, unavailable, or estimated, with the pricing version/date when cost is calculated.

**Acceptance gate.** Fixture executors cover reported usage, unavailable usage, budget exhaustion, and retry-over-budget flows; no run is classified as ordinary success after exceeding a hard declared budget.

## Recommended evaluation scorecard

Keep the release-facing scorecard small:

| Metric | Type | Why it matters |
|---|---|---|
| deterministic pass@1 | binary/rate | Phase 0 first-attempt success from objective gates |
| accepted@1 | binary/rate | Phase 1 useful first-attempt success after reviewer receipts exist |
| regression-free | binary/rate | Protects existing behavior |
| writable-scope compliance | binary/count | Measures bounded delegation discipline |
| evidence fidelity | rate/count | Measures trustworthiness of reports |
| operator interventions | count/rate | Measures autonomy burden |
| wall time | median/p95 | Measures delivery latency |
| tokens and cost | median/p95 | Measures resource efficiency |
| retry count | median/rate | Exposes fragile success |
| stall/orphan rate | rate | Measures operational reliability |

Provide drill-down metrics, but do not add dozens of primary KPIs. A release gate should be understandable without a dashboard.

Tail columns are conditional: p90 requires at least 20 observations and p95 at least 40. Smaller cohorts show median, range, and raw trials instead.

## Implementation sequence

### Phase -1: topology and reuse decision

Deliver:

- working Inspect SWE Codex and Claude baseline runs;
- prototype sandbox-installed `agent-workflow` run using `sandbox_agent_bridge()` and `sandbox().exec()`;
- documented API routing, XDG receipt extraction, patch transfer, model accounting, tmux behavior, and teardown behavior;
- ADR selecting topology and listing reused Inspect SWE components.

Exit criteria:

- at least one task completes with bridge-captured model calls and exported workflow receipts;
- host-to-sandbox control is either proven safe or explicitly rejected;
- E1 implementation is blocked until the ADR is accepted.

### Phase 0: ordered deterministic MVP

Implement these dependencies in order:

1. **Contract and validation.** Add separate evaluation JSON, JSON Schema instance validation, cohort hashing, and evaluator-only oracle references.
2. **Structured and sealed receipts.** Add completion JSON, run provenance, final receipt sealing, raw executor event preservation, and mutation detection.
3. **Baseline/post collectors.** Capture complete multi-repository Git state, baseline/post JUnit results, tool versions, timing, and budgets.
4. **Deterministic scorers.** Implement acceptance, regression, writable-scope, schema, static-quality, and evidence-fidelity scoring from sealed receipts.
5. **Fixtures and oracle boundary.** Add three to five public fixture tasks, external evaluator-only oracles, no-op/broken baselines, reference solutions, and leakage canaries.
6. **Inspect adapter.** Implement the E0-selected bridge topology by composing existing Inspect SWE components where possible.
7. **CLI and reports.** Add a thin local command that invokes Inspect, prints its log location, and renders deterministic Markdown/JSON summaries from the Inspect log.

Exit criteria:

- each numbered step has focused tests before its dependent step begins;
- repeatable results from clean, isolated fixtures;
- all scores link to sealed receipts and evaluator-only oracles remain inaccessible to agents;
- no custom database, scheduler, statistics implementation, or web UI;
- no LLM judge or `accepted@1` requirement in the Phase 0 release gate.

### Phase 1: comparison quality and recovery

Deliver:

- repeated-trial eval sets and paired comparison report;
- recovery/fault-injection task suite;
- lifecycle history and multi-signal stall observations;
- explicit reviewed/accepted/rejected receipts;
- calibrated optional qualitative grader.

Exit criteria:

- comparison reports include uncertainty and cohort validation;
- recovery failures preserve evidence and produce correct next actions;
- judge calibration results are versioned and visible.

### Phase 2: external benchmarks and interoperability

Deliver:

- official SWE-bench harness adapter;
- OpenTelemetry export behind an optional extra;
- optional MLflow tracking backend for shared longitudinal analysis;
- scheduled validation/holdout runs.

Exit criteria:

- official harness accepts predictions without local patching;
- trace attributes use published OTel conventions where available;
- local Inspect logs and run receipts remain sufficient without MLflow.

## Explicit non-recommendations

Do not build the following in the near term:

- a custom model-judge framework;
- a custom benchmark container manager;
- a bespoke experiment database;
- a web dashboard before Inspect's log viewer and MLflow are demonstrably insufficient;
- a universal agent protocol when Inspect Agent Bridge and executor adapters cover current needs;
- automatic model selection from a small, noisy result history;
- one opaque composite score that hides correctness or safety failures;
- automatic termination based only on stall heuristics;
- patch-similarity scoring as a proxy for correctness;
- benchmark claims based on one run or an unpinned dataset/harness.

## Official integration references

- [Inspect AI documentation](https://inspect.aisi.org.uk/) — tasks, datasets, solvers/agents, scorers, metrics, sandboxes, eval sets, logs, and log viewer.
- [Inspect AI Agent Bridge](https://inspect.aisi.org.uk/agent-bridge.html) — integration point for third-party and custom agents.
- [Inspect SWE Codex CLI agent](https://meridianlabs-ai.github.io/inspect_swe/codex_cli.html) — existing sandboxed Codex integration to reuse or use as a baseline.
- [Inspect SWE Claude Code agent](https://meridianlabs-ai.github.io/inspect_swe/claude_code.html) — existing sandboxed Claude integration to reuse or use as a baseline.
- [Inspect AI scorers](https://inspect.aisi.org.uk/scorers.html) — standard/custom/multiple scorers and score aggregation.
- [Inspect AI eval logs](https://inspect.aisi.org.uk/eval-logs.html) — durable eval log format, analysis, retries, and sample preservation.
- [SWE-bench evaluation guide](https://www.swebench.com/SWE-bench/guides/evaluation/) — official containerized patch evaluation harness.
- [SWE-bench repository](https://github.com/SWE-bench/SWE-bench) — datasets, harness, and current implementation.
- [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) — published GenAI events, metrics, spans, and agent-span conventions; treat experimental portions as versioned optional integration.
- [MLflow agent evaluation](https://mlflow.org/docs/latest/genai/eval-monitor/running-evaluation/agents/) — trace-aware datasets, agent scorers, evaluation, and tracking UI.
- [fsatrace](https://github.com/jacereda/fsatrace) and [strace](https://strace.io/) — existing Linux process-tree filesystem tracing options for corroborating ignored-path writes.

## Definition of success

This plan succeeds when an operator can run the same pinned ticket cohort against Codex and Claude, obtain reproducible deterministic scores plus calibrated qualitative scores, compare success/cost/latency/evidence quality with uncertainty, inspect every failed trial from durable receipts, and detect regressions caused by model, prompt, CLI, or workflow changes—without `agent-workflow` owning a new benchmark engine, trace backend, statistics library, or dashboard.
