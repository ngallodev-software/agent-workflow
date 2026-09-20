#!/usr/bin/env python3
"""Live qualification for Agent-Workflow's optional built-in TypeSafe provider."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_workflow.config import defaults, load_settings
from agent_workflow.routing import advise_routing_with_policy
from agent_workflow.semantic.typesafe import capability

CASES = (
    ({"task": "Implement the requested configuration change and update its tests.", "task_type": "implementation", "risk": "normal"}, "implementation"),
    ({"task": "Review the supplied patch for correctness and report findings only.", "task_type": "review", "risk": "normal"}, "review"),
    ({"task": "Diagnose why the worker stopped after startup without changing product behavior.", "task_type": "research", "risk": "normal"}, "exploratory"),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, default=Path("typesafe-live-receipt.json"))
    parser.add_argument("--model")
    args = parser.parse_args()
    if not os.environ.get("TYPESAFE_API_KEY"):
        parser.error("TYPESAFE_API_KEY must be set for live qualification")
    settings = load_settings(args.config) if args.config else defaults()
    settings = replace(settings, decision_mode="comparative", typesafe_model=args.model or settings.typesafe_model)
    started = time.perf_counter()
    rows = []
    ok = True
    for index, (metadata, expected_control) in enumerate(CASES, 1):
        advice = advise_routing_with_policy(metadata, settings, task_text=str(metadata["task"]), source_ref=f"live:{index}")
        receipts = advice["decision_receipts"]
        statuses = {key: value["semantic"]["status"] for key, value in receipts.items()}
        types = {key: value["semantic"]["semantic_type"] for key, value in receipts.items()}
        case_ok = statuses == {key: "success" for key in statuses} and types == {
            "routing.task_class": "choice", "routing.interaction_required": "noul", "routing.semantic_risk": "score"
        }
        case_ok = case_ok and advice["recommendation"]["agent_class"] == expected_control
        case_ok = case_ok and all(receipt["applied_result"] == receipt["control_result"] for receipt in receipts.values())
        case_ok = case_ok and all("evidence_result" in receipt and "policy_candidate_result" in receipt for receipt in receipts.values())
        case_ok = case_ok and all(receipt["evidence_result"] is not None for receipt in receipts.values())
        ok = ok and case_ok
        rows.append({
            "case": index, "ok": case_ok, "control_agent_class": advice["recommendation"]["agent_class"],
            "candidate_agent_class": advice.get("counterfactual_candidate", {}).get("recommendation", {}).get("agent_class"),
            "receipts": receipts,
        })
    result = {
        "schema": "agent-workflow/typesafe-live-qualification/v2", "ok": ok,
        "mode": "comparative", "capability": capability(settings), "cases": rows,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
