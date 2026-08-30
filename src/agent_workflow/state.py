from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Settings, enforce_trust
from .contracts import read_agent_run_contract
from .errors import WorkflowError
from .path import require_directory
from .util import atomic_write_json, read_json, utc_now, validate_id

TERMINAL_STATUSES = {
    "completed",
    "failed",
    "interrupted",
    "terminated",
    "retired",
}

STATUS_SCHEMA = "agent-workflow/agent-run-status/v1"
PROJECTION_AUTHORITY = "cache"


def _stamp_projection(
    data: dict[str, Any],
    *,
    source: str,
    freshness: str = "snapshot",
) -> dict[str, Any]:
    stamped = dict(data)
    stamped["projection_generated_at"] = utc_now()
    stamped["projection_source"] = source
    stamped["projection_freshness"] = freshness
    stamped["projection_authority"] = PROJECTION_AUTHORITY
    return stamped


def _current(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("schema") != STATUS_SCHEMA:
        raise WorkflowError(
            f"unsupported Agent Run status schema: {data.get('schema')!r}; "
            f"expected {STATUS_SCHEMA!r}"
        )
    return data


def runs_root(settings: Settings) -> Path:
    enforce_trust(settings)
    creator = settings.state_root
    while not creator.exists() and creator.parent != creator:
        creator = creator.parent
    require_directory(creator, label="state root parent")
    settings.state_root.mkdir(parents=True, mode=0o700, exist_ok=True)
    require_directory(settings.state_root, label="state root")
    enforce_trust(settings)
    root = settings.state_root / "runs"
    root.mkdir(mode=0o700, exist_ok=True)
    require_directory(root, label="state runs root")
    return root


def run_dir(settings: Settings, agent_run_id: str) -> Path:
    validate_id(agent_run_id, "agent run ID")
    return runs_root(settings) / agent_run_id


def status_path(settings: Settings, agent_run_id: str) -> Path:
    return run_dir(settings, agent_run_id) / "status.json"


def read_status_path(path: Path) -> dict[str, Any]:
    return _current(read_json(path))


def read_status(settings: Settings, agent_run_id: str) -> dict[str, Any]:
    return read_status_path(status_path(settings, agent_run_id))


def write_projection_path(
    path: Path,
    data: dict[str, Any],
    *,
    projection_source: str = "initialization",
    projection_freshness: str = "snapshot",
) -> dict[str, Any]:
    """Write mutable Agent Run status as a rebuildable projection only."""
    current = _stamp_projection(
        _current(data), source=projection_source, freshness=projection_freshness
    )
    atomic_write_json(path, current)
    return current


def write_projection(
    settings: Settings,
    agent_run_id: str,
    data: dict[str, Any],
    *,
    projection_source: str = "initialization",
    projection_freshness: str = "snapshot",
) -> dict[str, Any]:
    return write_projection_path(
        status_path(settings, agent_run_id),
        data,
        projection_source=projection_source,
        projection_freshness=projection_freshness,
    )


def _update_projection_path_unchecked(
    path: Path,
    *,
    projection_source: str = "status-update",
    projection_freshness: str = "snapshot",
    **changes: Any,
) -> dict[str, Any]:
    if not path.exists():
        raise WorkflowError(f"unknown Agent Run projection: {path.parent.name}")
    data = read_status_path(path)
    data.update(changes)
    data["updated_at"] = str(changes.get("updated_at") or utc_now())
    data = _stamp_projection(
        data, source=projection_source, freshness=projection_freshness
    )
    atomic_write_json(path, data)
    return data


def update_projection_path(
    path: Path,
    *,
    projection_source: str = "status-update",
    projection_freshness: str = "snapshot",
    **changes: Any,
) -> dict[str, Any]:
    """Patch mutable projection fields; execution status is lifecycle-owned."""
    if "status" in changes:
        raise WorkflowError(
            "execution status must be changed through run_lifecycle.transition_execution"
        )
    return _update_projection_path_unchecked(
        path,
        projection_source=projection_source,
        projection_freshness=projection_freshness,
        **changes,
    )


def update_projection(
    settings: Settings,
    agent_run_id: str,
    *,
    projection_source: str = "status-update",
    projection_freshness: str = "snapshot",
    **changes: Any,
) -> dict[str, Any]:
    return update_projection_path(
        status_path(settings, agent_run_id),
        projection_source=projection_source,
        projection_freshness=projection_freshness,
        **changes,
    )


def list_statuses(settings: Settings) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(runs_root(settings).glob("*/status.json")):
        try:
            items.append(read_status(settings, path.parent.name))
        except WorkflowError as exc:
            items.append(
                {
                    "schema": STATUS_SCHEMA,
                    "agent_run_id": path.parent.name,
                    "status": "failed",
                    "failure_category": "corrupt_status",
                    "error": str(exc),
                    "status_path": str(path),
                }
            )
    return items


def repair_status(settings: Settings, agent_run_id: str) -> dict[str, Any]:
    """Rebuild the mutable status projection from immutable/run-event authority."""
    run = run_dir(settings, agent_run_id)
    contract_path = run / "agent-run-contract.json"
    if not contract_path.is_file():
        raise WorkflowError("Agent Run has no immutable contract and cannot be repaired")
    contract = read_agent_run_contract(contract_path)
    now = read_json(run / "run-provenance.json").get("started_at") or ""
    status: dict[str, Any] = {
        "schema": STATUS_SCHEMA,
        "agent_run_id": agent_run_id,
        "ticket_id": contract.get("ticket"),
        "pack_id": contract["pack"].get("id"),
        "status": "prepared",
        "disposition": None,
        "created_at": now,
        "updated_at": now,
        "workdir": contract["worktree"]["path"],
        "prompt_path": str(run / "prompt.md"),
        "prompt_source": contract["prompt"]["source"],
        "role": (contract.get("role") or {}).get("id"),
        "role_digest": (contract.get("role") or {}).get("digest"),
        "worker_mode": contract["worker_plan"]["mode"],
        "worker_id": None,
        "worker_pid": None,
        "worker_process_group_id": None,
        "worker_alive": None,
        "prompt_sha256": contract["prompt"]["sha256"],
        "prompt_pack_root": contract["pack"].get("root"),
        "result_contract": contract["paths"].get("result_contract"),
        "launch_prompt_path": str(run / "launch-prompt.md"),
        "launch_prompt_sha256": contract["prompt"]["launch_sha256"],
        "log_path": str(run / "output.log"),
        "command_path": str(run / "command.json"),
        "completion_path": str(run / "completion.md"),
        "completion_json_path": str(run / "completion.json"),
        "handoff_dir": contract["paths"]["handoff_dir"],
        "provenance_path": str(run / "run-provenance.json"),
        "events_path": str(run / "executor-events.jsonl"),
        "stderr_path": str(run / "executor-stderr.log"),
        "final_receipt_path": None,
        "source_baseline_path": str(run / "source-baseline.json"),
        "agent_run_contract_path": str(contract_path),
    }

    from .receipts import read_sealed_contract, verify_seal_details

    receipt_path = run / "final-receipt.json"
    if receipt_path.is_file():
        receipt, digest = verify_seal_details(run)
        final, _ = read_sealed_contract(run, receipt, "final-status.json", STATUS_SCHEMA)
        status.update(final)
        status["final_receipt_path"] = str(receipt_path)
        status["final_receipt_sha256"] = digest
        status["sealed_artifact_count"] = len(receipt.get("artifacts", []))

        # Review/acceptance happens after execution sealing, so rebuild that
        # orthogonal disposition from its immutable receipt authority rather
        # than from the pre-review final-status snapshot.
        from .approval import lifecycle_disposition

        disposition = lifecycle_disposition(run)
        if disposition is None:
            status["disposition"] = None
        else:
            action = str(disposition["action"])
            status["disposition"] = action
            status["disposition_at"] = disposition["receipt"].get("created_at")
            status["disposition_actor"] = disposition["receipt"].get("actor")
            if action == "force-accepted":
                status["force_accept_receipt_path"] = disposition["receipt_path"]
            else:
                status["lifecycle_receipt_path"] = disposition["receipt_path"]
            if action == "accepted":
                status["accepted_revision"] = disposition.get("revision")
    else:
        from .events import reconstruct_lifecycle

        events_path = run / "events.jsonl"
        if not events_path.is_file():
            raise WorkflowError(
                "Agent Run has no lifecycle journal and cannot be repaired"
            )
        lifecycle = reconstruct_lifecycle(events_path)
        execution = lifecycle.get("state", {}).get("execution")
        if not isinstance(execution, str) or not execution:
            raise WorkflowError(
                "Agent Run lifecycle journal has no execution authority"
            )
        status["status"] = execution
        status["disposition"] = lifecycle.get("state", {}).get("review")
    return write_projection(
        settings,
        agent_run_id,
        status,
        projection_source="repair",
        projection_freshness="snapshot",
    )
