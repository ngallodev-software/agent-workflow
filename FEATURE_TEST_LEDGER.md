# Agent-workflow feature test ledger

This is the running verification record for the P0 workflow-foundation
implementation round. Results are based on executable tests, agent-workflow
receipts, focused probes, and live observations. `partial` means the durable
core exists but an important operational boundary remains; `failed` means a
reproducible correctness defect; `useful` and `pointless` are practical value
assessments, not quality scores.

| Feature | Result | Usefulness | Evidence / current limitation |
|---|---|---|---|
| Codebase-memory MCP indexing | pass | useful | Full persistent index rebuilt before this round: 5,108 nodes, 11,310 edges; `.codebase-memory/graph.db.zst` written. |
| Prompt-pack validation and dependency DAG checks | pass | useful | Pack validation and WF-001 tests reject malformed, unknown, self, and cyclic dependencies. |
| Structured completion contracts and handoff collection | pass | useful | WF-002 completion JSON/schema collection and sealed artifact tests pass. |
| Agent class/model/no-go policy routing | pass | useful | Config and session-launch tests cover executor-specific models, classes, permissions, and no-go authorization. |
| Unique agent names across active interactive/detached runs | pass | useful | Session-launch naming tests pass; active-name collisions are rejected or receive another configured name. |
| Detached noninteractive tmux sessions | pass | useful | WF-00 and WF-01 runs use dedicated sessions with durable state and no visible pane consumption. |
| Interactive pane layout/capacity and mouse behavior | pass (automated) | useful | tmux tests cover horizontal columns, vertical stacking, capacity preflight, dead-pane handling, and mouse configuration; live pane behavior remains observational. |
| Durable steer/progress/ack records | partial | useful | JSONL append/replay, fsync, correlation, and validation pass; one-shot Codex/Claude processes do not yet consume late steering semantically. Tracked as BKL-002. |
| Child progress emission from delegated runs | partial | useful | Child attempts to emit progress, but executor sandbox access to the external run-state messages file can fail read-only; delivery is not yet adapter-backed. |
| Lifecycle review/accept/reject disposition | partial | useful | Lifecycle code requires a deterministic score set even for ordinary non-evaluation implementation runs; WF-00 disposition could not be recorded without fabricating a score. |
| WF-00 workflow schemas, event journal, replay, and corruption rejection | pass | useful | Mini implementation plus independent Luna review accepted at `64ee486`; focused and full-suite gates passed. |
| WF-01 dependency scheduler | pass | useful | Luna correction plus independent Mini re-review accepted at `82d56d3`; race, crash-window, dependent advancement, provenance, manifest, and full-suite checks pass (171 passed, 1 skipped). |
| Release manifest portability across linked worktrees | pass for WF-00 and WF-01 correction | useful | Corrected auditor excludes `.git` directory and worktree control file; Luna regenerated and validated the manifest. |
| Optional read-only MCP server/resources | pass | useful | Existing MCP protocol/service tests pass; bounded resources and `pack_validate` are available. |
| MCP mutation tools | deferred | useful | Correctly blocked until WF-22; must call shared services and report pending steering honestly. |
| WF-02 restart recovery and workflow CLI | pass | useful | Mini correction `wf02-mini-r3-20260724` plus independent Luna review `wf02-review-luna-r3-20260725` accepted at `ea77a74`; direct JSON/human CLI probes, bounded filesystem errors, 178 passed/1 skipped, and release audit passed. |
| Executor command safety during review | partial | useful but frictional | A review probe using `mktemp` plus narrowly scoped `rm -rf "$tmp"` was rejected by the executor safety filter before execution. The guard protects against destructive commands but does not distinguish a validated temporary path; the reviewer completed using `/dev/null` and non-destructive cleanup. |
| Delegated linked-worktree commit/finalization | partial | useful but incomplete | WF-10 Mini implementation reached green focused/full/audit gates, but the linked worktree could not write its Git index lock, so the delegated commit and completion sidecar could not be finalized. The run was terminated with sealed evidence preserved; acceptance requires coordinator-side recovery plus independent review. |
| WF-10 receipt-backed approval gates | rejected | useful | Independent Luna review found a correctness/security gap: approval trusts mutable `status.json` receipt-path state and does not prove the referenced receipt is the append-only artifact for this run, allowing a forged/copied same-session receipt with matching fields. Full review gates passed (181 passed/1 skipped; release audit valid), but acceptance is blocked pending correction. |
| Claude launch interactivity default | pass | useful | Session policy tests pass: Claude defaults to interactive even for exploratory/review classes; explicit `interactive=False` remains non-interactive. Focused launch/config/CLI/executor suite: 36 passed. |
| Global install/doctor/build path | pending this round | useful | Must be rerun after cumulative P0 integration; no claim made yet. |

## Practical assessment

The most useful features so far are isolated durable worktrees, explicit
executor/model policy, completion contracts, independent review, and the
codebase-memory graph. The least useful behavior is terminal capture as a
control mechanism: it is useful for observation, but pointless as proof of
semantic delivery. The current one-shot executor path is also insufficient
for interactive reuse or late steering until BKL-002 supplies a real adapter.

Update this ledger whenever a feature is exercised, repaired, rejected, or
found to be operationally misleading. Do not mark a feature `pass` from an
exit code alone; retain the command, receipt, or reproducible probe that
supports the result.
