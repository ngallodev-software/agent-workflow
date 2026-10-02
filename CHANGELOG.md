# Changelog

## 0.12.1 — comparative-eval compatibility patch

- Make the Agent-Workflow package identity unambiguous after the comparative-eval compatibility update: the runtime boundary now requires comparative-eval 0.3.4 while continuing to accept the additive 0.3.1–0.3.4 compatibility range.
- Keep the comparative-eval adoption test in the release gate so future compatibility changes cannot pass CI without exercising the installed-library boundary.
- Preserve all existing Agent-Workflow lifecycle, authority, decision-provider, and evaluation semantics; this patch changes release identity and compatibility gating, not workflow behavior.


## 0.12.0 — initial public preview

This is the first tagged GitHub release of Agent-Workflow. It is intentionally
published as a **prerelease** while clean-host compatibility evidence remains a
release-policy blocker; the attached release evidence records that boundary.

- Add the qualified OpenSpec 1.13.2 -> `source-specification-import/v1` ->
  `native-job/v2` planning import path while preserving legacy
  `native-job/v1` SpecGen/shared-contract compatibility.
- Keep execution scope, deterministic acceptance commands, hidden evaluation
  authority, review, sealing, and lifecycle acceptance owned by Agent-Workflow.
- Ship the durable Agent Run orchestration/evidence lifecycle, restart-safe
  workflows, read-only evidence index, trusted plugin boundary, and optional
  TypeSafe semantic decision provider as GitHub release artifacts.
- Publish wheel, sdist, platform installer bundles, checksums, SBOM, build
  provenance, structured test evidence, and the direct bootstrap installer.
- Distinguish preview publication from a supported release: technical failures
  always block; the currently accepted `REL-003` compatibility-policy blocker
  forces GitHub's prerelease flag rather than being silently waived.

PyPI publication is not part of this release. The base package still has a
digest-pinned direct URL dependency for the frozen legacy shared-contract
wheel; public Python indexes are not the current publication target.


## 0.11.10

- Preserve Choice/Noul/Score probability evidence through the comparative persistence boundary.
- Emit separate neutral observations for `routing.task_class`, `routing.interaction_required`, and `routing.semantic_risk`.
- Persist one shared provider-request record for each batched TypeSafe call so latency/token/cost accounting is not triple-counted.
- Add request identity, projector version, and provider usage to decision evidence/receipts.
- Centralize receipt-to-comparative projection so runtime capture and benchmark studies use the same semantics.
- Require `agent-workflow-comparative-eval==0.2.0` for comparative mode.


- Integrate the Agent-Workflow-specific TypeSafe routing provider into core as an optional `typesafe` extra, using official SDK `Choice`, `Noul`, and `Score` primitives. The former `agent-workflow-typesafe-ai` plugin/package is retired; generic plugin support remains available for independent extensions.

