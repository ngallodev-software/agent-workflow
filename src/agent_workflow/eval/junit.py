from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..errors import WorkflowError


def parse_junit(path: Path) -> dict[str, str]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise WorkflowError(f"invalid JUnit XML {path}: {exc}") from exc
    outcomes: dict[str, str] = {}
    for case in root.iter("testcase"):
        identifier = f"{case.get('classname', '')}::{case.get('name', '')}"
        if identifier in outcomes:
            raise WorkflowError(f"duplicate JUnit test ID in {path}: {identifier}")
        if case.find("failure") is not None:
            outcome = "fail"
        elif case.find("error") is not None:
            outcome = "error"
        elif case.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "pass"
        outcomes[identifier] = outcome
    if not outcomes:
        raise WorkflowError(f"JUnit XML has no test cases: {path}")
    return dict(sorted(outcomes.items()))


def compare_junit(
    baseline: dict[str, str], post: dict[str, str]
) -> dict[str, Any]:
    transitions: list[dict[str, str]] = []
    regressions: list[str] = []
    fixes: list[str] = []
    for identifier in sorted(set(baseline) | set(post)):
        before = baseline.get(identifier, "missing")
        after = post.get(identifier, "missing")
        transitions.append({"id": identifier, "before": before, "after": after})
        if before == "pass" and after in {"fail", "error", "missing"}:
            regressions.append(identifier)
        if before in {"fail", "error"} and after == "pass":
            fixes.append(identifier)
    return {"transitions": transitions, "regressions": regressions, "fixes": fixes}
