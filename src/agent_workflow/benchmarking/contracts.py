from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import read_contract, validate_instance
from ..errors import WorkflowError
from .auth import validate_authentication_config
from .common import canonical_json_sha256, child, safe_relative
from .runtime import validate_runtime_lock

BENCHMARK_SPEC_SCHEMA = "agent-workflow/benchmark-spec/v1"
BENCHMARK_EXECUTOR_SCHEMA = "agent-workflow/benchmark-executor-config/v1"
BENCHMARK_RUN_SCHEMA = "agent-workflow/benchmark-run/v1"
BENCHMARK_ARM_SCHEMA = "agent-workflow/benchmark-arm/v1"
BENCHMARK_PAIR_SCHEMA = "agent-workflow/benchmark-pair/v1"
BENCHMARK_PHASE_EVENT_SCHEMA = "agent-workflow/benchmark-phase-event/v1"
BENCHMARK_MACHINE_SCORE_SCHEMA = "agent-workflow/benchmark-machine-score/v1"
BENCHMARK_REVIEW_ASSIGNMENT_SCHEMA = "agent-workflow/benchmark-review-assignment/v1"
BENCHMARK_HUMAN_REVIEW_SCHEMA = "agent-workflow/benchmark-human-review/v1"
BENCHMARK_CONSOLIDATION_SCHEMA = "agent-workflow/benchmark-consolidation-receipt/v1"
BENCHMARK_REPORT_SCHEMA = "agent-workflow/benchmark-report/v2"
BENCHMARK_VISUAL_EVIDENCE_SCHEMA = "agent-workflow/benchmark-visual-evidence/v1"
BENCHMARK_OPERATING_POLICY_SCHEMA = "agent-workflow/benchmark-operating-policy/v1"


def _unique(items: list[str], label: str) -> None:
    if len(items) != len(set(items)):
        raise WorkflowError(f"benchmark specification contains duplicate {label}")


def _require_file(root: Path, relative: str, label: str) -> Path:
    path = child(root, safe_relative(relative, label), label)
    if not path.is_file():
        raise WorkflowError(f"{label} not found: {path}")
    return path


def _require_directory(root: Path, relative: str, label: str) -> Path:
    path = child(root, safe_relative(relative, label), label)
    if not path.is_dir():
        raise WorkflowError(f"{label} not found: {path}")
    return path


def validate_spec(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    value = read_contract(path, BENCHMARK_SPEC_SCHEMA)
    root = path.parent
    _require_file(root, value["canonical_task"], "canonical task")
    _require_directory(root, value["fixture"]["template_path"], "fixture template")
    _require_file(root, value["visual"]["rubric_path"], "visual rubric")
    runtime_lock_path = _require_file(root, value["visual"]["runtime_lock_path"], "visual runtime lock")
    from .common import read_object
    validate_runtime_lock(read_object(runtime_lock_path), claim_level=str(value["claim_level"]))
    phase_ids = [str(item["id"]) for item in value["phases"]]
    _unique(phase_ids, "phase IDs")
    for phase in value["phases"]:
        _require_file(root, str(phase["prompt_path"]), f"phase {phase['id']} prompt")
    arms = value["arms"]
    if set(arms) != {"control_raw", "workflow_full"}:
        raise WorkflowError(
            "initial benchmark requires exactly control_raw and workflow_full arms"
        )
    for arm, profile in arms.items():
        _require_file(root, str(profile["wrapper_path"]), f"{arm} wrapper")
        if profile["profile_id"] not in {"control-raw/v1", "workflow-full/v1"}:
            raise WorkflowError(f"unsupported initial constraint profile: {profile['profile_id']}")
    scheduling = value["scheduling"]
    if int(scheduling["pair_concurrency"]) != 1:
        raise WorkflowError("initial benchmark supports one pair at a time; each pair still runs both arms concurrently")
    retries = int(scheduling["infrastructure_retries"])
    if retries < 0 or retries > 3:
        raise WorkflowError("benchmark infrastructure retries must be between 0 and 3")
    cases = value["cases"]
    _unique([str(item["id"]) for item in cases], "case IDs")
    for case in cases:
        _require_file(root, str(case["input_path"]), f"case {case['id']} input")
        scope = case["allowed_scope"]
        for key in ("writable_paths", "writable_trees", "disposable_trees"):
            for relative in scope.get(key, []):
                safe_relative(str(relative), f"case {case['id']} {key}")
    scorers = value["machine_scoring"]["scorers"]
    _unique([str(item["id"]) for item in scorers], "scorer IDs")
    total = sum(float(item["max_points"]) for item in scorers)
    if abs(total - 100.0) > 1e-9:
        raise WorkflowError(f"machine scorer points must total 100, observed {total:g}")
    if abs(float(value["composite"]["machine_weight"]) + float(value["composite"]["human_weight"]) - 1.0) > 1e-9:
        raise WorkflowError("benchmark composite weights must total 1.0")
    required_dimensions = {
        "hidden_functional",
        "public_regression",
        "robustness",
        "accessibility_ui",
        "scope_completeness",
        "engineering_quality",
    }
    if {str(item["dimension"]) for item in scorers} != required_dimensions:
        raise WorkflowError("benchmark machine scoring must define the six frozen dimensions")
    return value


def validate_executor_config(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    value = read_contract(path, BENCHMARK_EXECUTOR_SCHEMA)
    validate_authentication_config(value)
    template = value["argv_template"]
    placeholders = "\n".join(str(item) for item in template)
    delivery = value["prompt_delivery"]["source"]
    if delivery == "argv" and "{prompt_file}" not in placeholders:
        raise WorkflowError("argv prompt delivery requires {prompt_file}")
    billing = value["billing"]
    if billing["mode"] == "subscription" and billing["provider_billed_cost_semantics"] != "not-attributable":
        raise WorkflowError("subscription billing must use not-attributable provider cost semantics")
    if billing["mode"] == "metered-api" and value["authentication"]["mode"] == "subscription-session":
        raise WorkflowError("subscription authentication cannot be labeled as metered API billing")
    return value


def validate_value(value: dict[str, Any], schema: str, artifact: str) -> dict[str, Any]:
    validate_instance(value, schema, artifact=artifact)
    return value


def contract_sha256(value: dict[str, Any]) -> str:
    return canonical_json_sha256(value)
