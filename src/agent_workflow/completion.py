"""Substantive validation for executor completion evidence.

JSON Schema proves shape. These checks prove that a terminal completion is not
an empty or placeholder-shaped object that accidentally satisfies the schema.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .contracts import read_agent_run_contract, validate_instance
from .errors import WorkflowError
from .path import read_regular_file
from .process import run
from .repository_closeout import (
    repository_closeout_summary,
    validate_repository_closeout_payload,
)

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
    agent_run_id: str,
    ticket_id: str | None,
    pack_id: str | None,
) -> list[str]:
    """Return deterministic semantic errors for one schema-valid completion.

    ``result`` records execution/submission outcome.  Review agents may also
    publish ``review_disposition`` so a successfully executed review can
    request changes without being mislabeled as a failed or partial executor.
    """
    errors: list[str] = []
    if value.get("agent_run_id") != agent_run_id:
        errors.append("completion agent_run_id does not match launch contract")
    if value.get("ticket_id") != ticket_id:
        errors.append("completion ticket_id does not match launch contract")
    if value.get("pack_id") != pack_id:
        errors.append("completion pack_id does not match launch contract")

    result = value.get("result")
    disposition = value.get("review_disposition")
    is_review = disposition in {"approved", "changes_requested", "blocked"}

    if disposition == "approved" and result != "completed":
        errors.append("approved review disposition requires result completed")
    elif disposition == "changes_requested" and result not in {"completed", "partial"}:
        errors.append("changes_requested review disposition requires result completed or partial")
    elif disposition == "blocked" and result not in {"partial", "blocked"}:
        errors.append("blocked review disposition requires result partial or blocked")
    if is_review and result == "failed":
        errors.append("failed review execution must omit review_disposition")

    if result == "completed":
        for field in ("base_revision", "head_revision"):
            if _empty_or_placeholder(value.get(field)):
                errors.append(f"completed result requires substantive {field}")
        if value.get("unresolved") and disposition not in {"changes_requested"}:
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
        if result == "completed" and not is_review and criterion_result != "pass":
            errors.append(f"completed result requires criteria[{index}] to be pass")
        if disposition == "approved" and criterion_result != "pass":
            errors.append(f"approved review requires criteria[{index}] to be pass")
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
        elif result == "completed" and disposition not in {"changes_requested"}:
            errors.append(
                f"completed result cannot hide commands[{index}] exit_code {exit_code}"
            )
    if result == "completed" and commands and successful_commands == 0:
        errors.append("completed result requires at least one successful command receipt")

    unresolved = value.get("unresolved", [])
    for index, item in enumerate(unresolved):
        if _empty_or_placeholder(item):
            errors.append(f"unresolved[{index}] is empty or placeholder-only")

    if disposition == "approved" and unresolved:
        errors.append("approved review disposition requires an empty unresolved list")
    if disposition == "changes_requested":
        has_nonpass = any(item.get("result") != "pass" for item in criteria)
        if not unresolved and not has_nonpass:
            errors.append(
                "changes_requested review disposition requires unresolved findings or a non-pass criterion"
            )
    if disposition == "blocked" and not unresolved:
        errors.append("blocked review disposition requires at least one unresolved blocker")
    return errors


def completion_revision_errors(
    value: dict[str, Any],
    *,
    expected_base_revision: str | None,
    actual_head_revision: str | None,
) -> list[str]:
    """Bind completed evidence to the launch baseline and current source HEAD."""
    if value.get("result") != "completed":
        return []
    errors: list[str] = []
    if not expected_base_revision or value.get("base_revision") != expected_base_revision:
        errors.append("completed base_revision does not match the launch source revision")
    if not actual_head_revision or value.get("head_revision") != actual_head_revision:
        errors.append("completed head_revision does not match the worktree Git HEAD")
    return errors


def validate_completion_repository_closeout(
    value: dict[str, Any],
    *,
    handoff: Path,
    expected_worktree: Path,
) -> dict[str, Any] | None:
    """Validate an optional repository-closeout sidecar bound by completion."""
    reference = value.get("repository_closeout")
    if reference is None:
        return None
    if not isinstance(reference, dict):
        raise WorkflowError("completion repository_closeout reference must be an object")
    relative = reference.get("path")
    expected_sha256 = reference.get("sha256")
    if relative != "repository-closeout.json" or not isinstance(expected_sha256, str):
        raise WorkflowError("completion repository_closeout reference is invalid")
    source = handoff / relative
    read = read_regular_file(source, max_bytes=4 * 1024 * 1024)
    if read.sha256 != expected_sha256:
        raise WorkflowError("repository closeout sidecar digest does not match completion reference")
    receipt = validate_repository_closeout_payload(
        read.data,
        artifact=str(source),
    )
    recorded_root = Path(str(receipt["repository"]["root"])).resolve()
    if recorded_root != expected_worktree.resolve():
        raise WorkflowError("repository closeout root does not match launch worktree")
    if receipt["local"]["head"] != value.get("head_revision"):
        raise WorkflowError("repository closeout local HEAD does not match completion head_revision")
    summary = repository_closeout_summary(receipt)
    summary["source_path"] = str(source)
    summary["source_sha256"] = read.sha256
    return summary


def validate_completion_handoff(run_dir: Path) -> dict[str, Any]:
    """Validate the executor-writable completion handoff without collecting it.

    This command is intentionally read-only.  It uses the immutable launch
    contract for identity, worktree, and schema bindings, allowing an agent to
    detect field-level errors before it exits or emits ``task-complete``.
    """
    launch = read_agent_run_contract(run_dir / "agent-run-contract.json")
    agent_run_id = str(launch["agent_run"]["id"])
    handoff = Path(str(launch["paths"]["handoff_dir"]))
    source = handoff / "completion.json"
    read = read_regular_file(source, max_bytes=1024 * 1024)
    try:
        value = json.loads(read.data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"invalid completion handoff JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError("completion handoff must be a JSON object")
    validate_instance(value, "agent-workflow/completion/v1", artifact=str(source))
    ticket_identity = launch.get("ticket_identity")
    expected_ticket = launch.get("ticket")
    if isinstance(ticket_identity, dict):
        expected_ticket = ticket_identity.get("value")
    semantic = substantive_completion_errors(
        value,
        agent_run_id=agent_run_id,
        ticket_id=expected_ticket,
        pack_id=(
            launch.get("pack", {}).get("id")
            if isinstance(launch.get("pack"), dict)
            else None
        ),
    )
    workdir = Path(str(launch["worktree"]["path"]))
    head_result = run(
        ["git", "-C", str(workdir), "rev-parse", "--verify", "HEAD"],
        check=False,
        max_stdout_bytes=128,
        max_stderr_bytes=1024,
    )
    actual_head = head_result.stdout.strip() if head_result.returncode == 0 else None
    revisions = completion_revision_errors(
        value,
        expected_base_revision=launch["worktree"].get("source_revision"),
        actual_head_revision=actual_head,
    )
    repository_closeout = None
    repository_error = None
    try:
        repository_closeout = validate_completion_repository_closeout(
            value,
            handoff=handoff,
            expected_worktree=workdir,
        )
    except WorkflowError as exc:
        repository_error = str(exc)
    errors = [*semantic, *revisions]
    if repository_error:
        errors.append(repository_error)
    if errors:
        raise WorkflowError("invalid completion handoff: " + "; ".join(errors))
    return {
        "schema": "agent-workflow/completion-validation/v1",
        "agent_run_id": agent_run_id,
        "source_path": str(source),
        "source_sha256": read.sha256,
        "validation_status": "valid",
        "result": value.get("result"),
        "review_disposition": value.get("review_disposition"),
        "repository_closeout": repository_closeout,
        "command_count": len(value.get("commands", [])),
        "criterion_count": len(value.get("criteria", [])),
    }
