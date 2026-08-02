"""Dispatch for the ``agent-workflow eval`` command domain."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from ..config import Settings
from ..errors import WorkflowError
from ..evaluation import validate_evaluation
from ..eval.assessment import assess_exported_runs
from ..eval.compare import compare_trials
from ..eval.oracles import resolve_oracle
from ..eval.reporting import build_report, render_markdown
from ..eval.scoring import evaluation_policy_for_run, score_trial
from ..eval.templating import (
    build_benchmark_report,
    build_ledger_row,
    build_lifecycle_archive,
    render_benchmark_markdown,
    validate_benchmark_manifest,
    write_template,
)
from ..eval.trials import collect_trials, load_trials
from ..inspect_adapter import build_task as build_inspect_task
from ..inspect_adapter import run_inspect
from ..integrations.swebench import write_prediction
from ..manifests import validate_pack
from ..receipts import verify_seal_details
from ..state import runs_root
from ..util import atomic_write_bytes, atomic_write_json, expand_path


def _resolve_run(settings: Settings, value: str | Path) -> Path:
    candidate = expand_path(Path(value))
    return candidate if candidate.is_dir() else runs_root(settings) / str(value)


def handle_eval_command(
    settings: Settings,
    args: argparse.Namespace,
) -> tuple[Any, bool]:
    """Return ``(data, output_complete)`` for one parsed evaluation command.

    ``output_complete`` is true only when the handler rendered the complete
    command response itself and the CLI must return without generic rendering.
    """
    if args.eval_command == "validate":
        pack_root = expand_path(args.pack) if args.pack else None
        plan = validate_evaluation(expand_path(args.source), pack_root=pack_root)
        if pack_root is not None:
            report = validate_pack(pack_root, verify_checksums=False)
            if not report.ok:
                raise WorkflowError(
                    "evaluation pack validation failed: " + "; ".join(report.errors)
                )
        return {
            "path": str(plan.path),
            "schema": plan.data["schema"],
            "sha256": plan.sha256,
            "task_ids": list(plan.task_ids),
        }, False

    if args.eval_command == "template":
        return write_template(args.kind, expand_path(args.output)), False

    if args.eval_command == "validate-benchmark":
        source = expand_path(args.source)
        pack_root = expand_path(args.pack) if args.pack else None
        manifest = validate_benchmark_manifest(source, pack_root=pack_root)
        if pack_root is not None:
            report = validate_pack(pack_root, verify_checksums=False)
            if not report.ok:
                raise WorkflowError(
                    "benchmark pack validation failed: " + "; ".join(report.errors)
                )
        return {
            "path": str(source),
            "schema": manifest["schema"],
            "benchmark_id": manifest["benchmark_id"],
            "case_ids": [case["case_id"] for case in manifest["cases"]],
        }, False

    if args.eval_command == "benchmark-report":
        output = expand_path(args.output)
        markdown_output = expand_path(args.markdown) if args.markdown else None
        inputs = {
            expand_path(args.manifest),
            expand_path(args.baseline),
            expand_path(args.candidate),
        }
        if output in inputs or markdown_output in inputs:
            raise WorkflowError("benchmark report output must not overwrite an input")
        if markdown_output is not None and markdown_output == output:
            raise WorkflowError(
                "benchmark JSON and Markdown outputs must be different paths"
            )
        report = build_benchmark_report(
            expand_path(args.manifest),
            expand_path(args.baseline),
            expand_path(args.candidate),
        )
        atomic_write_json(output, report)
        if markdown_output is not None:
            atomic_write_bytes(
                markdown_output,
                render_benchmark_markdown(report).encode("utf-8"),
            )
        return {
            "output": str(output),
            "markdown": str(markdown_output) if markdown_output else None,
            "benchmark_id": report["benchmark_id"],
            "paired_n": report["aggregate_metrics"]["paired_n"],
            "regressions": len(report["regressions"]),
        }, False

    if args.eval_command == "ledger-row":
        output = expand_path(args.output)
        row = build_ledger_row(expand_path(args.run))
        atomic_write_json(output, row)
        return {"output": str(output), **row}, False

    if args.eval_command == "archive-plan":
        output = expand_path(args.output)
        plan = build_lifecycle_archive(
            expand_path(args.run),
            retention_class=args.retention_class,
            exclude_paths=(output,),
        )
        atomic_write_json(output, plan)
        return {
            "output": str(output),
            "run_id": plan["run_id"],
            "retention_class": plan["retention_class"],
            "artifact_count": len(plan["export_contents"]),
        }, False

    if args.eval_command in {"score", "report"}:
        evaluation_run = _resolve_run(settings, args.run)
        if not evaluation_run.is_dir():
            raise WorkflowError(f"run not found: {args.run}")
        if args.eval_command == "score":
            output_dir = (
                expand_path(args.output_dir)
                if args.output_dir
                else evaluation_run / "scores"
            )
            oracle = None
            canary = None
            final_receipt, receipt_digest = verify_seal_details(evaluation_run)
            policy = evaluation_policy_for_run(evaluation_run, final_receipt)
            refs = policy.get("oracle_refs", {})
            ticket = policy.get("ticket_id")
            reference = refs.get(ticket) if isinstance(refs, dict) else None
            if isinstance(reference, dict):
                configured_root = args.oracle_root or os.environ.get(
                    "AGENT_WORKFLOW_ORACLE_ROOT"
                )
                if not configured_root:
                    raise WorkflowError(
                        "evaluation requires --oracle-root or AGENT_WORKFLOW_ORACLE_ROOT"
                    )
                verified = resolve_oracle(
                    str(reference["id"]),
                    str(reference["sha256"]),
                    expand_path(Path(configured_root)),
                )
                canary_path = verified.root / "canary.txt"
                if not canary_path.is_file():
                    raise WorkflowError(f"oracle canary is missing: {canary_path}")
                oracle = verified.manifest
                canary = canary_path.read_bytes()
            data = score_trial(
                evaluation_run,
                output_dir=output_dir,
                oracle=oracle,
                oracle_canary=canary,
                expected_final_receipt_sha256=receipt_digest,
            )
            atomic_write_json(output_dir / "score-set.json", data)
            return data, False

        _receipt, receipt_digest = verify_seal_details(evaluation_run)
        report = build_report(
            evaluation_run,
            expected_final_receipt_sha256=receipt_digest,
        )
        rendered = (
            json.dumps(report, indent=2, sort_keys=True) + "\n"
            if args.format == "json"
            else render_markdown(report)
        )
        if args.output:
            output = expand_path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
            return {"output": str(output), "format": args.format}, False
        print(rendered, end="")
        return None, True

    if args.eval_command == "inspect":
        prompt_path = expand_path(args.prompt)
        if not prompt_path.is_file():
            raise WorkflowError(f"prompt not found: {prompt_path}")
        task = build_inspect_task(
            prompt=prompt_path.read_text(encoding="utf-8"),
            executor=args.executor,
            sample_id=prompt_path.stem,
            dockerfile=expand_path(args.dockerfile),
        )
        return {
            "logs": run_inspect(
                task,
                model=args.model,
                log_dir=expand_path(args.log_dir),
            )
        }, False

    if args.eval_command == "swebench-prediction":
        evaluation_run = _resolve_run(settings, args.run)
        _receipt, receipt_digest = verify_seal_details(evaluation_run)
        output = write_prediction(
            instance_id=args.instance_id,
            model_name_or_path=args.model,
            patch_path=evaluation_run / "patch.diff",
            output=expand_path(args.output),
            final_receipt_sha256=receipt_digest,
        )
        return {"output": str(output)}, False

    if args.eval_command == "collect":
        output = expand_path(args.output)
        evidence = collect_trials([expand_path(path) for path in args.runs], output)
        return {"output": str(output), "trials": len(evidence["trials"])}, False

    if args.eval_command == "compare":
        baseline = load_trials(expand_path(args.baseline))
        candidate = load_trials(expand_path(args.candidate))
        currencies = {
            trial.get("currency")
            for trial in [*baseline, *candidate]
            if trial.get("cost") is not None
        }
        if len(currencies) > 1:
            raise WorkflowError("cannot compare evidence with different currencies")
        output = expand_path(args.output)
        comparison = compare_trials(baseline, candidate)
        atomic_write_json(output, comparison)
        return {"output": str(output), **comparison}, False

    if args.eval_command == "assess-exported-runs":
        # This command is currently exposed as a top-level command rather than
        # an eval subcommand. Keeping the implementation import here would be
        # misleading, so fail closed if a future parser wires it incorrectly.
        raise WorkflowError("assess-exported-runs is not an eval subcommand")

    raise WorkflowError(f"unhandled eval command: {args.eval_command}")
