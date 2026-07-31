"""Substantive validation for executor completion evidence.

JSON Schema proves shape. These checks prove that a terminal completion is not
an empty or placeholder-shaped object that accidentally satisfies the schema.
"""

from __future__ import annotations

import re
from typing import Any

_PLACEHOLDER = re.compile(
    r"^(?:todo|tbd|n/?a|none|null|unknown|placeholder|fixme|pending|later|"
    r"not provided|not available|<[^>]+>|\.{3})$",
    re.IGNORECASE,
)


def _empty_or_placeholder(value: object) -> bool:
    return not isinstance(value, str) or not value.strip() or bool(
        _PLACEHOLDER.fullmatch(value.strip())
    )


def substantive_completion_errors(
    value: dict[str, Any],
    *,
    session_id: str,
    ticket_id: str | None,
    pack_id: str | None,
) -> list[str]:
    """Return deterministic semantic errors for one schema-valid completion."""
    errors: list[str] = []
    if value.get("session_id") != session_id:
        errors.append("completion session_id does not match launch contract")
    if value.get("ticket_id") != ticket_id:
        errors.append("completion ticket_id does not match launch contract")
    if value.get("pack_id") != pack_id:
        errors.append("completion pack_id does not match launch contract")

    result = value.get("result")
    if result == "completed":
        for field in ("base_revision", "head_revision"):
            if _empty_or_placeholder(value.get(field)):
                errors.append(f"completed result requires substantive {field}")
        if value.get("unresolved"):
            errors.append("completed result must not contain unresolved items")
    elif result in {"partial", "failed", "blocked"} and not value.get("unresolved"):
        errors.append(f"{result} result requires at least one unresolved item")

    changed_files = value.get("changed_files", [])
    for index, path in enumerate(changed_files):
        if _empty_or_placeholder(path):
            errors.append(f"changed_files[{index}] is empty or placeholder-only")

    criteria = value.get("criteria", [])
    if result == "completed" and not criteria:
        errors.append("completed result requires at least one acceptance criterion")
    for index, criterion in enumerate(criteria):
        criterion_id = criterion.get("id")
        criterion_result = criterion.get("result")
        evidence = criterion.get("evidence", [])
        if _empty_or_placeholder(criterion_id):
            errors.append(f"criteria[{index}].id is empty or placeholder-only")
        if result == "completed" and criterion_result != "pass":
            errors.append(
                f"completed result requires criteria[{index}] to be pass"
            )
        if not evidence:
            errors.append(f"criteria[{index}] requires substantive evidence")
        for evidence_index, item in enumerate(evidence):
            if _empty_or_placeholder(item):
                errors.append(
                    f"criteria[{index}].evidence[{evidence_index}] is empty or placeholder-only"
                )

    commands = value.get("commands", [])
    if result == "completed" and not commands:
        errors.append("completed result requires at least one command receipt")
    successful_commands = 0
    for index, command in enumerate(commands):
        argv = command.get("argv", [])
        cwd = command.get("cwd")
        receipt = command.get("receipt")
        exit_code = command.get("exit_code")
        if not isinstance(exit_code, int) or isinstance(exit_code, bool):
            errors.append(f"commands[{index}].exit_code is missing or invalid")
        if not argv or any(_empty_or_placeholder(item) for item in argv):
            errors.append(f"commands[{index}].argv is empty or placeholder-only")
        if _empty_or_placeholder(cwd):
            errors.append(f"commands[{index}].cwd is empty or placeholder-only")
        if _empty_or_placeholder(receipt):
            errors.append(f"commands[{index}].receipt is empty or placeholder-only")
        if exit_code == 0:
            successful_commands += 1
        elif result == "completed":
            errors.append(
                f"completed result cannot hide commands[{index}] exit_code {exit_code}"
            )
    if result == "completed" and commands and successful_commands == 0:
        errors.append("completed result requires at least one successful command receipt")

    for index, item in enumerate(value.get("unresolved", [])):
        if _empty_or_placeholder(item):
            errors.append(f"unresolved[{index}] is empty or placeholder-only")
    return errors
