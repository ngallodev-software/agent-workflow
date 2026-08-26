---
name: prompt-pack-builder
description: Create and validate reproducible host-independent prompt packs with tasks, result contracts, evaluations, and deterministic archives.
---

# Prompt-Pack Builder Skill

Use this skill to create reproducible prompt packs with tasks, result contracts, evaluations, and deterministic archives.

A pack must be host-independent. `pack.yaml` is the single authoritative, versioned machine-readable manifest. Phase directories contain human-readable prompts and runbooks only; do not create per-phase task manifests or a second workflow manifest. It may define:

- phases/tasks and dependencies;
- prompts and writable scope;
- expected outputs;
- result JSON Schemas;
- evaluation commands/policies;
- review requirements;
- completion instructions.

Operational instructions should use `agent-workflow agent-run prepare` and `agent-workflow agent-run start` for headless execution. If a future external host is used, the pack should still define the same durable Agent Run contract and leave host-specific presentation to a separate integration document.

Use schema `agent-workflow/prompt-pack/v1`. Keep task dependencies, Agent Run IDs, prompt paths, result contracts, and optional backlog ownership in root `pack.yaml`. `MANIFEST.json` is reserved for deterministic archive integrity and is never a source-pack workflow manifest.

Validate with `agent-workflow pack validate` and produce deterministic archives with `agent-workflow pack archive`.
