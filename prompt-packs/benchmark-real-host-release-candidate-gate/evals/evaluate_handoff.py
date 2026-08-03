#!/usr/bin/env python3
"""Validate and score the real-host benchmark handoff evidence.

The score is diagnostic only. Acceptance requires every mandatory check to pass,
100/100, and an independent gate decision of ``accept``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "evaluation-manifest.json"
TEMPLATE_PATH = HERE.parent / "templates" / "eval-results.template.json"
ALLOWED_STATES = {"pass", "fail", "blocked", "not_run"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    checks = manifest.get("checks")
    if not isinstance(checks, list) or not checks:
        return ["manifest checks must be a non-empty array"]
    seen: set[str] = set()
    total = 0
    for item in checks:
        if not isinstance(item, dict):
            errors.append("manifest check is not an object")
            continue
        check_id = item.get("id")
        if not isinstance(check_id, str) or not check_id:
            errors.append("manifest check missing id")
            continue
        if check_id in seen:
            errors.append(f"duplicate manifest check: {check_id}")
        seen.add(check_id)
        points = item.get("max_points")
        if not isinstance(points, int) or points <= 0:
            errors.append(f"invalid points for {check_id}")
        else:
            total += points
    if total != manifest.get("total_points") or total != 100:
        errors.append(f"manifest points total {total}, expected 100")
    return errors


def safe_evidence_path(root: Path, relative: str) -> tuple[Path | None, str | None]:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None, f"evidence escapes root: {relative}"
    if not candidate.exists():
        return None, f"missing evidence: {relative}"
    if candidate.is_symlink() or not candidate.is_file():
        return None, f"evidence is not a regular file: {relative}"
    return candidate, None


def evaluate(evidence_root: Path, results: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if results.get("schema") != "agent-workflow/benchmark-host-gate-evidence/v1":
        errors.append("unexpected or missing evidence schema")
    rows = results.get("checks")
    if not isinstance(rows, list):
        rows = []
        errors.append("checks must be an array")
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            errors.append("invalid check result entry")
            continue
        check_id = row["id"]
        if check_id in by_id:
            errors.append(f"duplicate result check: {check_id}")
        by_id[check_id] = row

    manifest_ids = {item["id"] for item in manifest["checks"]}
    for unknown in sorted(set(by_id) - manifest_ids):
        errors.append(f"unknown result check: {unknown}")

    score = 0
    check_reports: list[dict[str, Any]] = []
    mandatory_failures: list[str] = []
    for item in manifest["checks"]:
        check_id = item["id"]
        row = by_id.get(check_id)
        if row is None:
            state = "not_run"
            summary = "missing result"
            evidence_rows = []
            errors.append(f"missing required check result: {check_id}")
        else:
            state = row.get("state")
            summary = row.get("summary")
            evidence_rows = row.get("evidence")
            if state not in ALLOWED_STATES:
                errors.append(f"invalid state for {check_id}: {state!r}")
                state = "fail"
            if not isinstance(summary, str) or not summary.strip():
                errors.append(f"missing summary for {check_id}")
                summary = "missing summary"
            if not isinstance(evidence_rows, list):
                errors.append(f"evidence must be an array for {check_id}")
                evidence_rows = []

        evidence_report: list[dict[str, Any]] = []
        for evidence in evidence_rows:
            if not isinstance(evidence, dict) or not isinstance(evidence.get("path"), str):
                errors.append(f"invalid evidence entry for {check_id}")
                continue
            relative = evidence["path"]
            path, path_error = safe_evidence_path(evidence_root, relative)
            actual = None
            valid = path_error is None
            if path_error:
                errors.append(f"{check_id}: {path_error}")
            elif path is not None:
                actual = sha256(path)
                expected = evidence.get("sha256")
                if expected is not None and expected != actual:
                    valid = False
                    errors.append(f"{check_id}: sha256 mismatch for {relative}")
            evidence_report.append({"path": relative, "valid": valid, "sha256": actual})

        if state == "pass" and not evidence_report:
            errors.append(f"passing check has no evidence: {check_id}")
            state = "fail"
        if state == "pass" and any(not value["valid"] for value in evidence_report):
            state = "fail"
        earned = int(item["max_points"]) if state == "pass" else 0
        score += earned
        if item.get("required", True) and state != "pass":
            mandatory_failures.append(check_id)
        check_reports.append({
            "id": check_id,
            "domain": item["domain"],
            "state": state,
            "summary": summary,
            "earned_points": earned,
            "max_points": item["max_points"],
            "evidence": evidence_report,
        })

    gate = results.get("independent_gate")
    gate_decision = gate.get("decision") if isinstance(gate, dict) else None
    if gate_decision not in {"accept", "reject", "blocked"}:
        errors.append("invalid or missing independent gate decision")
    accepted = (
        not errors
        and not mandatory_failures
        and score == manifest["acceptance"]["required_score"]
        and gate_decision == manifest["acceptance"]["independent_gate_decision"]
    )
    verdict = "accepted" if accepted else ("blocked" if gate_decision == "blocked" else "rejected")
    return {
        "schema": "agent-workflow/benchmark-host-gate-evaluation-report/v1",
        "verdict": verdict,
        "score": score,
        "maximum_score": 100,
        "mandatory_failures": mandatory_failures,
        "independent_gate_decision": gate_decision,
        "errors": errors,
        "warnings": warnings,
        "checks": check_reports,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Benchmark real-host handoff evaluation",
        "",
        f"- Verdict: **{report['verdict']}**",
        f"- Score: **{report['score']}/{report['maximum_score']}**",
        f"- Independent gate: **{report.get('independent_gate_decision')}**",
        "",
        "## Checks",
        "",
        "| ID | State | Points | Summary |",
        "|---|---|---:|---|",
    ]
    for item in report["checks"]:
        summary = str(item["summary"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {item['id']} | {item['state']} | {item['earned_points']}/{item['max_points']} | {summary} |")
    if report["errors"]:
        lines += ["", "## Errors", ""] + [f"- {value}" for value in report["errors"]]
    if report["mandatory_failures"]:
        lines += ["", "## Mandatory failures", ""] + [f"- {value}" for value in report["mandatory_failures"]]
    lines += ["", "Acceptance requires 100/100, every mandatory check passing, and an independent `accept` decision.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    manifest = read_json(MANIFEST_PATH)
    manifest_errors = validate_manifest(manifest)
    if args.self_test:
        template = read_json(TEMPLATE_PATH)
        if template.get("schema") != "agent-workflow/benchmark-host-gate-evidence/v1":
            manifest_errors.append("template schema mismatch")
        if manifest_errors:
            print(json.dumps({"valid": False, "errors": manifest_errors}, indent=2))
            return 1
        print(json.dumps({"valid": True, "checks": len(manifest["checks"]), "points": 100}, indent=2))
        return 0

    if not args.evidence_root or not args.results or not args.output_dir:
        parser.error("--evidence-root, --results, and --output-dir are required unless --self-test is used")
    if manifest_errors:
        print(json.dumps({"valid": False, "errors": manifest_errors}, indent=2))
        return 1
    evidence_root = args.evidence_root.resolve()
    results = read_json(args.results.resolve())
    report = evaluate(evidence_root, results, manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "evaluation-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "evaluation-report.md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "score": report["score"], "errors": len(report["errors"])}, indent=2))
    return 0 if report["verdict"] == "accepted" else 1


if __name__ == "__main__":
    sys.exit(main())
