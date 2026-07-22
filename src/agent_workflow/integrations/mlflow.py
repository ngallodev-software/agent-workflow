from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..errors import WorkflowError


def log_report(
    report: Mapping[str, Any],
    *,
    report_path: Path,
    experiment_name: str,
) -> str:
    try:
        import mlflow
    except ModuleNotFoundError as exc:
        raise WorkflowError(
            "MLflow export requires: pip install 'agent-workflow[mlflow]'"
        ) from exc
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run() as active:
        mlflow.log_params(
            {
                "session_id": report.get("session_id"),
                "executor": report.get("executor"),
                "source_revision": report.get("source_revision"),
            }
        )
        mlflow.log_metric(
            "deterministic_pass", float(report.get("score_verdict") == "pass")
        )
        mlflow.log_artifact(str(report_path))
        return str(active.info.run_id)
