"""Deterministic worker-facing completion protocol.

Workers express intent through constrained commands. Agent-Workflow owns the
protocol JSON: identity, revisions, changed files, command receipts, enums, and
final schema validation are derived or constructed here rather than authored by
an LLM.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .agent_run_paths import AgentRunPaths
from .completion import substantive_completion_errors
from .config import Settings
from .contracts import read_agent_run_contract, validate_instance
from .errors import WorkflowError
from .git import snapshot
from .path import read_regular_file
from .process import EnvironmentPolicy, run
from .protocol_values import COMPLETION_RESULTS, CRITERION_RESULTS, REVIEW_DISPOSITIONS
from .run_lifecycle import authoritative_execution_status
from .state import run_dir
from .util import atomic_write_json, sha256_file, utc_now, validate_id

DRAFT_SCHEMA = "agent-workflow/worker-completion-draft/v1"
DRAFT_NAME = "completion-draft.json"
FINAL_NAME = "completion.json"
MAX_EVIDENCE_ITEMS = 64
MAX_TEXT_CHARS = 4096


def _context(settings: Settings, agent_run_id: str) -> tuple[Path, dict[str, Any], Path, Path]:
    validate_id(agent_run_id, "agent run ID")
    state_dir = run_dir(settings, agent_run_id)
    contract = read_agent_run_contract(AgentRunPaths(state_dir).contract)
    status = authoritative_execution_status(state_dir)
    if status not in {"running", "interruption_requested"}:
        raise WorkflowError(
            f"worker completion operations require a running Agent Run (status={status!r})"
        )
    workdir = Path(str(contract["worktree"]["path"])).resolve()
    handoff = Path(str(contract["paths"]["handoff_dir"])).resolve()
    current_handoff = (state_dir / "handoff").resolve()
    legacy_handoff = (workdir / ".agent-workflow-handoff" / agent_run_id).resolve()
    if handoff not in {current_handoff, legacy_handoff}:
        raise WorkflowError("launch handoff is outside the authorized runtime boundary")
    return state_dir, contract, workdir, handoff


def _clean_text(value: str, label: str) -> str:
    value = value.strip()
    if not value or len(value) > MAX_TEXT_CHARS:
        raise WorkflowError(f"{label} must be 1-{MAX_TEXT_CHARS} characters")
    return value


def _new_draft(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": DRAFT_SCHEMA,
        "agent_run_id": str(contract["agent_run"]["id"]),
        "state": "open",
        "criteria": [],
        "limitations": [],
        "commands": [],
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }


def _load_draft(handoff: Path, contract: dict[str, Any]) -> dict[str, Any]:
    path = handoff / DRAFT_NAME
    if not path.is_file():
        return _new_draft(contract)
    try:
        value = json.loads(read_regular_file(path, max_bytes=1024 * 1024).data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
        raise WorkflowError(f"cannot read worker completion draft: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != DRAFT_SCHEMA:
        raise WorkflowError("invalid worker completion draft")
    # Compatibility with drafts created by the first deterministic-protocol
    # overlay before non-gating limitation records were introduced.
    value.setdefault("limitations", [])
    validate_instance(value, DRAFT_SCHEMA, artifact=str(path))
    if value.get("agent_run_id") != contract["agent_run"]["id"]:
        raise WorkflowError("worker completion draft Agent Run identity mismatch")
    return value


def _save_draft(handoff: Path, draft: dict[str, Any]) -> dict[str, Any]:
    draft["updated_at"] = utc_now()
    validate_instance(draft, DRAFT_SCHEMA, artifact=str(handoff / DRAFT_NAME))
    atomic_write_json(handoff / DRAFT_NAME, draft)
    return draft


def _require_open(draft: dict[str, Any]) -> None:
    if draft.get("state") != "open":
        raise WorkflowError("worker completion is already finalized for this run")


def _evidence_items(
    workdir: Path,
    evidence: Iterable[str],
    evidence_files: Iterable[Path],
    *,
    label: str,
) -> list[str]:
    items = [_clean_text(item, label) for item in evidence]
    for source in evidence_files:
        selected = Path(source)
        if not selected.is_absolute():
            selected = workdir / selected
        selected = selected.resolve()
        try:
            relative = selected.relative_to(workdir).as_posix()
        except ValueError as exc:
            raise WorkflowError(
                "evidence files must stay inside the Agent Run worktree"
            ) from exc
        read = read_regular_file(selected, max_bytes=16 * 1024 * 1024)
        items.append(
            f"file:{relative}#sha256={read.sha256};bytes={len(read.data)}"
        )
    if not items or len(items) > MAX_EVIDENCE_ITEMS:
        raise WorkflowError(
            f"{label} must contain 1-{MAX_EVIDENCE_ITEMS} text/file items"
        )
    return items


def record_criterion(
    settings: Settings,
    agent_run_id: str,
    *,
    criterion_id: str,
    result: str,
    evidence: Iterable[str],
    evidence_files: Iterable[Path] = (),
) -> dict[str, Any]:
    """Record one criterion using only protocol-valid result values."""
    if result not in CRITERION_RESULTS:
        raise WorkflowError(f"criterion result must be one of: {', '.join(CRITERION_RESULTS)}")
    criterion_id = _clean_text(criterion_id, "criterion ID")
    _, contract, workdir, handoff = _context(settings, agent_run_id)
    evidence_items = _evidence_items(
        workdir,
        evidence,
        evidence_files,
        label="criterion evidence",
    )
    draft = _load_draft(handoff, contract)
    _require_open(draft)
    record = {"id": criterion_id, "result": result, "evidence": evidence_items}
    criteria = [item for item in draft.get("criteria", []) if item.get("id") != criterion_id]
    criteria.append(record)
    draft["criteria"] = criteria
    _save_draft(handoff, draft)
    return {"agent_run_id": agent_run_id, "criterion": record, "criterion_count": len(criteria)}


def record_limitation(
    settings: Settings,
    agent_run_id: str,
    *,
    limitation_id: str,
    evidence: Iterable[str],
    evidence_files: Iterable[Path] = (),
) -> dict[str, Any]:
    """Record a non-gating controlled-environment limitation.

    Limitations are always ``not_verified`` by construction. They preserve
    network/browser/sandbox constraints without converting them into source
    failures or allowing an LLM to choose a lifecycle-affecting enum.
    """
    limitation_id = _clean_text(limitation_id, "limitation ID")
    _, contract, workdir, handoff = _context(settings, agent_run_id)
    draft = _load_draft(handoff, contract)
    _require_open(draft)
    record = {
        "id": limitation_id,
        "result": "not_verified",
        "evidence": _evidence_items(
            workdir,
            evidence,
            evidence_files,
            label="limitation evidence",
        ),
    }
    limitations = [
        item for item in draft.get("limitations", [])
        if item.get("id") != limitation_id
    ]
    limitations.append(record)
    draft["limitations"] = limitations
    _save_draft(handoff, draft)
    return {
        "agent_run_id": agent_run_id,
        "limitation": record,
        "limitation_count": len(limitations),
    }


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def verify_command(
    settings: Settings,
    agent_run_id: str,
    *,
    argv: Iterable[str],
    cwd: Path | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Execute a verification command and record its observed result.

    The command result is observed by Agent-Workflow, never supplied by the
    worker. Re-running the same argv/cwd replaces its prior final receipt so a
    corrected successful verification can become the canonical completion
    receipt without erasing the fact that the worker had to retry from logs.
    """
    command = [str(item) for item in argv]
    if not command or any(not item for item in command):
        raise WorkflowError("verification command must contain non-empty argv values")
    _, contract, workdir, handoff = _context(settings, agent_run_id)
    draft = _load_draft(handoff, contract)
    _require_open(draft)
    selected_cwd = (cwd or workdir).resolve()
    try:
        selected_cwd.relative_to(workdir)
    except ValueError as exc:
        raise WorkflowError("verification cwd must stay inside the Agent Run worktree") from exc
    if not selected_cwd.is_dir():
        raise WorkflowError(f"verification cwd is not a directory: {selected_cwd}")
    result = run(
        command,
        cwd=selected_cwd,
        check=False,
        timeout_seconds=timeout_seconds,
        environment=EnvironmentPolicy(unsafe_inherit=True),
    )
    stdout = str(result.stdout)
    stderr = str(result.stderr)
    receipt = (
        f"exit={result.returncode}; stdout_sha256={_digest_text(stdout)}; "
        f"stderr_sha256={_digest_text(stderr)}"
    )
    record = {
        "argv": list(result.argv),
        "cwd": str(selected_cwd),
        "exit_code": int(result.returncode),
        "receipt": receipt,
    }
    key = (tuple(record["argv"]), record["cwd"])
    commands = [
        item
        for item in draft.get("commands", [])
        if (tuple(item.get("argv", [])), item.get("cwd")) != key
    ]
    commands.append(record)
    draft["commands"] = commands
    _save_draft(handoff, draft)
    return {
        "agent_run_id": agent_run_id,
        "command": record,
        "ok": result.returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
    }


def _changed_files(workdir: Path, base_revision: str | None, head_revision: str) -> list[str]:
    if not base_revision:
        return []
    changed = run(
        ["git", "-C", str(workdir), "diff", "--name-only", f"{base_revision}..{head_revision}"],
        check=False,
        environment=EnvironmentPolicy(unsafe_inherit=True, git_config_policy="operator"),
    )
    if changed.returncode != 0:
        raise WorkflowError("cannot derive changed files from the launch revision")
    return sorted({line.strip() for line in str(changed.stdout).splitlines() if line.strip()})


def _closeout_binding(handoff: Path) -> dict[str, str] | None:
    path = handoff / "repository-closeout.json"
    if not path.is_file():
        return None
    return {"path": "repository-closeout.json", "sha256": sha256_file(path)}


def complete(
    settings: Settings,
    agent_run_id: str,
    *,
    result: str,
    unresolved: Iterable[str] = (),
    review_disposition: str | None = None,
) -> dict[str, Any]:
    """Build, validate, and publish the canonical worker handoff.

    This is the worker's only terminal protocol operation. It does not seal or
    mutate host-owned execution lifecycle state; the runner collects the exact
    generated handoff and performs finalization/sealing after worker exit.
    """
    if result not in COMPLETION_RESULTS:
        raise WorkflowError(f"completion result must be one of: {', '.join(COMPLETION_RESULTS)}")
    if review_disposition is not None and review_disposition not in REVIEW_DISPOSITIONS:
        raise WorkflowError(
            f"review disposition must be one of: {', '.join(REVIEW_DISPOSITIONS)}"
        )
    unresolved_items = [_clean_text(item, "unresolved item") for item in unresolved]
    state_dir, contract, workdir, handoff = _context(settings, agent_run_id)
    draft = _load_draft(handoff, contract)
    _require_open(draft)
    snap = snapshot(workdir)
    base_revision = contract["worktree"].get("source_revision")
    ticket_identity = contract.get("ticket_identity")
    ticket_id = contract.get("ticket")
    if isinstance(ticket_identity, dict):
        ticket_id = ticket_identity.get("value")
    pack = contract.get("pack")
    pack_id = pack.get("id") if isinstance(pack, dict) else None
    value: dict[str, Any] = {
        "schema": "agent-workflow/completion/v1",
        "agent_run_id": agent_run_id,
        "ticket_id": ticket_id,
        "pack_id": pack_id,
        "result": result,
        "base_revision": base_revision,
        "head_revision": snap.head,
        "changed_files": _changed_files(workdir, base_revision, snap.head),
        "criteria": list(draft.get("criteria", [])),
        "limitations": list(draft.get("limitations", [])),
        "commands": list(draft.get("commands", [])),
        "unresolved": unresolved_items,
        "usage": None,
        "repository_closeout": _closeout_binding(handoff),
    }
    if review_disposition is not None:
        value["review_disposition"] = review_disposition
    validate_instance(value, "agent-workflow/completion/v1", artifact="generated completion")
    errors = substantive_completion_errors(
        value,
        agent_run_id=agent_run_id,
        ticket_id=ticket_id,
        pack_id=pack_id,
    )
    if errors:
        raise WorkflowError("generated completion is not terminally valid: " + "; ".join(errors))
    atomic_write_json(handoff / FINAL_NAME, value)
    draft["state"] = "finalized"
    draft["final_result"] = result
    draft["final_sha256"] = sha256_file(handoff / FINAL_NAME)
    _save_draft(handoff, draft)
    return {
        "agent_run_id": agent_run_id,
        "state": "finalized",
        "result": result,
        "review_disposition": review_disposition,
        "completion_path": str(handoff / FINAL_NAME),
        "completion_sha256": draft["final_sha256"],
        "criterion_count": len(value["criteria"]),
        "limitation_count": len(value["limitations"]),
        "command_count": len(value["commands"]),
        "changed_files": value["changed_files"],
        "next_action": "exit the worker normally; Agent-Workflow runner will collect and seal evidence",
    }


def status(settings: Settings, agent_run_id: str) -> dict[str, Any]:
    """Show the deterministic worker-completion protocol state."""
    _, contract, _, handoff = _context(settings, agent_run_id)
    draft = _load_draft(handoff, contract)
    final = handoff / FINAL_NAME
    return {
        "agent_run_id": agent_run_id,
        "state": draft.get("state"),
        "criteria": draft.get("criteria", []),
        "limitations": draft.get("limitations", []),
        "commands": draft.get("commands", []),
        "completion_path": str(final) if final.is_file() else None,
        "completion_sha256": sha256_file(final) if final.is_file() else None,
    }
