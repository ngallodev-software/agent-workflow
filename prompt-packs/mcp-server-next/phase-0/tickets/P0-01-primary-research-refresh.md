# P0-01 — Primary-source MCP research refresh

## Delegation metadata

- Recommended class: `exploratory`
- Dependencies: P0-00
- Risk: read-only research

## Objective

Verify the protocol, SDK, conformance, host, and security assumptions in the
approved decision against current official sources.

## Writable paths

Only operator-designated phase evidence and a proposed replacement research
reference inside this prompt pack. No production source.

## Procedure and acceptance

Research MCP specification 2025-11-25, official Python SDK stable 1.x pinned at
1.28.1, Inspector/conformance guidance, stdio lifecycle, cancellation/progress,
resource URI templates, tool annotations, and relevant official host behavior.
Record URL, publisher, access date, stable version/commit, direct implication,
and disagreement with current docs. Use primary sources only. Explicitly compare
stable 1.x with the v2 pre-release line and retain 1.28.1 unless evidence requires
a decision gate. Produce a source matrix and bounded recommendations.

## Necessary tests

No production tests. Verify every material claim against the linked primary
source and independently check cited version/tag/commit identifiers.

## Stop conditions

Stop before implementation. Escalate if the stable SDK or selected protocol is
unsupported, unavailable, or incompatible with Python 3.11.
