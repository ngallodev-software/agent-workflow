from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..errors import WorkflowError
from ..receipts import verify_seal
from .scoring import validate_score_set


def build_report(
    run_dir: Path, *, expected_final_receipt_sha256: str
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    final = verify_seal(
        run_dir, expected_sha256=expected_final_receipt_sha256
    )
    score_set_path = run_dir / "scores" / "score-set.json"
    score_set = None
    if score_set_path.is_file():
        try:
            score_set = json.loads(score_set_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"invalid score set {score_set_path}: {exc}") from exc
        score_set = validate_score_set(
            run_dir,
            score_set,
            final_receipt=final,
            expected_final_receipt_sha256=expected_final_receipt_sha256,
        )
    status = json.loads((run_dir / "final-status.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (run_dir / "run-provenance.json").read_text(encoding="utf-8")
    )
    return {
        "schema": "agent-workflow/evaluation-report/v1",
        "session_id": final.get("session_id"),
        "status": status.get("status"),
        "executor": provenance.get("executor"),
        "executor_version": provenance.get("executor_version"),
        "source_revision": provenance.get("source_revision"),
        "usage": provenance.get("usage"),
        "score_verdict": score_set.get("verdict") if isinstance(score_set, dict) else None,
        "scores": score_set.get("scores", []) if isinstance(score_set, dict) else [],
        "sealed_artifact_count": len(final.get("artifacts", [])),
    }


def render_markdown(value: dict[str, Any]) -> str:
    lines = [
        f"# Evaluation report: {value.get('session_id')}",
        "",
        f"- Status: `{value.get('status')}`",
        f"- Executor: `{value.get('executor') or 'explicit'}`",
        f"- Source revision: `{value.get('source_revision') or 'unavailable'}`",
        f"- Overall deterministic verdict: `{value.get('score_verdict') or 'not-scored'}`",
        f"- Sealed artifacts: {value.get('sealed_artifact_count', 0)}",
        "",
        "## Deterministic scores",
        "",
        "| Scorer | Verdict |",
        "|---|---|",
    ]
    for score in value.get("scores", []):
        lines.append(f"| {score['scorer']['id']} | {score['verdict']} |")
    return "\n".join(lines) + "\n"
