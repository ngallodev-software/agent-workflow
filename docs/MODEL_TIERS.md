# Model and Delegation Tiers

The tiers describe reasoning and risk requirements, not product-specific model names.

## Tier A

Use for security-sensitive changes, data migrations, authority-boundary changes, cross-repository contracts, destructive cleanup, and independent final review.

## Tier B

Use for bounded production implementation with explicit interfaces, paths, and acceptance tests. A stronger reviewer is appropriate when the change affects shared contracts.

## Tier C

Use for deterministic inventory, documentation truth corrections, manifest generation, simple wrappers, and read-only preflight work. The prompt must still contain exact paths and stop conditions.

## Composite labels

- `B_with_A_gate`: bounded implementation with a high-reasoning reviewer.
- `A_reviewer`: independent review only.

Do not assign a smaller model to “figure out the architecture.” Ownership decisions and code shapes belong in pack references before delegation.
