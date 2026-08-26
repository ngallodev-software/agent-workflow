# Built-in benchmark assets

Canonical built-in benchmark definitions are packaged under:

`src/agent_workflow/assets/benchmarks/`

They use shared immutable layers plus thin suite-specific overlays to avoid duplicating Priority Picker fixtures, evaluator support, policies, profiles, and reference solutions across benchmark versions.

The internal layer layout is packaging detail. Materialize a complete self-contained suite through the public CLI:

```bash
agent-workflow benchmark suite-export /tmp/priority-picker-v2 \
  --benchmark-id priority-picker-v2
```

The exported suite is the structure consumed by validation, planning, execution, scoring, review, consolidation, and publication workflows. Layering must not alter benchmark task, scoring, evaluator, or exported-file identity.

See `docs/BENCHMARKS.md` for the human-readable operating and interpretation guide.
