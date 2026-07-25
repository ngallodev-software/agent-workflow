# MCP Server Architecture Decision

**Status:** Read-only local-stdio implementation complete; safe mutation deferred until workflow foundations complete; no HTTP rollout  
**Decision date:** 2026-07-24  
**Confidence:** High for local stdio; medium for later HTTP deployment

## 1. Executive recommendation

Adopt MCP as an optional integration layer for `agent-workflow`, beginning with a thin, local, stdio-only Python server that calls existing domain services and reads authoritative run artifacts. Do not make MCP the lifecycle authority, do not expose tmux directly, and do not add a daemon or remote HTTP endpoint in the first phase.

The completed first surface is intentionally small: bounded read-only resources for run state/evidence plus `pack_validate`. Remaining mutation tools must wait until the workflow foundation is complete through `WF-22`, then reuse the same workflow, launch, routing, messaging, approval, and receipt services as the CLI. A steering call returns `pending` unless an executor-specific correlated acknowledgement proves delivery or application.

Rejected alternatives:

- **No MCP server:** safest, but leaves supported MCP hosts unable to use the durable lifecycle through a standard integration boundary.
- **TypeScript rewrite:** duplicates Python lifecycle logic and adds a second implementation language without a repository need.
- **Separate local daemon first:** adds process supervision, session ownership, and authorization burden before local value is proven.
- **Direct tmux exposure:** bypasses validation and receipts and creates arbitrary-command and keystroke-injection risk.
- **Multi-host gateway now:** conflicts with the current single-host assumption and requires broker, identity, authorization, and tenancy design.

## 2. Current architecture and durable boundaries

`agent-workflow` is a Python CLI and domain package that creates isolated Git worktrees, launches executor processes through tmux, and stores authoritative evidence under the state root. `messages.jsonl`, immutable artifacts, lifecycle events, review receipts, and final receipts are the durable record. Terminal capture is observational context only.

BKL-006 is complete in this change set: repo-owned skills now direct supported agents to the CLI and distinguish host-native subagents from durable runs. MCP should sit beside that skill surface as another client adapter. It must not fork lifecycle logic or reinterpret terminal output as proof.

The MCP protocol provides initialization, version/capability negotiation, tools, resources, prompts, client capabilities, logging, cancellation/progress utilities, and HTTP authorization semantics. The current published specification is 2025-11-25; experimental Tasks exist but should not be used as the durable run authority because repository receipts already define the lifecycle contract.

## 3. SDK, framework, and client matrix

| Option | License / maintenance | Protocol and transports | Auth/testing ergonomics | Operational burden | Fit |
|---|---|---|---|---|---|
| Official Python SDK / FastMCP | MIT; active official repository | Client/server, tools/resources/prompts, stdio, Streamable HTTP, legacy SSE compatibility | Native Python types, async support, in-process tests, HTTP auth hooks available when needed | Lowest; matches repository language | **Selected** |
| Official TypeScript SDK | MIT; active official repository | Broad client/server coverage; Node, Bun, Deno; stdio and Streamable HTTP | Strong schemas and web ecosystem | Adds Node toolchain and duplicates Python domain calls | Good protocol option, poor repository fit |
| Official Java SDK | MIT; maintained with Spring AI | Sync/async, stdio, Streamable HTTP, HTTP/SSE; broad feature coverage | Mature testing and enterprise HTTP integrations | JVM/runtime and wrapper layer | Not justified locally |
| Official C# SDK | Apache-2.0; maintained with Microsoft | Core, hosted, and ASP.NET HTTP packages; 2025-11-25 support in stable line | Strong DI/auth integration | .NET runtime and wrapper layer | Future enterprise gateway option only |
| Official Kotlin SDK | Apache-2.0 for new contributions, legacy MIT; maintained with JetBrains | Multiplatform, stdio, Streamable HTTP, SSE, WebSocket | Coroutine and Ktor integration | New ecosystem and no repository affinity | Not justified |
| Official Ruby SDK | Official and active | stdio and Streamable HTTP/SSE, tools/resources/prompts | Conformance runner present | New runtime and smaller fit | Not justified |
| Official Go/Rust SDKs | Official and active | Systems-oriented client/server implementations | Good standalone binary potential | Requires a domain API boundary or duplicated logic | Consider only for a future hardened gateway |

Representative hosts include Claude products, ChatGPT, Visual Studio Code, Cursor, and other MCP-compatible applications. Client feature support varies; capability negotiation is mandatory, and optional extensions must never be assumed.

## 4. Proposed capability map

### Read-only resources

| Resource | Input | Output/evidence | Authorization | Notes |
|---|---|---|---|---|
| `agent-workflow://runs` | filters, bounded page cursor | sanitized run summaries from state root | local user; state-root boundary | No arbitrary path input |
| `agent-workflow://runs/{id}/status` | validated run ID | normalized status plus evidence references | same-run access | Terminal capture clearly labeled observational |
| `agent-workflow://runs/{id}/messages` | run ID, sequence cursor | durable `messages.jsonl` records | same-run access | Bounded paging |
| `agent-workflow://runs/{id}/receipts` | run ID | final/lifecycle/review receipt metadata and hashes | same-run access | No secret-bearing raw environment |
| `agent-workflow://packs/{id}` | registered/validated pack ID | manifest and validation summary | configured pack roots | No unrestricted filesystem browsing |
| `agent-workflow://workflows` | bounded filters/page cursor | sanitized workflow summaries from authoritative workflow records | local user; state-root boundary | Added only after workflow foundation completion |
| `agent-workflow://workflows/{id}/status` | validated workflow ID | allowlisted node/status summary and receipt references | same-workflow access | No raw child terminal or direct state-file exposure |
| `agent-workflow://workflows/{id}/receipts` | workflow ID | aggregate workflow receipt metadata and child receipt hashes | same-workflow access | Verify sealed hashes before presentation |

### Mutating tools

| Tool | Durable result | Idempotency / safety |
|---|---|---|
| `pack_validate` | validation report | read-only; pack root allowlist |
| `worktree_create` | source-baseline/worktree result | safe repo/ticket identifiers; existing collision checks |
| `launch` | run ID, prompt hash, command/provenance receipts | explicit executor allowlist; no raw shell string |
| `progress` | appended control record | caller-supplied idempotency key or returned message ID |
| `ack` | correlated acknowledgement record | requires existing message ID |
| `steer` | appended request with state `pending` | never reports delivered without correlated acknowledgement |
| `workflow_validate` | validated immutable workflow snapshot or structured validation report | configured pack/root only; no execution |
| `workflow_launch` | workflow run ID and durable snapshot/event references | idempotency key; invokes authoritative scheduler only |
| `workflow_status` / `workflow_resume` | allowlisted status or durable resume action result | valid transition, idempotency, restart-safe service |
| `interrupt` / `terminate` | lifecycle event/receipt | destructive annotation; explicit run ID; policy gate |
| `review` / `accept` / `reject` | immutable review receipts | actor/reason required; acceptance requires revision |

### Explicit exclusions

Do not expose arbitrary shell execution, executor argv supplied as an unvalidated string, raw `tmux send-keys`, unrestricted file reads/writes, environment dumps, secret retrieval, worktree deletion, force kill, or cross-run bulk mutation in the first phase.

Prompts may later package operator workflows, but they are convenience templates rather than authorities. Sampling and elicitation are unnecessary for phase one. Elicitation must never be used to collect secrets. Experimental MCP Tasks must not replace repository lifecycle records.

## 5. Transport, lifecycle, and error semantics

### Phase-one transport

Use stdio. The host starts one local server process with the same OS identity and filesystem permissions as the user. This avoids listening sockets, OAuth setup, DNS rebinding exposure, and service supervision. Each process initializes once, negotiates capabilities, and exits with the client.

### Conditional HTTP evolution

Add Streamable HTTP only after stdio conformance and real-host trials pass and maintainers authorize a service boundary. The HTTP phase requires:

- loopback-only default binding;
- Origin and Host validation and DNS-rebinding protection;
- OAuth-based authorization following the current MCP authorization specification;
- explicit session ownership, expiration, and resumability rules;
- per-principal run and pack-root authorization;
- request size, concurrency, and rate limits;
- structured audit records linked to durable run evidence.

Legacy HTTP/SSE should be compatibility-only, not the preferred new deployment.

### Cancellation, progress, and errors

MCP cancellation may stop the current RPC handler but cannot erase a durable lifecycle action already committed. Long operations should report MCP progress while recording repository-native evidence. Return stable typed errors for invalid identifiers, forbidden roots, conflict/idempotency mismatch, missing run, invalid transition, executor unavailable, and evidence-integrity failure. Never downgrade an integrity failure to a warning.

## 6. Threat model

| Threat | Control |
|---|---|
| Path traversal / arbitrary file access | Resolve only validated IDs under configured repository, pack, worktree, and state roots; reject symlink escapes |
| Prompt/tool injection | Treat model-provided arguments as untrusted; validate schemas and enforce server-side policy independent of descriptions |
| Confused deputy | Bind every call to the local principal/session and authorize the exact run/root/action |
| Cross-run access | Safe run IDs, root containment, and per-run authorization checks |
| tmux visibility leakage | Return bounded sanitized capture only when requested; never expose raw pane control |
| Credential leakage | Never return environment, config secrets, tokens, or executor command secrets |
| Denial of service | Bound pagination, capture length, wait timeout, concurrent launches, and request sizes |
| Destructive lifecycle misuse | Annotate destructive tools, require explicit IDs/reasons, and preserve immutable events |
| False steering claims | Return `pending`; require correlated executor acknowledgement for delivered/applied state |
| Replay/duplicate mutation | Idempotency keys mapped to durable action receipts; reject mismatched reuse |
| Evidence tampering | Verify sealed hashes before presenting authoritative completion/acceptance claims |

## 7. Phased implementation plan

### MCP-0 — Domain seam audit and contracts

Identify existing CLI handlers that mix parsing with domain behavior. Define typed request/result contracts without changing lifecycle semantics. Add tests proving MCP and CLI call the same service functions. **Stop** if lifecycle behavior cannot be reused without a substantial refactor.

### MCP-1 — Read-only local stdio server — complete

Add `mcp==1.28.1` as an optional extra. Implement server initialization, capability declaration, run/pack resources, status, bounded messages, and receipt metadata. Add schema, traversal, redaction, conformance, and representative-host smoke tests. Rollback is removal of the optional entry point and dependency extra.

### Workflow prerequisite gate

Complete `workflow-foundations-next` through `WF-22` before any remaining MCP mutation work. This includes restart-safe scheduling, approvals, result binding, aggregate receipts, the three authorized templates, deterministic routing explanations, and integration review. The gate prevents MCP from becoming a second workflow implementation.

### MCP-2 — Safe creation, workflow, and control tools

Add `worktree_create`, single-run `launch`, workflow validate/launch/status/resume, `progress`, `ack`, and `steer` through shared services only. Require structured executor selection, configured roots, idempotency, and durable result IDs. Test invalid transitions, restart recovery, and the `pending` steering contract.

### MCP-3 — Destructive/review tools

Add interrupt/terminate and review/accept/reject behind explicit policy flags and tool annotations. Test authorization, reason/revision requirements, duplicate requests, and immutable receipts. Keep force kill excluded unless separately approved.

### MCP-4 — Host matrix and release gate

Test supported local hosts against a pinned protocol/SDK matrix. Run the official MCP Inspector/conformance tooling, cancellation/progress scenarios, malformed input fuzzing, and end-to-end receipt verification. Publish a capability compatibility table.

### MCP-5 — Optional Streamable HTTP design gate

Only after local adoption evidence, produce a separate ADR for service identity, OAuth, deployment, session persistence, rate limits, and multi-user authorization. No HTTP code before approval.

## 8. Approved maintainer decisions

1. MCP is an optional integration surface implemented in Python.
2. The first transport is local stdio, with MCP Inspector as the initial conformance client; host-specific trials follow.
3. Pin the official stable Python SDK to `mcp==1.28.1` and target protocol `2025-11-25` initially.
4. Authorize only configured repository, pack, worktree, and state roots; reject traversal and symlink escapes.
5. Omit destructive tools until MCP-3; force kill remains excluded.
6. Use `mcp-stdio:<server-instance-id>` as the local actor identity in receipts.
7. Add an optional `mcp` dependency extra and `agent-workflow-mcp` entry point; runtime code uses public SDK APIs rather than vendored internals.
8. Exclude raw terminal capture from the first surface; any later observational view must be bounded and explicitly labeled.
9. Require a separate authorization ADR before any non-stdio transport.

## 9. Decision-refresh research and current scaffold

Research refreshed 2026-07-24 against the official Python SDK repository and
stable tag `v1.28.1` (`777b8d06710c140e3606b0d4598e2aa48546c266`). The SDK's public
FastMCP API supports `@mcp.resource`, `@mcp.tool`, and `mcp.run(transport="stdio")`.
The repository's `main` line is v2 alpha/beta and is not the selected dependency.

The initial scaffold is in `src/agent_workflow/mcp/server.py`. It exposes bounded
run/status/messages/receipt resources and `pack_validate`, while delegating to
existing state, message, receipt, and manifest services. It does not expose shell,
tmux, arbitrary paths, launch/control mutation, raw terminal capture, or HTTP.

The full SDK source snapshot is retained at `src/agent_workflow/mcp/sdk/` for
research and prompt-pack evidence only; the runtime package depends on the pinned
optional distribution.

## Applied backlog update

- **MCP-001 (done):** Reusable domain seams and typed MCP request/result contracts.
- **MCP-002 (done):** Read-only local stdio MCP server with official Python SDK, bounded resources, traversal/redaction controls, and conformance tests.
- **MCP-003 (blocked on WF-22):** Safe single-run/workflow mutation tools with idempotency and durable evidence mapping.
- **MCP-004 (deferred):** Gated destructive/review tools and representative-host evaluation matrix.
- **MCP-005 (decision):** Authorize or reject Streamable HTTP after local adoption and security evidence.

## Official sources

Accessed 2026-07-24; SDK source pinned to `v1.28.1`:

- MCP specification 2025-11-25: https://modelcontextprotocol.io/specification/2025-11-25
- Protocol overview and capability areas: https://modelcontextprotocol.io/specification/2025-06-18/basic
- Tools: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- Authorization: https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- Elicitation security guidance: https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation
- Experimental Tasks: https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks
- Architecture/client concepts: https://modelcontextprotocol.io/docs/learn/architecture
- Local server connection guidance: https://modelcontextprotocol.io/docs/develop/connect-local-servers
- Official Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Official Python SDK stable tag: https://github.com/modelcontextprotocol/python-sdk/tree/v1.28.1
- Official TypeScript SDK: https://github.com/modelcontextprotocol/typescript-sdk
- Official Java SDK: https://github.com/modelcontextprotocol/java-sdk
- Official C# SDK: https://github.com/modelcontextprotocol/csharp-sdk
- Official Kotlin SDK: https://github.com/modelcontextprotocol/kotlin-sdk
- Official Ruby SDK: https://github.com/modelcontextprotocol/ruby-sdk
- Official Go SDK: https://github.com/modelcontextprotocol/go-sdk
- Official Rust SDK: https://github.com/modelcontextprotocol/rust-sdk
- Official ecosystem introduction: https://modelcontextprotocol.io/docs/getting-started/intro
