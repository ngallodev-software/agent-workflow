# MCP server

## Current boundary

`agent-workflow-mcp` is a local stdio adapter built with the pinned official Python MCP SDK. It exposes bounded read-only views of configured repository, prompt-pack, worktree, state, run, message, receipt, installed-command, and sealed run-command-context data.

The adapter is intentionally not a second orchestration engine. CLI and MCP surfaces must call the same application services and produce the same durable evidence.

Current exclusions:

- launch or workflow mutation;
- review, acceptance, rejection, interrupt, terminate, or kill;
- arbitrary shell commands or arbitrary filesystem paths;
- raw unbounded terminal capture;
- network transport or Streamable HTTP;
- implicit privilege escalation or model selection.

## Trust boundaries

- Local stdio is the only authorized transport.
- Configured roots and every selected path are opened component-wise with no-follow descriptors; traversal and symlink components fail closed.
- Responses use versioned bounded envelopes, bounded pagination, and metadata-only message/receipt summaries.
- Actor identity uses a local server-instance identity rather than pretending to be a human reviewer.
- Resource reads do not make mutable projections authoritative.
- Optional dependency failure is deterministic and actionable; the stdio child receives only a sanitized environment.

Message resources never return message bodies. They expose identity, type, placeholder principal, timestamp, correlation/disposition metadata, byte length, digest, and `redaction_state: "body_omitted"`. A separately authorized and redacted content capability is intentionally deferred; no casual boolean enables it.

Receipt resources verify the same contiguous, regular, read-only lifecycle receipt chain used by lifecycle verification. Replacement, writable, irregular, duplicate, malformed, and noncontiguous entries fail closed rather than producing a partial summary.

Errors use stable categories. Unexpected failures return only an opaque correlation ID; local logging records that ID without exception text, paths, or captured content.

## Command capability resources

The read-only server publishes parser-derived command knowledge without converting CLI commands into MCP tools:

- `agent-workflow://capabilities` reports the installed version, stdio/read-only mode, live command-catalog digest and leaf count, supported launch-contract versions, registered resources/tools, and explicit exclusions.
- `agent-workflow://commands` returns the complete schema-validated catalog generated from the installed CLI parser.
- `agent-workflow://commands/{role}` returns the existing `orchestrator`, `implementation`, or `review` role scope.
- `agent-workflow://runs/{agent_run_id}/command-context` verifies the run launch contract and reports its catalog/card binding. The verified Agent Run contract returns a bounded command-context binding.
- `agent-workflow://runs/{agent_run_id}/command-card` returns the verified bounded role card for Agent Runs.

The server calls the same `runtime_command_catalog()`, `filter_catalog()`, and `read_launch_contract()` boundaries used by the CLI and sealed-run verifier. It never maintains an MCP-specific command list. Public run context normalizes the executable name and does not expose an absolute installation path. Catalog/card replacement or digest drift fails closed.

The catalog is discovery metadata, not authorization. The server must not dynamically register one MCP tool per CLI command.

## Planned mutation phase

`MCP-003` is the planned mutation phase, but it remains blocked on `HARD-007` authenticated principals. The prerequisite read-only path/response hardening is already implemented. When authorized, it may add only validated tools that wrap existing services:

- prompt-pack validation;
- worktree creation;
- one bounded run launch;
- workflow validate/start/status/resume;
- durable progress, acknowledgement, and steering records.

Before any mutation tool lands, the shared service layer must provide durable idempotency keys, replay-safe result mapping, bounded request contracts, and evidence linking equivalent to the CLI. Future Agent Run and workflow mutation tools must call the same application services as the CLI so every child run emits the same Agent Run contract, command catalog/card bindings, child environment pointers, and immutable digests. Mutation responses should return the Agent Run ID, contract schema, command-catalog digest, role, idempotency identity, and durable result identity where available. A returned tool response is not proof that a child consumed steering; correlated durable acknowledgement remains required.

Destructive lifecycle and review/disposition tools are a later policy-gated phase. Force kill remains excluded. Streamable HTTP requires a separate authorization ADR after local stdio adoption and security evidence.

## Planned tool/resource shape

Read-only resources should remain URI-addressable and bounded. Mutation tools should use typed request/result schemas, stable error categories, idempotency keys, and actor provenance. Tool names must describe existing domain operations rather than expose internal Python functions.

The former implementation prompt pack was retired in the 0.8.0 rewrite. Future MCP work belongs in [BACKLOG.md](BACKLOG.md) with explicit scope and acceptance criteria.

## Acceptance requirements

A mutation release is not complete until black-box MCP client journeys prove:

1. equivalent CLI and MCP operations produce equivalent durable artifacts;
2. duplicate requests do not duplicate launches or journal effects;
3. restart and reconnect preserve idempotency;
4. traversal, symlink, oversize, and unauthorized-root requests fail closed;
5. actor identity and request provenance are sealed;
6. steering remains pending until correlated acknowledgement;
7. no tool can bypass executor/model/class/no-go policy;
8. no transport beyond local stdio is enabled;
9. command capability resources remain parser-derived and read-only rather than becoming dynamic executable tools;
10. MCP-launched child Agent Runs preserve command-context parity with CLI-created Agent Runs.
