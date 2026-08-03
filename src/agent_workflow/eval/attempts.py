"""Post-seal attempt projections that never alter acceptance authority."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..errors import WorkflowError
from ..receipts import read_sealed_contract, verify_seal_details
from ..util import atomic_write_bytes, atomic_write_json
from .outcomes import classify_attempt
from .reporting import build_report, render_markdown
from .scoring import evaluation_policy_for_run, score_trial
from .templating import build_ledger_row




def _completion_result(
    run_dir: Path, final_receipt: Mapping[str, Any]
) -> tuple[str | None, dict[str, Any] | None]:
    try:
        collection, _ = read_sealed_contract(
            run_dir,
            dict(final_receipt),
            "collections/completion.json",
            "agent-workflow/completion-collection/v1",
        )
    except WorkflowError:
        return None, None
    value = collection.get("validation_status")
    return (str(value) if value in {"valid", "missing", "invalid"} else None), collection


def emit_attempt_artifacts(run_dir: Path) -> dict[str, Any]:
    """Create deterministic post-seal evaluation and ledger projections.

    These files summarize immutable evidence. They are deliberately excluded
    from the final receipt and cannot make a run accepted.
    """
    run_dir = run_dir.resolve()
    final, digest = verify_seal_details(run_dir)
    status, _ = read_sealed_contract(
        run_dir, final, "final-status.json", "agent-workflow/session-status/v2"
    )
    completion_result, _collection = _completion_result(run_dir, final)
    policy = evaluation_policy_for_run(run_dir, final)
    sealed_paths = {
        item.get("path")
        for item in final.get("artifacts", [])
        if isinstance(item, dict)
    }
    evaluation_planned = bool(
        policy
        or "evaluation-runtime.json" in sealed_paths
        or status.get("evaluation_path")
    )

    score_verdict: str | None = None
    report_path: str | None = None
    if evaluation_planned:
        scores_dir = run_dir / "scores"
        score_set = score_trial(
            run_dir,
            output_dir=scores_dir,
            expected_final_receipt_sha256=digest,
        )
        atomic_write_json(scores_dir / "score-set.json", score_set)
        score_verdict = str(score_set.get("verdict"))
        report = build_report(run_dir, expected_final_receipt_sha256=digest)
        reports_dir = run_dir / "reports"
        atomic_write_json(reports_dir / "evaluation.json", report)
        atomic_write_bytes(
            reports_dir / "evaluation.md", render_markdown(report).encode("utf-8")
        )
        report_path = "reports/evaluation.md"

    ledger = build_ledger_row(run_dir)
    atomic_write_json(run_dir / "ledger-row.json", ledger)
    classification = classify_attempt(
        status,
        completion_result=completion_result,
    )
    return {
        "evaluation_state": ledger["evaluation_state"],
        "evaluation_result": score_verdict,
        "attempt_classification": classification,
        "ledger_row_path": str(run_dir / "ledger-row.json"),
        "evaluation_report_path": (
            str(run_dir / report_path) if report_path is not None else None
        ),
    }
