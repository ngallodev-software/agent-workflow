# Collision and ownership analysis

## Canonical ownership

| Backlog item | Owner after this pack is added | Collision result |
|---|---|---|
| BKL-001 | `orchestrator-two-way-messaging` | Previously active but unowned by any prompt pack; safe to claim. |
| BKL-002 | `orchestrator-two-way-messaging` | Previously active but unowned by any prompt pack; safe to claim. |
| MSG-001 through MSG-007 | `orchestrator-two-way-messaging` | New namespace; no prior task or pack uses these IDs. |
| DEC-001 | No prompt-pack owner | Decision prerequisite only; this pack may not resolve it implicitly. |
| HARD-001 through HARD-010 | Existing hardening packs | Prerequisites only; no ticket in this pack claims them. |
| MCP-003 | `mcp-server-next` | Remains separate. Shared messaging services may later be exposed through MCP only after MCP-003 authorization and gates. |
| REL-* | Existing release pack or backlog | Not owned by this pack. |

## Scope boundaries

This pack implements the local messaging substrate and public CLI/service behavior. It does not:

- duplicate the bounded process substrate (`HARD-001`);
- duplicate no-follow artifact integrity (`HARD-002`);
- duplicate immutable launch authority (`HARD-004`);
- duplicate sensitive-content controls (`HARD-006`);
- duplicate authenticated principals (`HARD-007`);
- duplicate configuration/executable trust (`HARD-008`);
- implement MCP mutation tools (`MCP-003`);
- resolve the multi-host architecture decision (`DEC-003`).

## Drift gate

Before each phase:

1. Re-read `BACKLOG.md` and all `prompt-packs/*/pack.yaml` files.
2. Run `python3 scripts/audit-release-assets.py`.
3. Reject execution when another pack claims any owned backlog item or task ID.
4. Reject implementation when a prerequisite has moved, been superseded, or changed its authority boundary.
5. Update this file, the pack manifests, and `docs/PROMPT_PACKS.md` together when ownership changes.
