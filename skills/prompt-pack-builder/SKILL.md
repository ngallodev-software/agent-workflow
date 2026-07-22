---
name: prompt-pack-builder
description: Build validated, self-contained implementation prompt packs with phased tickets, references, terminal delegation rules, and checksums.
---

# Prompt-pack builder

Use this skill to produce the durable prompt-pack format.

## Required archive structure

- root README, execution protocol, and delegation runbook;
- one directory per phase;
- phase README, master prompt, task manifest, and bounded tickets;
- complexity/model tiers and dependency ordering;
- writable paths, acceptance criteria, necessary tests, and stop conditions;
- concrete code structures and interfaces where possible;
- reusable templates and portable helper scripts;
- source references sufficient for a smaller model to avoid guessing;
- internal SHA-256 manifest and external archive checksum;
- validated `.tar.zst` archive.

## Quality rules

A ticket must be independently executable but should not duplicate broad context unnecessarily. Use exact paths and current source evidence. Never use one large prompt as a substitute for dependency ordering or review gates. Keep tests narrow and semantic.
