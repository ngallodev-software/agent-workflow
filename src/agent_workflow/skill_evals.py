"""Deterministic behavioral contract checks for the primary Agent-Workflow skill.

The primary skill is a product interface.  These checks keep its critical decisions
machine-auditable without introducing a second runtime schema or an LLM-as-judge
release dependency.  The scenario corpus names the user situation and the behavior
that the skill must teach; matching remains deliberately narrow and deterministic.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SkillBehaviorEval:
    eval_id: str
    scenario: str
    requirement: str
    patterns: tuple[str, ...]


def load_skill_behavior_evals(path: Path) -> tuple[SkillBehaviorEval, ...]:
    """Load and structurally validate a deterministic skill behavior corpus."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema") != "agent-workflow/skill-behavior-evals/v1":
        raise ValueError("unexpected skill behavior eval schema")
    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("skill behavior eval corpus must contain cases")

    result: list[SkillBehaviorEval] = []
    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"cases[{index}] must be an object")
        eval_id = case.get("id")
        scenario = case.get("scenario")
        requirement = case.get("requirement")
        patterns = case.get("skill_patterns")
        if not isinstance(eval_id, str) or not re.fullmatch(r"SKILL-EVAL-[A-Z0-9-]+", eval_id):
            raise ValueError(f"cases[{index}].id is invalid")
        if eval_id in seen:
            raise ValueError(f"duplicate skill behavior eval id: {eval_id}")
        seen.add(eval_id)
        if not isinstance(scenario, str) or not scenario.strip():
            raise ValueError(f"{eval_id}: scenario must be non-empty")
        if not isinstance(requirement, str) or not requirement.strip():
            raise ValueError(f"{eval_id}: requirement must be non-empty")
        if not isinstance(patterns, list) or not patterns or not all(
            isinstance(pattern, str) and pattern for pattern in patterns
        ):
            raise ValueError(f"{eval_id}: skill_patterns must be a non-empty string list")
        result.append(
            SkillBehaviorEval(
                eval_id=eval_id,
                scenario=scenario.strip(),
                requirement=requirement.strip(),
                patterns=tuple(patterns),
            )
        )
    return tuple(result)


def validate_primary_skill_behavior(
    skill_path: Path,
    corpus_path: Path,
) -> tuple[str, ...]:
    """Return unmet deterministic behavior contracts for the primary skill."""

    text = skill_path.read_text(encoding="utf-8")
    errors: list[str] = []
    try:
        cases = load_skill_behavior_evals(corpus_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return (f"{corpus_path}: invalid skill behavior eval corpus: {exc}",)

    for case in cases:
        missing: list[str] = []
        for pattern in case.patterns:
            try:
                matched = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is not None
            except re.error as exc:
                errors.append(f"{case.eval_id}: invalid corpus regex {pattern!r}: {exc}")
                matched = True
            if not matched:
                missing.append(pattern)
        if missing:
            errors.append(
                f"{case.eval_id}: primary skill does not satisfy {case.requirement!r}; "
                f"missing contract pattern(s): {missing}"
            )
    return tuple(errors)
