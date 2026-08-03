# Evidence model

## Directory layout

```text
handoff-evidence/
├── baseline/
├── local-gates/
├── runs/
│   ├── codex-fast-rc/
│   ├── claude-fast-rc/
│   ├── full-v2-rc/
│   └── cancel-rc/
├── reviews/
├── defects/
├── eval-results.json
├── final-gate-review.md
└── final-evaluation/
```

## Evidence rules

- Paths in `eval-results.json` are relative to `handoff-evidence/`.
- Evidence must be regular files, not symlinks.
- Sensitive provider authentication files must never be copied.
- Private blinding mappings may be retained in a restricted subdirectory but must not be exposed to UI reviewers before submission.
- Raw run evidence remains in the coordinator run directory; copy or archive it without editing and record its digest.
- Every repair creates a new run ID and a lineage note. Do not replace failed evidence.
- Hash the final evidence tree and archive after the independent review.

## Minimum run evidence

Each real-provider run should include:

- run-plan path and copy;
- tmux snapshots before/after;
- pane-monitor summary and captures;
- command transcript;
- status and verify output;
- run directory archive or manifest;
- report and score receipts;
- live-review status and HTTP probes;
- review assignment/template/submission where applicable;
- cleanup results.
