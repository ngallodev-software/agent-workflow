from __future__ import annotations

import ast
from pathlib import Path

from agent_workflow.decisions import DECISIONS


def _production_decision_ids() -> set[str]:
    """Return literal decision IDs supplied by production execute_decision_set calls."""
    root = Path(__file__).resolve().parents[1] / "src" / "agent_workflow"
    found: set[str] = set()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if name != "execute_decision_set":
                continue
            keyword = next((item for item in node.keywords if item.arg == "decision_ids"), None)
            assert keyword is not None, f"{path}: execute_decision_set must declare decision_ids"
            assert isinstance(keyword.value, (ast.Tuple, ast.List)), (
                f"{path}: decision_ids must be a literal tuple/list so coverage is auditable"
            )
            for item in keyword.value.elts:
                assert isinstance(item, ast.Constant) and isinstance(item.value, str), (
                    f"{path}: decision_ids entries must be string literals"
                )
                found.add(item.value)
    return found


def test_registered_runtime_decisions_match_live_production_boundaries() -> None:
    """Registration and reachable host dispatch sites must evolve together."""
    assert set(DECISIONS) == _production_decision_ids() == {
        "routing.task_class",
        "routing.interaction_required",
        "routing.semantic_risk",
    }
