from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import InstalledProduct
from tests.support import trial


def test_installed_cli_writes_and_validates_deterministic_evaluation_templates(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    tmp_path: Path,
) -> None:
    evaluation_one = tmp_path / "evaluation-one.json"
    evaluation_two = tmp_path / "evaluation-two.json"
    manifest = tmp_path / "benchmark-manifest.json"

    installed_product.json("eval", "template", "evaluation-plan", "--output", evaluation_one, env=product_env)
    installed_product.json("eval", "template", "evaluation-plan", "--output", evaluation_two, env=product_env)
    installed_product.json("eval", "template", "benchmark-manifest", "--output", manifest, env=product_env)

    assert evaluation_one.read_bytes() == evaluation_two.read_bytes()
    validated_plan = installed_product.json("eval", "validate", evaluation_one, env=product_env)
    validated_manifest = installed_product.json("eval", "validate-benchmark", manifest, env=product_env)
    assert validated_plan["task_ids"] == ["EVAL-CASE-001"]
    assert validated_manifest["case_ids"] == ["case-001"]


def test_installed_cli_rejects_identity_drift_and_preserves_missing_evidence(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "benchmark-manifest.json"
    installed_product.json(
        "eval",
        "template",
        "benchmark-manifest",
        "--output",
        manifest_path,
        env=product_env,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    task_id = manifest["cases"][0]["task_id"]

    baseline_trial = trial("baseline", "pass", task_id=task_id)
    baseline_trial.update(
        source_revision=manifest["cohorts"]["baseline"]["source_revision"],
        executor_version=None,
    )
    candidate_trial = trial("candidate", "pass", task_id=task_id)
    candidate_trial.update(source_revision="wrong-revision", executor_version=None)
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    for path, values in (
        (baseline_path, [baseline_trial]),
        (candidate_path, [candidate_trial]),
    ):
        path.write_text(
            json.dumps(
                {
                    "schema": "agent-workflow/trial-evidence/v2",
                    "collected_at": "2026-07-27T00:00:00+00:00",
                    "trials": values,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    rejected = installed_product.run(
        "eval",
        "benchmark-report",
        manifest_path,
        baseline_path,
        candidate_path,
        "--output",
        tmp_path / "rejected.json",
        env=product_env,
    )
    assert rejected.returncode == 2
    assert "source_revision mismatch" in rejected.stderr

    candidate_path.write_text(
        json.dumps(
            {
                "schema": "agent-workflow/trial-evidence/v2",
                "collected_at": "2026-07-27T00:00:00+00:00",
                "trials": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report_path = tmp_path / "missing.json"
    installed_product.json(
        "eval",
        "benchmark-report",
        manifest_path,
        baseline_path,
        candidate_path,
        "--output",
        report_path,
        env=product_env,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["cases"][0]["state"] == "not_verified"
    assert report["cases"][0]["missing_evidence"]["candidate"] == ["trial"]
    assert report["aggregate_metrics"]["paired_n"] == 0

