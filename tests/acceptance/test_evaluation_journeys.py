from __future__ import annotations

import json
import time
from pathlib import Path

from tests.conftest import (
    InstalledProduct,
    fake_agent_path,
    git_repo,
    wait_for_status,
    write_config,
)


def test_sealed_evaluation_runs_score_report_collect_and_compare_through_installed_cli(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "evaluation-task.md"
    prompt.write_text("Inspect README.md without modifying the repository.\n", encoding="utf-8")
    plan = tmp_path / "evaluation.json"
    plan.write_text(
        json.dumps(
            {
                "schema": "agent-workflow/evaluation-plan/v1",
                "dataset_split": "development",
                "task_ids": ["EVAL-1"],
                "repetitions": 1,
                "timeout_seconds": 60,
                "max_retries": 0,
                "scorers": ["schema_validity", "writable_scope"],
                "scope": {
                    "writable_paths": [],
                    "writable_trees": [],
                    "disposable_trees": [".agent-workflow-handoff/", ".delegations/"],
                },
                "sandbox": "docker",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    config = write_config(product_env, fake_agent=fake_agent_path)
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "structured"
    state_runs = Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs"

    validated = installed_product.json("eval", "validate", plan, env=env)
    assert validated["task_ids"] == ["EVAL-1"]

    evidence_files: list[Path] = []
    run_dirs: list[Path] = []
    for session_id in ("baseline-eval", "candidate-eval"):
        installed_product.json(
            "launch",
            session_id,
            repo,
            prompt,
            "--ticket",
            "EVAL-1",
            "--tier",
            "low",
            "--evaluation",
            plan,
            "--config",
            config,
            "--executor",
            "codex",
            "--structured",
            "--no-interactive",
            env=env,
        )
        status = wait_for_status(env, session_id)
        assert status["status"] == "completed"
        run_dir = state_runs / session_id
        run_dirs.append(run_dir)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not (run_dir / "ledger-row.json").is_file():
            time.sleep(0.05)
        assert (run_dir / "scores" / "score-set.json").is_file()
        assert (run_dir / "reports" / "evaluation.md").is_file()
        assert (run_dir / "ledger-row.json").is_file()
        auto_ledger = json.loads((run_dir / "ledger-row.json").read_text(encoding="utf-8"))
        assert auto_ledger["receipt_verification"] == "verified"
        assert auto_ledger["attempt_classification"] == "acceptance-eligible"
        assert auto_ledger["acceptance_eligible"] is True

        score = installed_product.json("eval", "score", run_dir, env=env)
        assert score["verdict"] == "pass"
        assert {item["scorer"]["id"] for item in score["scores"]} >= {
            "schema_validity",
            "writable_scope",
        }

        report = run_dir / "reports" / "evaluation.md"
        rendered = installed_product.json(
            "eval", "report", run_dir, "--format", "markdown", "--output", report, env=env
        )
        assert rendered["output"] == str(report)
        assert "Overall deterministic verdict: `pass`" in report.read_text(encoding="utf-8")

        evidence = run_dir / "trials.json"
        collected = installed_product.json("eval", "collect", run_dir, "--output", evidence, env=env)
        assert collected["trials"] == 1
        trial = json.loads(evidence.read_text(encoding="utf-8"))["trials"][0]
        assert trial["task_id"] == "EVAL-1"
        assert trial["verdict"] == "pass"
        assert trial["input_tokens"] == 5
        assert trial["output_tokens"] == 3
        evidence_files.append(evidence)

        installed_product.json(
            "review",
            session_id,
            "--actor",
            "fixture-reviewer",
            "--reason",
            "deterministic fixture review",
            env=env,
        )
        completion = json.loads((run_dir / "completion.json").read_text(encoding="utf-8"))
        installed_product.json(
            "accept",
            session_id,
            "--actor",
            "fixture-reviewer",
            "--reason",
            "fixture evidence accepted",
            "--revision",
            completion["head_revision"],
            env=env,
        )

    comparison_path = tmp_path / "comparison.json"
    comparison = installed_product.json(
        "eval",
        "compare",
        evidence_files[0],
        evidence_files[1],
        "--output",
        comparison_path,
        env=env,
    )
    assert comparison["paired_n"] == 1
    assert comparison["winner"] is None
    assert comparison["baseline"]["rate"] == 1.0
    assert comparison["candidate"]["rate"] == 1.0
    assert json.loads(comparison_path.read_text(encoding="utf-8"))["schema"] == "agent-workflow/comparison/v1"

    manifest_path = tmp_path / "benchmark-manifest.json"
    installed_product.json(
        "eval", "template", "benchmark-manifest", "--output", manifest_path, env=env
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    baseline_trial = json.loads(evidence_files[0].read_text(encoding="utf-8"))["trials"][0]
    candidate_trial = json.loads(evidence_files[1].read_text(encoding="utf-8"))["trials"][0]
    for role, item in (("baseline", baseline_trial), ("candidate", candidate_trial)):
        manifest["cohorts"][role].update(
            provider=item["provider"],
            source_revision=item["source_revision"],
            pack_manifest_sha256=item["pack_manifest_sha256"],
            model=item["model"],
            executor=item["executor"],
            executor_version=item["executor_version"],
        )
    manifest["cases"][0].update(
        case_id="eval-1",
        task_id="EVAL-1",
        repetition=0,
        prompt_sha256=baseline_trial["prompt_sha256"],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    installed_product.json("eval", "validate-benchmark", manifest_path, env=env)

    benchmark_json = tmp_path / "benchmark-report.json"
    benchmark_md = tmp_path / "benchmark-report.md"
    benchmark = installed_product.json(
        "eval",
        "benchmark-report",
        manifest_path,
        evidence_files[0],
        evidence_files[1],
        "--output",
        benchmark_json,
        "--markdown",
        benchmark_md,
        env=env,
    )
    assert benchmark["paired_n"] == 1
    assert benchmark["regressions"] == 0
    assert "Winner: `not-established`" in benchmark_md.read_text(encoding="utf-8")

    ledger_path = run_dir / "ledger-row.json"
    ledger = installed_product.json(
        "eval", "ledger-row", run_dir, "--output", ledger_path, env=env
    )
    assert ledger["receipt_verification"] == "verified"
    assert ledger["evaluation_state"] == "verified"
    assert ledger["evaluation_result"] == "pass"
    assert ledger["disposition"] == "accepted"

    assessment_path = tmp_path / "sealed-run-assessment.json"
    assessment = installed_product.json(
        "assess-sealed-runs",
        state_runs,
        "--output",
        assessment_path,
        env=env,
    )
    candidate_assessment = next(
        row for row in assessment["runs"] if row["run_id"] == "candidate-eval"
    )
    assert candidate_assessment["comparable"] is True
    assert candidate_assessment["phase_acceptance"] == "accepted"
    assert candidate_assessment["scope_audit"]["state"] == "verified"

    archive_path = run_dir / "archive-plan.json"
    archive = installed_product.json(
        "eval", "archive-plan", run_dir, "--output", archive_path, env=env
    )
    assert archive["artifact_count"] > 0
    first_archive_bytes = archive_path.read_bytes()
    installed_product.json(
        "eval", "archive-plan", run_dir, "--output", archive_path, env=env
    )
    assert archive_path.read_bytes() == first_archive_bytes
    archive_value = json.loads(archive_path.read_text(encoding="utf-8"))
    assert archive_value["transfer_checksum"]["required_in_repository"] is False
    assert all(not item["path"].endswith(".sha256") for item in archive_value["export_contents"])

    for session_id in ("baseline-eval", "candidate-eval"):
        installed_product.json("terminate", session_id, "--grace-seconds", "0", env=env)
        assert not (Path(env["FAKE_TMUX_STATE"]) / f"{session_id}.json").exists()


def test_installed_evidence_repair_preserves_source_and_projects_supplemental_history(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    tmp_path: Path,
) -> None:
    from agent_workflow.receipts import final_receipt_sha256, make_read_only, seal_run
    from agent_workflow.util import atomic_write_json
    from tests.support import write_minimal_run

    state = Path(product_env["XDG_STATE_HOME"]) / "agent-workflow"
    source_run = state / "runs" / "source-review-run"
    write_minimal_run(source_run, session_id="source-review-run")
    atomic_write_json(
        source_run / "result.json",
        {
            "schema": "tax-machine/completion/v0",
            "session_id": "source-review-run",
            "ticket_id": "P1-REV-001",
            "pack_id": "tax-machine-backlog-v1",
            "result": "changes_requested",
            "disposition": "changes_requested",
            "base_revision": "base",
            "head_revision": "head",
            "changed_files": [],
            "criteria": [
                {"id": "review", "result": "fail", "evidence": ["durability gap"]}
            ],
            "commands": [
                {
                    "argv": ["pytest", "-q"],
                    "cwd": "/repo",
                    "exit_code": 0,
                    "receipt": "1 passed",
                }
            ],
            "unresolved": ["durability gap"],
            "usage": None,
        },
    )
    seal_run(source_run, session_id="source-review-run")
    make_read_only(source_run)
    digest = final_receipt_sha256(source_run)
    source_before = {
        path.relative_to(source_run).as_posix(): path.read_bytes()
        for path in source_run.rglob("*")
        if path.is_file() and path.name != "seal.lock"
    }

    created = installed_product.json(
        "evidence",
        "repair",
        "--source-run",
        "source-review-run",
        "--source-receipt",
        digest,
        "--artifact",
        "result.json",
        "--output-run",
        "source-review-repair",
        "--actor",
        "coordinator",
        env=product_env,
    )
    assert created["idempotent"] is False
    repeated = installed_product.json(
        "evidence",
        "repair",
        "--source-run",
        "source-review-run",
        "--source-receipt",
        digest,
        "--artifact",
        "result.json",
        "--output-run",
        "source-review-repair",
        "--actor",
        "coordinator",
        env=product_env,
    )
    assert repeated["idempotent"] is True
    verified = installed_product.json(
        "evidence", "verify", "source-review-repair", env=product_env
    )
    assert verified["validation_result"] == "valid"
    listed = installed_product.json(
        "evidence", "list", "--source-run", "source-review-run", env=product_env
    )
    assert listed["count"] == 1
    assert listed["repairs"][0]["validation_result"] == "valid"
    assert source_before == {
        path.relative_to(source_run).as_posix(): path.read_bytes()
        for path in source_run.rglob("*")
        if path.is_file() and path.name != "seal.lock"
    }

    installed_product.json("index", "rebuild", env=product_env)
    indexed = installed_product.json(
        "index", "query", "repairs", "--session", "source-review-run", env=product_env
    )
    assert indexed["rows"][0]["repair_id"] == "source-review-repair"
    assert indexed["rows"][0]["source_final_receipt_sha256"] == digest
