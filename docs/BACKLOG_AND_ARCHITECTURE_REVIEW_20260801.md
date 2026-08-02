# Backlog and architecture review — 2026-08-01

> **Historical/superseded:** This review records the analysis that preceded 0.7.7 decisions. DEC-005 and DEC-009 are now decided; Jenkins remains repository-core CI/CD but is excluded from runtime distributions; MCP is an optional extra; Apache-2.0 is adopted; and GitHub Private Vulnerability Reporting is selected pending enablement proof. Use `docs/BACKLOG.md` for current state.

## Executive assessment

The core design remains solid. The most important architectural boundary—immutable JSON/JSONL contracts, journals, snapshots, and receipts as authority, with status files, tmux state, rendered output, and SQLite as rebuildable projections—is consistently represented in the runtime, tests, and current architecture documentation. Shared CLI/MCP/workflow services, isolated worktrees, explicit acceptance, bounded subprocess ownership, and fail-closed evidence validation are also the right foundations for this product.

The project has not drifted into a contradictory architecture, but it has accumulated **scope pressure**. It now contains or plans orchestration, durable messaging, workflow execution, evaluation, comparative benchmarking, tmux operator UI, self-healing, searchable analytics, MCP, plugin hosting, collaborative spec authoring, hierarchical teams, installers, and release infrastructure. Most additions are adjacent and well designed; the risk is attempting to make all of them first-class core product surfaces before the security and public-release boundary closes.

Recommended posture:

1. Finish the currently unblocked security and compatibility lane: HARD-003, HARD-006, HARD-007, REL-003, then HARD-009/HARD-010 and REL-004.
2. Close existing in-review work before opening another major subsystem.
3. Keep comparative benchmarking modular and keep collaborative spec authoring in the proposed sibling plugin.
4. Do not begin hierarchy without explicit DEC-005 approval.
5. Treat the optional tmux sidebar, host routing, local Jenkins trigger, multi-host transport, and state-mutating MCP as nonessential until measured need or their security prerequisites exist.

## Review scope and evidence

Reviewed surfaces:

- canonical backlog, decisions, release-readiness, security, architecture, operations, testing, and changelog documents;
- all prompt-pack manifests and declared backlog ownership;
- runtime modules, schemas, package metadata, release assets, installer/release workflow, tests, and future specifications;
- module size and responsibility concentration;
- current external libraries/projects that could replace limited custom infrastructure.

Validation completed in this environment:

- `scripts/audit-release-assets.py`: passed after all edits and deletions;
- all 16 repository prompt packs: validated;
- core invariant/future/preflight slice: **139 passed, 11 intentional strict xfails**;
- release installer suite: **4 passed**;
- release/static slice not requiring an installed product: **7 passed**;
- comparative benchmark development journey: **1 passed** before the documentation-only reconciliation. A post-edit rerun did not complete because the host Chromium process stopped reaching headless readiness; no benchmark runtime file changed.

The complete installed-product suite could not be collected in this analysis environment because its fixture correctly requires the declared `mcp==1.28.1` distribution and the available package index could not provision it. This is an environment limitation, not evidence that those tests fail. The repository CI and a clean release environment should rerun the full suite before integration.

## Backlog corrections applied

The prior backlog contained real status drift:

- completed IDs remained mixed into active sections despite the stated “unfinished work only” policy;
- HARD-003, HARD-006, HARD-007, REL-003, and BKL-007 were marked blocked even though their stated prerequisites were complete;
- REL-008 was marked ready although the release workflow, bundle builder, bootstrap/install surfaces, and installer tests already existed;
- REL-002 was marked blocked even though it requires an external maintainer/ownership decision rather than an implementation dependency;
- REL-007 duplicated clean-host compatibility in REL-003 and real-provider cohort evidence in BKL-004;
- HARD-004 remained a strict expected-failure placeholder after implementation and accepted evidence existed;
- obsolete blocker inventories contradicted the current foundation-gate state;
- hierarchy prose implied DEC-005 was approved when it remains `needs-decision`;
- release readiness still listed accepted HARD foundations as active blockers;
- the changelog placed released 0.5.x–0.7.5 features under `Unreleased`.

Applied changes:

- moved accepted task IDs into an explicit completed/superseded register;
- promoted HARD-003, HARD-006, HARD-007, and REL-003 to `ready`;
- changed BKL-007, REL-002, and REL-006 to `needs-decision` for the actual unresolved decision;
- changed REL-008 to `in-review` with only tagged-release and clean-host evidence open;
- closed REL-007 as superseded;
- graduated HARD-004 out of `tests/future`;
- updated HARD-009 to include backlog state-transition, prerequisite, and active/completed consistency checks;
- added MAINT-001 for behavior-preserving module decomposition and MAINT-002 for retiring the MiniYAML fallback;
- removed obsolete blocker artifacts and their stale handoff prompt;
- corrected public-release, architecture, README, testing, and changelog language.

## Feature status

### Complete and accepted foundations

These capabilities have implementation and accepted task-level evidence:

- bounded subprocess execution, process-group cancellation, output/environment limits, and executable evidence (HARD-001);
- no-follow artifact/path handling, pack completeness, and schema identity/integrity controls (HARD-002);
- immutable launch/final-receipt authority independent of mutable status projections (HARD-004);
- bounded, metadata-minimal, path-safe read-only MCP resources (HARD-005);
- trusted configuration/executor identity and sanitized host environment (HARD-008);
- durable per-consumer messaging cursor/reconstruction foundation (BKL-001);
- orchestrator registry/fan-in and supervisor delivery foundation (MSG-001/MSG-002);
- structured release policy, direct dependency lock, SBOM/provenance evidence, and release blocker reporting (REL-005);
- comparative benchmark fixture/evaluation matrix and full synthetic paired benchmark path (BKL-011 and 0.7.5 benchmark foundation).

### Functionally implemented but partially complete

These features exist and have meaningful tests, but still need an independent gate, live-host/provider evidence, security prerequisite, or release proof:

- late steering/control-file bridge (BKL-002);
- delegation preflight, control handshake, observability, completion validation, pane identity, and source snapshot reliability (PROC-001 through PROC-007);
- force-accept lifecycle override and Luna effort policy (LIFE-001/POL-001);
- self-healing observable foundation and safe supervisor loop (SUP-001/SUP-002);
- SQLite evidence schema, reconciliation, curated queries, CLI, and supervisor sync (IDX-001 through IDX-005);
- message restart reconstruction closeout (MSG-005);
- real-provider comparative benchmark operation and publication runtime proof (BKL-004/BKL-010);
- Linux/WSL2/macOS release installer mechanics (REL-008);
- installed acceptance and release checks that depend on full clean-environment dependency provisioning.

### Obviously missing before public support

- a maintainer-selected open-source license (REL-001);
- a real monitored vulnerability-reporting mechanism (REL-002);
- preventative write/read/network/resource isolation rather than post-run detection (HARD-003);
- content classification, redaction, opt-in disclosure, retention, export, and deletion enforcement (HARD-006);
- authenticated principals and independent-review identity enforcement (HARD-007);
- a supported host/tmux/Python/executor matrix with clean-host evidence (REL-003);
- source-derived drift/state consistency as a release gate (HARD-009);
- transitive dependency audit/locking, reproducibility, and authenticated signing/attestation (HARD-010);
- final independent public-preview decision and ownership record (REL-004).

### Less obvious missing or under-specified

These gaps are already covered by existing backlog lanes and should not receive duplicate IDs:

- **Backlog state-machine validation:** audit tooling checks ownership collisions but did not detect satisfied prerequisites left blocked, completed IDs in active sections, or contradictory prose. This is now explicit HARD-009 scope.
- **Clean dependency provisioning:** installed acceptance currently relies on obtaining the declared MCP distribution. REL-003/REL-008 should prove a clean online install and, if offline/restricted installs are a support goal, a documented wheelhouse strategy.
- **Fault-injection closeout:** supervisor, messaging reconstruction, SQLite replacement, and release installers need interruption/corruption matrices at their existing gates rather than more implementation-unit tests.
- **Measured capacity budgets:** large-run rebuild, journal replay, terminal capture, and benchmark consolidation need published scale evidence before optimization. IDX-007/SUP-008 already own this.
- **Data lifecycle execution:** documentation describes bounded evidence, but enforceable classification, retention, export, and deletion await HARD-006/SUP-003/IDX-006.
- **Release workflow trust:** action pinning, transitive vulnerability auditing, provenance verification, and signing belong under HARD-010.
- **Migration/support policy:** SQLite migrations exist, but the supported prior-schema range and downgrade/non-downgrade policy should be made explicit at the IDX gates.

## Design quality and drift

### What remains strong

- Authority and projection are sharply separated.
- tmux is presentation/attachment infrastructure, not state authority.
- CLI, workflow, and MCP are intended to share services rather than create alternate execution paths.
- Worktree isolation and immutable launch/evidence boundaries match the project’s threat model.
- Acceptance is a separate lifecycle decision rather than an inference from process exit.
- The SQLite store is correctly rebuildable and non-authoritative.
- The benchmark subsystem is already placed behind a modular package boundary.
- The proposed spec-authoring product is correctly designed as a sibling/plugin rather than another core state machine.

### Where scope has drifted

The drift is mostly **portfolio drift**, not low-level architectural drift. Too many adjacent programs are described as imminent:

- hierarchy is called a next layer in some prose despite lacking DEC-005 approval;
- the tmux operator program contains both a useful status/navigation layer and an optional sidebar that would become layout/capacity product scope;
- host routing is planned without current measured failure evidence;
- local Jenkins trigger work appears in the product backlog even though it is host-local operations;
- plugin hosting, spec authoring, hierarchy, state-mutating MCP, advanced analytics, and public release all compete for the same security foundations.

### Recommended cuts and deferrals

- **Do not start hierarchy** until DEC-005 is explicitly approved and existing messaging/delegation/pane work is accepted.
- **Keep TMUXUI-008 unapproved** unless operators demonstrate that popup/dashboard surfaces are inadequate. The sidebar adds capacity and layout authority risk for little core value.
- **Close BKL-007 unless measured evidence justifies it.** Host routing can become surprising installer-owned shell behavior.
- **Move or cut REL-006** unless local Jenkins deployment is an intentionally supported product surface.
- **Keep HIER-004 optional and non-blocking.** External terminal forking is convenience, not orchestration authority.
- **Keep multi-host/broker work deferred.** The current local durable model should be proven at scale first.
- **Do not add state-mutating MCP** before authenticated identity; read-only MCP is already a useful stable boundary.
- **Do not fold collaborative spec authoring into core.** Prove the plugin boundary and sibling repository first.
- **Do not add a vector store, online learning, or autonomous routing policy.** Existing evidence-derived static recommendations are sufficient until comparable cohorts exist.

## Files that should be split

The issue is responsibility concentration, not merely line count. Splits should preserve public imports/commands and happen as behavior-neutral maintenance.

| File | Approximate size | Recommended split |
|---|---:|---|
| `sessions.py` | ~2,020 lines | launch/contract builder; observe/status queries; control operations; restart/recovery; interactive-agent identity and native-job bindings |
| `cli.py` | ~1,530 lines | parser assembly by command domain; dispatch handlers by domain; shared rendering/error policy; retain one parser-derived command catalog |
| `index_store.py` | ~1,450 lines | schema/migrations; authoritative-source discovery/readers; reconciliation/projectors; read-only query service; verification/status |
| `runner.py` | ~1,300 lines | execution loop; structured stream collector; control bridge; completion collection; post-run sealing/retry cleanup |
| `process.py` | ~990 lines | executable/environment/redaction policy; managed process lifecycle; bounded I/O/spooling; synchronous wrappers |
| `workflow.py` | ~775 lines | graph/snapshot validation; replay/state reduction; serialization; keep scheduling in the existing scheduler/service modules |
| `config.py` | ~750 lines | schema/defaults; parsing/normalization; trust validation; serialization and compatibility diagnostics |
| `eval/templating.py` | ~720 lines | template registry; individual renderers; shared validation/digest code |
| `tests/conftest.py` | concentrated fixture surface | installed-product environment; repository/worktree fixtures; fake executors/tmux; benchmark fixtures |

Avoid a single large “refactor release.” Split one seam at a time, run installed journeys, and make no evidence/schema changes in the same commit.

## Library and project recommendations

### Replace or reuse

| Area | Recommendation | Rationale |
|---|---|---|
| YAML parsing | Replace `miniyaml.py` with declared [PyYAML](https://pyyaml.org/wiki/PyYAMLDocumentation) `safe_load` plus existing schema/semantic validation | The custom parser implements a partial YAML dialect and duplicates mature parsing/security behavior. This is the clearest custom-code removal. |
| Plugin host | Use `importlib.metadata.entry_points` with [pluggy](https://pluggy.readthedocs.io/) for hook registration, validation, blocking, and inspection | PLUG-001 should define policy/version/conflict rules, not invent a dispatcher and hook manager. |
| DAG validation | Use standard-library [`graphlib.TopologicalSorter`](https://docs.python.org/3/library/graphlib.html) for pure cycle/topological validation where it fits | Keep durable workflow replay/scheduling custom, but remove standalone graph-ordering code that duplicates the standard library. |
| Linux sandbox backend | Implement HARD-003 as a pluggable backend with [bubblewrap](https://github.com/containers/bubblewrap) as the Linux baseline | Do not build mount/user/network namespace isolation from scratch. The project still owns policy construction, validation, capability detection, and fail-closed behavior. |
| Cross-platform sandbox research | Evaluate [Anthropic sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) only as an adapter/reference | It is useful prior art for Linux/macOS/Windows backends, but should not become a hard dependency until its preview maturity and policy fit are proven. |
| Signing/attestation | Use [Sigstore](https://docs.sigstore.dev/) | HARD-010 should use interoperable signing, identity, and verification rather than a custom signature envelope. |
| SBOM | Continue/standardize on [CycloneDX Python](https://github.com/CycloneDX/cyclonedx-python) tooling | REL-005 already emits CycloneDX; HARD-010 should strengthen provenance and validation, not invent another format. |
| Vulnerability audit | Add [pip-audit](https://github.com/pypa/pip-audit) to HARD-010 release evidence | Use the PyPA-maintained vulnerability audit path rather than a custom advisory client. |
| tmux test support | Consider [libtmux](https://github.com/tmux-python/libtmux) fixtures/helpers for opt-in tests only | Keep exact tmux CLI commands, stable pane IDs, and evidence in the current authority path. A wrapper migration would risk semantic drift without reducing core complexity. |
| MCP dependency policy | Consider `mcp>=1.28.1,<2` in project metadata with an exact hashed release lock | The public compatibility range and reproducible release resolution serve different purposes. Change only after CI/clean-host compatibility evidence. |

### Keep custom

- **SQLite projection:** keep `sqlite3` and explicit migrations/transactions. SQLAlchemy would add abstraction without improving the rebuildable single-writer authority boundary; split `index_store.py` instead.
- **Argument parsing:** keep `argparse`. `cli.py` is too large because it contains many domains and handlers, not because the parser library is inadequate. A Typer/Click migration would create help/catalog/output drift.
- **Git worktree operations:** keep the Git CLI and exact argv/provenance. GitPython/pygit2 would not remove the need for subprocess/evidence policy and could diverge from operator Git behavior.
- **JSON/JSONL journals and receipts:** do not replace them with a generic event-sourcing framework. Their schemas, digest boundaries, no-follow reads, and recovery semantics are the product.
- **Managed process substrate:** do not wholesale replace it with AnyIO/Trio. Bounded I/O, process groups, exact executable/environment evidence, truncation/spooling, and descendant cleanup are security behavior. Small platform helpers may still be adopted.
- **tmux authority integration:** do not replace exact tmux CLI/evidence handling with a general object wrapper.

## Recommended execution order

1. Accept or close existing in-review PROC/MSG/SUP/IDX work with its named gates.
2. Implement HARD-003, HARD-006, and HARD-007 in parallel where writable scopes permit.
3. Run REL-003 clean-host compatibility while those controls stabilize; close REL-008 tagged-release evidence.
4. Implement HARD-009 and make backlog/status consistency machine-enforced.
5. Complete HARD-010 with standards-based audit/SBOM/provenance/signing and independent reproducibility.
6. Resolve REL-001 and REL-002, then execute REL-004.
7. Only after the public CLI boundary is stable, choose one next product lane: tmux core UX, plugin/spec authoring, or hierarchy—not all three concurrently.
8. Execute MAINT-001/MAINT-002 incrementally between feature gates, never as a broad rewrite.

## Final verdict

The design should be retained. There is no reason to restart the architecture or replace the durable evidence model. The highest-value changes are state discipline, scope control, module decomposition, and selective reuse of mature infrastructure at non-differentiating boundaries.

The project has drifted in ambition, but not yet in authority semantics. Keeping optional programs gated, cutting duplicate/convenience scope, and finishing the security/release lane before opening hierarchy or plugin execution will preserve the design’s strongest qualities.
