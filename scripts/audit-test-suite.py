#!/usr/bin/env python3
"""Fail closed when the repository test suite drifts from its authority model."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "tests" / "test-authority.json"
ALLOWED_AUTHORITIES = {
    "accounting",
    "durability",
    "evaluation",
    "path-security",
    "process",
    "release-evidence",
    "replay",
    "scheduler",
}
FORBIDDEN_INVARIANT_IMPORT_PREFIXES = (
    "agent_workflow.cli_handlers",
    "agent_workflow.cli_parser",
    "agent_workflow.cli_runtime",
)


@dataclass(frozen=True)
class FileMetrics:
    path: str
    test_functions: int
    subprocess_calls: int
    wheel_build_sites: int
    uses_mocking: bool
    private_imports: tuple[str, ...]
    imported_modules: tuple[str, ...]


def _load_policy(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read test authority policy {path}: {exc}") from exc
    if value.get("schema") != "agent-workflow/test-authority/v1":
        raise SystemExit(f"unsupported test authority schema in {path}")
    return value


def _module_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _module_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return None


def _literal_strings(node: ast.AST) -> list[str]:
    values: list[str] = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        values.append(node.value)
    elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for item in node.elts:
            values.extend(_literal_strings(item))
    return values


def _measure_file(path: Path) -> FileMetrics:
    relative = path.relative_to(ROOT).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    test_functions = sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        for node in tree.body
    )
    imported_modules: set[str] = set()
    private_imports: set[str] = set()
    uses_mocking = False
    subprocess_calls = 0
    wheel_build_sites = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
                if alias.name == "unittest.mock":
                    uses_mocking = True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported_modules.add(module)
            if module == "unittest.mock":
                uses_mocking = True
            for alias in node.names:
                if alias.name.startswith("_"):
                    private_imports.add(f"{module}.{alias.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(argument.arg == "monkeypatch" for argument in node.args.args):
                uses_mocking = True
        elif isinstance(node, ast.Call):
            called = _module_name(node.func)
            if called in {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call"}:
                subprocess_calls += 1
                command_strings: list[str] = []
                if node.args:
                    command_strings = _literal_strings(node.args[0])
                if "pip" in command_strings and "wheel" in command_strings:
                    wheel_build_sites += 1

    return FileMetrics(
        path=relative,
        test_functions=test_functions,
        subprocess_calls=subprocess_calls,
        wheel_build_sites=wheel_build_sites,
        uses_mocking=uses_mocking,
        private_imports=tuple(sorted(private_imports)),
        imported_modules=tuple(sorted(imported_modules)),
    )


def _test_files(relative_root: str) -> list[Path]:
    root = ROOT / relative_root
    if root.is_file():
        return [root]
    return sorted(root.glob("test_*.py")) if root.is_dir() else []


def _collect_count(relative_root: str) -> tuple[int, str | None]:
    command = [sys.executable, "-m", "pytest", "--collect-only", "-q", relative_root]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )
    if result.returncode:
        detail = (result.stdout + result.stderr).strip()
        return 0, f"collection failed for {relative_root}: {detail}"
    return sum("::" in line for line in result.stdout.splitlines()), None


def _junit_metrics(path: Path) -> tuple[int, float, int]:
    root = ET.parse(path).getroot()
    testcases = list(root.findall(".//testcase"))
    collection_skips = 0
    executed_cases = 0
    for testcase in testcases:
        skipped = testcase.find("skipped")
        if (
            testcase.attrib.get("classname", "") == ""
            and skipped is not None
            and skipped.attrib.get("message") == "collection skipped"
        ):
            collection_skips += 1
            continue
        executed_cases += 1
    if root.tag == "testsuite":
        duration = float(root.attrib.get("time", "0"))
    else:
        duration = sum(
            float(suite.attrib.get("time", "0"))
            for suite in root.findall("testsuite")
        )
    return executed_cases, duration, collection_skips


def audit(
    policy: dict[str, Any],
    *,
    policy_path: Path,
    collect: bool,
    junit: Path | None,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    report: dict[str, Any] = {
        "schema": "agent-workflow/test-suite-audit/v1",
        "policy": str(policy_path.resolve().relative_to(ROOT.resolve()))
        if policy_path.resolve().is_relative_to(ROOT.resolve())
        else str(policy_path.resolve()),
        "layers": {},
        "static": {},
        "junit": None,
    }
    all_metrics: list[FileMetrics] = []

    for layer, expected in policy["layers"].items():
        files = _test_files(expected["path"])
        metrics = [_measure_file(path) for path in files]
        all_metrics.extend(metrics)
        functions = sum(item.test_functions for item in metrics)
        collected: int | None = None
        if collect:
            collected, collection_error = _collect_count(expected["path"])
            if collection_error:
                errors.append(collection_error)
        observed = {
            "path": expected["path"],
            "files": len(files),
            "test_functions": functions,
            "collected_cases": collected,
            "subprocess_calls": sum(item.subprocess_calls for item in metrics),
            "wheel_build_sites": sum(item.wheel_build_sites for item in metrics),
        }
        report["layers"][layer] = observed
        for field in ("files", "test_functions"):
            maximum = expected[f"max_{field}"]
            if observed[field] > maximum:
                errors.append(f"{layer} {field} grew to {observed[field]} (budget {maximum})")
        if collect and collected is not None and collected > expected["max_collected_cases"]:
            errors.append(
                f"{layer} collected cases grew to {collected} "
                f"(budget {expected['max_collected_cases']})"
            )

    invariant_metrics = {
        item.path: item
        for item in all_metrics
        if item.path.startswith("tests/invariants/")
    }
    declared = {item["path"]: item for item in policy["invariants"]}
    missing = sorted(set(declared) - set(invariant_metrics))
    undeclared = sorted(set(invariant_metrics) - set(declared))
    if missing:
        errors.append(f"declared invariant files are missing: {', '.join(missing)}")
    if undeclared:
        errors.append(f"invariant files lack authority records: {', '.join(undeclared)}")

    for path, metrics in invariant_metrics.items():
        entry = declared.get(path)
        if not entry:
            continue
        if entry.get("authority") not in ALLOWED_AUTHORITIES:
            errors.append(f"{path}: invalid authority category {entry.get('authority')!r}")
        if not str(entry.get("rationale", "")).strip():
            errors.append(f"{path}: missing invariant rationale")
        if metrics.test_functions > int(entry["max_test_functions"]):
            errors.append(
                f"{path}: test functions grew to {metrics.test_functions} "
                f"(budget {entry['max_test_functions']})"
            )
        forbidden = sorted(
            module
            for module in metrics.imported_modules
            if module.startswith(FORBIDDEN_INVARIANT_IMPORT_PREFIXES)
        )
        if forbidden:
            errors.append(f"{path}: private CLI implementation imports are forbidden: {forbidden}")
        declared_private = tuple(sorted(entry.get("private_imports", [])))
        if metrics.private_imports != declared_private:
            errors.append(
                f"{path}: private-import authority drift; observed={list(metrics.private_imports)} "
                f"declared={list(declared_private)}"
            )
        if metrics.private_imports and not str(entry.get("private_import_rationale", "")).strip():
            errors.append(f"{path}: private imports require a narrow rationale")
        if metrics.uses_mocking and not str(entry.get("mock_rationale", "")).strip():
            errors.append(f"{path}: mocking requires an invariant-specific rationale")
        if not metrics.uses_mocking and entry.get("mock_rationale"):
            errors.append(f"{path}: stale mock rationale; the file no longer uses mocking")
        if Path(path).name.startswith("test_cli_") and Path(path).name.endswith("_boundary.py"):
            errors.append(f"{path}: private CLI boundary tests belong in installed acceptance journeys")

    static = {
        "subprocess_calls": sum(item.subprocess_calls for item in all_metrics),
        "wheel_build_sites": sum(item.wheel_build_sites for item in all_metrics),
    }
    report["static"] = static
    for field, observed in static.items():
        maximum = policy["static_budgets"][f"max_{field}"]
        if observed > maximum:
            errors.append(f"{field} grew to {observed} (budget {maximum})")

    if junit is not None:
        if not junit.is_file():
            errors.append(f"JUnit results do not exist: {junit}")
        else:
            tests, duration, collection_skips = _junit_metrics(junit)
            report["junit"] = {
                "path": str(junit),
                "tests": tests,
                "collection_skips": collection_skips,
                "duration_seconds": duration,
            }
            expected_total = policy["default_suite"]["max_collected_cases"]
            if tests > expected_total:
                errors.append(f"JUnit test count grew to {tests} (budget {expected_total})")
            runtime_budget = float(policy["default_suite"]["max_runtime_seconds"])
            if duration > runtime_budget:
                errors.append(
                    f"default suite runtime grew to {duration:.3f}s (budget {runtime_budget:.3f}s)"
                )

    report["ok"] = not errors
    report["errors"] = errors
    return report, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--skip-collection", action="store_true")
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    policy = _load_policy(args.policy)
    report, errors = audit(
        policy,
        policy_path=args.policy,
        collect=not args.skip_collection,
        junit=args.junit,
    )
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for layer, metrics in report["layers"].items():
        collected = metrics["collected_cases"]
        collected_text = "not-collected" if collected is None else str(collected)
        print(
            f"{layer}: {metrics['files']} files, {metrics['test_functions']} functions, "
            f"{collected_text} collected cases"
        )
    print(
        "static: "
        f"{report['static']['subprocess_calls']} subprocess call sites, "
        f"{report['static']['wheel_build_sites']} wheel-build sites"
    )
    if report["junit"]:
        print(
            f"junit: {report['junit']['tests']} tests, "
            f"{report['junit']['duration_seconds']:.3f}s"
        )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("test authority audit: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
