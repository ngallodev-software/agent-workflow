---
name: prompt-pack-builder
description: Create and validate reproducible Agent-Workflow prompt packs with tasks, result contracts, evaluations, and deterministic archives.
---

# Prompt-Pack Builder Skill

Use this specialization to create reproducible Agent-Workflow prompt packs.
Follow `skills/agent-workflow/SKILL.md` for execution lifecycle, Agent Run
identity, worker-mode selection, provenance, messaging, recovery, acceptance,
and continuous-improvement boundaries. A pack's instructions can be
host-neutral; its `agent-workflow/prompt-pack/v1` manifest is Agent-Workflow
specific.

`pack.yaml` is the single authoritative, versioned machine-readable workflow/task manifest. Phase directories contain human-readable prompts and runbooks only; do not create a second workflow manifest. A pack may define phases/tasks and dependencies, prompts and writable scope, expected outputs, result JSON Schemas, evaluation commands/policies, review requirements, and completion instructions.

Use schema `agent-workflow/prompt-pack/v1`. Keep task dependencies, Agent Run IDs, prompt paths, result contracts, and optional backlog ownership in root `pack.yaml`. `MANIFEST.json` is reserved for deterministic archive integrity and is never a source-pack workflow manifest.

Validate with `agent-workflow pack validate` and produce deterministic archives with `agent-workflow pack archive`. When executing pack work, use the primary skill's normal `agent-workflow delegate` facade unless recovery, diagnostics, or explicit operator control requires lower-level lifecycle commands. External hosts remain presentation/execution adapters and do not alter the pack's durable Agent Run contract.
