# Evidence boundary — phase 1 (Issue #81)

Status: implementation proposal; no existing authority is retired in this phase.

## Source inventory

| Current source | Responsibility | Decision |
| --- | --- | --- |
| `src/agent_workflow/receipts.py` | Seal and verify run-local artifacts; SHA-256, stable beneath-root reads, final receipt | Extract integrity primitive; keep lifecycle-specific sealing and contract checks |
| `schemas/final-receipt.schema.json` | Agent Run final-receipt/v1 schema | Preserve unchanged; define separate evidence-bundle/v1 |
| `src/agent_workflow/agent_run_artifacts.py` | Worktree links, runner scripts, handoff layout | Keep in Agent-Workflow; never copy into evidence utility |
| `src/agent_workflow/agent_runs.py` | Native job bindings, prepare/restart, run state | Keep; v2/v3 job binding remains workflow-specific |
| `src/agent_workflow/provider_evidence.py` | Semantic provider evidence | Keep optional; not required for independent verification |
| `src/agent_workflow/workflow_receipt.py` | Workflow-level receipt | Keep; do not couple standalone utility to workflow DAG |
| `src/agent_workflow/hierarchy/receipts.py` | Hierarchy/delegation receipts | Keep; no delegation in extracted utility |
| `evals/fixtures/public/evidence-fidelity/` | Existing public fidelity fixture | Reuse in comparative benchmark, do not rewrite history |

## Authority boundaries

1. The agent or host owns command execution, model selection, worktree mutation, and acceptance.
2. The evidence utility owns only byte-level evidence inventory, digest validation, and offline inspection.
3. An evidence bundle attests that bytes match a manifest; it **does not** attest that a command was run, that a model behaved correctly, or that the manifest author is trustworthy.
4. No network, model API, agent-workflow installation, SpecGen, TypeSafe, scheduler, or MCP is required.
5. Capture should be optional and should never change execution authority.

## Phase 1 contract

A small standalone Python module and CLI, `evidence_cli.py`, offers:
- `capture ROOT MANIFEST`: enumerate regular files beneath ROOT, reject symlinks, produce a deterministic JSON manifest at an **external** output path.
- `verify ROOT MANIFEST`: check schema, path uniqueness and normalization, byte sizes, SHA-256, and exact file set; no commands are executed.
- `inspect MANIFEST`: print bounded metadata; no file access or command execution.

The initial contract is `agent-evidence/bundle/v1` with sorted `artifacts` entries (`path`, `size`, `sha256`). This is an **integrity manifest**, not a signed or trusted provenance record. Command execution receipts, optional git revision, atomic publication, and snapshot consistency are future slices and must not be implied by this version.

## Security and failure cases

Fail closed for symlinks, path traversal, absolute paths, duplicate entries, missing or extra files, invalid hashes, unexpected schema fields, and mutated bytes. Root must be a directory; manifest must be external to root. Verification reads regular files without following path-component symlinks on POSIX. Concurrent mutation cannot be completely excluded by a non-snapshot filesystem; later phases should add capture-time stability checks and transactional bundle publication.

## Follow-up

- Phase 2: standalone package entrypoint, durable atomic bundle capture, command receipt metadata, and tests for race/interruption.
- Phase 3: optional Agent-Workflow adapter with unchanged v2/v3 OpenSpec job-binding authority.
- Phase 4: frozen three-arm BM comparison with repeated cohorts, costs, tokens, quality, and evidence integrity.

No deletion of the existing orchestration runtime is authorized by this phase. Run tests after the implementation phase, consistent with project workflow.
