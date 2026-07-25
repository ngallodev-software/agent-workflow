# P0-02 — Independent architecture review and executable plan

## Delegation metadata

- Recommended class: `review`
- Dependencies: P0-01
- Risk: architecture and security judgment

## Objective

Independently review the MCP decision and current scaffold, then produce a
dependency-ordered implementation plan, bounded tickets, and revised prompt pack.

## Required checks

Trace each proposed MCP operation to the authoritative Python service and durable
artifact. Threat-model traversal, symlink escape, secret leakage, confused deputy,
cross-run access, replay, false delivery claims, and denial of service. Confirm
that stdio remains local, MCP remains an adapter, and HTTP/destructive surfaces
remain excluded. Identify CLI parsing mixed with domain behavior.

## Deliverables and acceptance

Provide a decision-delta table, module/API outline, error taxonomy, compatibility
plan, test matrix, dependency graph, individually executable tickets, model/class
routing, exact writable paths, stop conditions, and independent phase gates.
Validate the revised pack. No implementation source may change.
