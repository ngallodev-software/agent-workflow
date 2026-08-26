from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_run_paths import AgentRunPaths
from .agent_runs import prepare as prepare_agent_run
from .agent_runs import public_agent_run_view, start as start_agent_run
from .config import Settings
from .contracts import read_agent_run_contract
from .errors import WorkflowError
from .path import absolute_path, require_directory
from .run_lifecycle import authoritative_execution_status
from .state import run_dir, synchronize_projection
from .util import validate_id
from .worktrees import create as create_worktree


def _stage_error(stage: str, exc: WorkflowError) -> WorkflowError:
    return WorkflowError(f"delegate stage {stage!r} failed: {exc}")


def _matching_existing_run(
    settings: Settings,
    *,
    agent_run_id: str,
    workdir: Path,
    prompt_path: Path,
    role: str | None,
    worker_mode: str,
) -> dict[str, Any] | None:
    """Return an idempotent existing run only when immutable launch inputs match."""
    state_dir = run_dir(settings, agent_run_id)
    if not state_dir.exists() or not any(state_dir.iterdir()):
        return None
    paths = AgentRunPaths(state_dir)
    try:
        contract = read_agent_run_contract(paths.contract)
    except WorkflowError as exc:
        raise _stage_error("existing-run-validation", exc) from exc

    mismatches: list[str] = []
    contract_workdir = Path(str(contract["worktree"]["path"]))
    if absolute_path(contract_workdir) != absolute_path(workdir):
        mismatches.append("workdir")
    contract_prompt = Path(str(contract["prompt"]["source"]))
    if absolute_path(contract_prompt) != absolute_path(prompt_path):
        mismatches.append("prompt")
    if role is not None and str(contract["role"]["id"]) != role:
        mismatches.append("role")
    if str(contract["worker_plan"]["mode"]) != worker_mode:
        mismatches.append("worker_mode")
    if mismatches:
        raise WorkflowError(
            "delegate stage 'existing-run-validation' failed: agent run ID already exists "
            f"with different immutable inputs: {', '.join(mismatches)}"
        )

    status = synchronize_projection(paths.status, source="delegate-idempotent")
    return public_agent_run_view(status)


def delegate(
    settings: Settings,
    *,
    agent_run_id: str,
    prompt_path: Path,
    repo: Path | None = None,
    workdir: Path | None = None,
    ticket_id: str | None = None,
    base_ref: str = "HEAD",
    destination: Path | None = None,
    branch: str | None = None,
    role: str | None = "implementation",
    executor: str | None = None,
    agent_name: str | None = None,
    agent_class: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    allow_no_go_model: bool = False,
    pack_id: str | None = None,
    job_path: Path | None = None,
    prerequisites: list[str] | None = None,
    evaluation_path: Path | None = None,
    tier: str | None = None,
    structured: bool = False,
    interactive: bool | None = None,
    allow_dirty: bool = False,
    worker_mode: str = "headless",
) -> dict[str, Any]:
    """Compose worktree creation and Agent Run launch without adding new authority."""
    validate_id(agent_run_id, "agent run ID")
    ticket_id = ticket_id or agent_run_id
    validate_id(ticket_id, "ticket ID")
    if (repo is None) == (workdir is None):
        raise WorkflowError("delegate requires exactly one of --repo or --workdir")

    prompt_path = absolute_path(prompt_path)
    worktree_result: dict[str, Any] | None = None

    # Retry the exact same delegation command safely. If the Agent Run already
    # has an immutable contract, its worktree is authoritative; do not attempt
    # to create a second worktree before validating the existing launch.
    existing_state_dir = run_dir(settings, agent_run_id)
    if workdir is None and existing_state_dir.exists() and any(existing_state_dir.iterdir()):
        try:
            existing_contract = read_agent_run_contract(AgentRunPaths(existing_state_dir).contract)
            selected_workdir = require_directory(
                absolute_path(Path(str(existing_contract["worktree"]["path"]))),
                label="existing delegated workdir",
            )
        except WorkflowError as exc:
            raise _stage_error("existing-run-validation", exc) from exc
    elif workdir is None:
        try:
            worktree_result = create_worktree(
                settings,
                repo=repo,  # type: ignore[arg-type]
                ticket_id=ticket_id,
                base_ref=base_ref,
                destination=destination,
                branch=branch,
                allow_dirty=allow_dirty,
            )
            selected_workdir = Path(str(worktree_result["destination"]))
        except WorkflowError as exc:
            raise _stage_error("worktree-create", exc) from exc
    else:
        try:
            selected_workdir = require_directory(absolute_path(workdir), label="workdir")
        except WorkflowError as exc:
            raise _stage_error("worktree-select", exc) from exc

    existing = _matching_existing_run(
        settings,
        agent_run_id=agent_run_id,
        workdir=selected_workdir,
        prompt_path=prompt_path,
        role=role,
        worker_mode=worker_mode,
    )
    if existing is not None:
        state = str(existing.get("status", "unknown"))
        if worker_mode == "headless" and authoritative_execution_status(run_dir(settings, agent_run_id)) == "prepared":
            try:
                existing = public_agent_run_view(start_agent_run(settings, agent_run_id))
                state = str(existing.get("status", "running"))
            except WorkflowError as exc:
                raise _stage_error("agent-run-start", exc) from exc
        return _delegation_result(
            agent_run_id=agent_run_id,
            worktree=selected_workdir,
            role=str(existing.get("role") or role or "implementation"),
            worker_mode=worker_mode,
            state=state,
            reused_existing_run=True,
            worktree_created=False,
        )

    try:
        prepared = prepare_agent_run(
            settings,
            agent_run_id=agent_run_id,
            workdir=selected_workdir,
            prompt_path=prompt_path,
            executor=executor,
            agent_name=agent_name,
            role=role,
            agent_class=agent_class,
            model=model,
            reasoning_effort=reasoning_effort,
            allow_no_go_model=allow_no_go_model,
            ticket_id=ticket_id,
            pack_id=pack_id,
            allow_dirty=allow_dirty,
            structured=structured,
            interactive=interactive,
            prerequisite_ids=prerequisites,
            evaluation_path=evaluation_path,
            tier=tier,
            job_path=job_path,
            worker_mode=worker_mode,
        )
    except WorkflowError as exc:
        raise _stage_error("agent-run-prepare", exc) from exc

    result = public_agent_run_view(prepared)
    if worker_mode == "headless":
        try:
            result = public_agent_run_view(start_agent_run(settings, agent_run_id))
        except WorkflowError as exc:
            raise _stage_error("agent-run-start", exc) from exc

    state = str(result.get("status", "prepared" if worker_mode == "external" else "running"))
    return _delegation_result(
        agent_run_id=agent_run_id,
        worktree=selected_workdir,
        role=str(result.get("role") or role or "implementation"),
        worker_mode=worker_mode,
        state=state,
        reused_existing_run=False,
        worktree_created=worktree_result is not None,
    )


def _delegation_result(
    *,
    agent_run_id: str,
    worktree: Path,
    role: str,
    worker_mode: str,
    state: str,
    reused_existing_run: bool,
    worktree_created: bool,
) -> dict[str, Any]:
    """Return the compact common-path delegation contract.

    Detailed Agent Run state and worktree provenance remain available through
    their authoritative status/context surfaces instead of being duplicated
    into every delegation response.
    """
    return {
        "agent_run_id": agent_run_id,
        "role": role,
        "worker_mode": worker_mode,
        "worktree": str(worktree),
        "state": state,
        "reused_existing_run": reused_existing_run,
        "worktree_created": worktree_created,
        "next_actions": _next_actions(agent_run_id, worker_mode, state),
    }


def _next_actions(agent_run_id: str, worker_mode: str, state: str) -> list[str]:
    actions = [f"agent-workflow agent-run status {agent_run_id}"]
    if worker_mode == "external" and state == "prepared":
        actions.insert(0, "launch the prepared external worker using the durable Agent Run launch contract")
    if state in {"running", "prepared"}:
        actions.append(f"agent-workflow agent-run watch {agent_run_id}")
    return actions
