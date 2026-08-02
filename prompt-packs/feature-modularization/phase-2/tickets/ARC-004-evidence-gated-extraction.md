# ARC-004 — extract one proven optional subsystem

**Backlog:** `ARC-004`  
**Priority:** P2 / High

## Gate

Do not execute extraction until PLUG-001 is accepted and the separately distributed first-party spec plugin has stable real-world evidence. If that evidence is absent, produce only a refreshed extraction recommendation and stop.

## Goal

Select exactly one optional subsystem whose authority/service boundary is already stable, then move it to a separately versioned first-party distribution through the accepted plugin/optional-feature contract.

## Selection criteria

Choose the candidate with the clearest dependency inversion, smallest migration surface, independent release value, and strongest installed-product proof. Preserve compatibility shims and rollback. Do not split multiple subsystems or rename the core distribution.

## Acceptance

Base installation remains functional without the extracted feature; explicit installation/enabling restores it; authority/evidence compatibility is preserved; clean install/upgrade/rollback journeys pass; release ownership and version compatibility are documented.

## Writable paths

Only the selected subsystem, its compatibility facade/adapter, package/release metadata for the new distribution, focused migration tests, and directly related documentation.

## Tests

Prove clean base install without the feature, explicit feature install/enablement, upgrade and rollback, artifact compatibility, and unchanged core authority journeys.

## Stop conditions

Stop with a recommendation-only report if first-party plugin evidence is absent, more than one subsystem is proposed, or the candidate lacks a stable service and ownership boundary.

