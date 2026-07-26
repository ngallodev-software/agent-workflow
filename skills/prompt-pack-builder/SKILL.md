---
name: prompt-pack-builder
description: Build validated, self-contained agent-workflow prompt packs with phased tickets, references, lifecycle instructions, and checksums.
---

# Prompt-pack builder

Use this skill when bounded work needs isolated worktrees, persistent evidence, independent review, recovery, or ordered multi-ticket execution. Small one-step local edits do not require a ceremonial pack. Use [`agent-workflow-orchestrator`](../agent-workflow-orchestrator/SKILL.md) to validate and launch the completed pack.

## Required archive structure

- root README, execution protocol, and delegation runbook;
- one directory per phase;
- phase README, master prompt, task manifest, and bounded tickets;
- complexity/model tiers, `backlog_id` ownership, and dependency ordering;
- writable paths, acceptance criteria, necessary tests, and stop conditions;
- concrete code structures and interfaces where possible;
- reusable templates and portable helper scripts;
- source references sufficient for a smaller model to avoid guessing;
- internal SHA-256 manifest and external archive checksum;
- validated `.tar.zst` archive.

## Operational requirements

The generated README and runbook must name `agent-workflow pack validate`, `agent-workflow worktree create`, and `agent-workflow launch`. They must state that a valid current tmux context produces a visible pane through `agent-workflow launch`, while an unusable context falls back to a detached named session. They must also state that native host subagents are not durable workflow runs unless explicitly bridged through the CLI.

## Quality rules

A ticket must be independently executable but should not duplicate broad context unnecessarily. Parallel tickets use separate worktrees and sessions; absence of a dependency edge permits concurrency, while integration and gate review remain serialized. Use exact paths and current source evidence. Never use one large prompt as a substitute for dependency ordering or review gates. Keep tests narrow and semantic.

## Workflow-aware packs

When tickets form a graph, declare cross-phase dependencies and optional structured result contracts explicitly. Prefer one of the authorized workflow templates when its shape fits. Define every downstream input as a named bounded JSON Pointer binding with required/optional behavior; never instruct children to scrape arbitrary predecessor files. Include terminal workflow sealing and independent phase review in acceptance criteria. Repository-owned packs must pass the `release-drift-auditor` ownership/collision checks before archive creation.
