from __future__ import annotations
from typing import Any
from .config import Settings
from .config import enforce_trust
from .errors import WorkflowError
from .events import append_lifecycle_event
from .migrations import migrate_contract
from .util import atomic_write_json, read_json, validate_id
from .contracts import read_launch_contract
from .path import require_directory

TERMINAL_STATUSES = {
    "completed",
    "failed",
    "interrupted",
    "killed",
}

STATUS_SCHEMA = "agent-workflow/session-status/v2"


def _current(data: dict[str, Any]) -> dict[str, Any]:
    if "schema" not in data:
        data = {"schema": "agent-workflow/session-status/v1", **data}
    return migrate_contract(data, STATUS_SCHEMA)


def runs_root(settings: Settings):
    enforce_trust(settings)
    creator = settings.state_root
    while not creator.exists() and creator.parent != creator:
        creator = creator.parent
    # Validate the existing prefix before mkdir can follow a hostile parent.
    require_directory(creator, label="state root parent")
    settings.state_root.mkdir(parents=True, mode=0o700, exist_ok=True)
    require_directory(settings.state_root, label="state root")
    enforce_trust(settings)
    root = settings.state_root / "runs"
    root.mkdir(mode=0o700, exist_ok=True)
    require_directory(root, label="state runs root")
    return root


def run_dir(settings: Settings, session_id: str):
    validate_id(session_id, "session ID")
    return runs_root(settings) / session_id


def status_path(settings: Settings, session_id: str):
    return run_dir(settings, session_id) / "status.json"


def read_status(settings: Settings, session_id: str):
    data = _current(read_json(status_path(settings, session_id)))
    return _migrate_legacy_tmux_status(settings, session_id, data)


def _migrate_legacy_tmux_status(
    settings: Settings,
    session_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Upgrade an unambiguous shared-window target to stable pane identity."""
    if data.get("tmux_mode") != "shared_window":
        return data
    target = data.get("tmux_target")
    if (
        not isinstance(target, str)
        or not target
        or target.startswith("%")
        or data.get("tmux_pane_id")
    ):
        return data

    from . import tmux

    try:
        pane = tmux.resolve_status_pane(data)
    except WorkflowError:
        return data
    if pane is None or not pane.pane_id or not pane.pane_id.startswith("%"):
        return data

    window_target = data.get("tmux_window_target")
    if not isinstance(window_target, str) or not window_target:
        window_target = None
        if ":" in target and "." in target:
            candidate, pane_index = target.rsplit(".", 1)
            if candidate and pane_index.isdigit():
                window_target = candidate
    if window_target is None:
        return data

    migrated = dict(data)
    migrated["tmux_pane_id"] = pane.pane_id
    migrated["tmux_target"] = pane.pane_id
    migrated["tmux_window_target"] = window_target
    atomic_write_json(status_path(settings, session_id), migrated)
    return migrated


def write_status(settings: Settings, session_id: str, data: dict[str, Any]):
    current = _current(data)
    append_lifecycle_event(
        run_dir(settings, session_id),
        dimension="execution",
        prior=None,
        new=current.get("status"),
        actor="agent-workflow",
        reason="status initialized",
    )
    atomic_write_json(status_path(settings, session_id), current)


def update_status(settings: Settings, session_id: str, **changes: Any):
    path = status_path(settings, session_id)
    if not path.exists():
        raise WorkflowError(f"unknown session: {session_id}")
    data = read_status(settings, session_id)
    actor = str(changes.pop("_actor", "agent-workflow"))
    reason = str(changes.pop("_reason", "status updated"))
    receipt_refs = changes.pop("_receipt_refs", ())
    if "status" in changes and changes["status"] != data.get("status"):
        append_lifecycle_event(
            path.parent,
            dimension="execution",
            prior=data.get("status"),
            new=changes["status"],
            actor=actor,
            reason=reason,
            receipt_refs=receipt_refs,
        )
    if "disposition" in changes and changes["disposition"] != data.get("disposition"):
        append_lifecycle_event(
            path.parent,
            dimension="review",
            prior=data.get("disposition"),
            new=changes["disposition"],
            actor=actor,
            reason=reason,
            receipt_refs=receipt_refs,
        )
    data.update(changes)
    atomic_write_json(path, data)
    return data


def list_statuses(settings: Settings):
    items = []
    for path in sorted(runs_root(settings).glob("*/status.json")):
        try:
            items.append(read_status(settings, path.parent.name))
        except WorkflowError as exc:
            items.append(
                {
                    "schema": STATUS_SCHEMA,
                    "session_id": path.parent.name,
                    "status": "failed",
                    "failure_category": "corrupt_status",
                    "error": str(exc),
                    "status_path": str(path),
                }
            )
    return items


def repair_status(settings: Settings, session_id: str) -> dict[str, Any]:
    """Rebuild the mutable status projection from immutable run authority."""
    run = run_dir(settings, session_id)
    contract_path = run / "launch-contract.json"
    if not contract_path.is_file():
        raise WorkflowError(
            "pre-contract run has no launch authority; sealed evidence remains verifiable "
            "but an unsealed projection cannot be repaired without its original provenance"
        )
    contract = read_launch_contract(contract_path)
    now = read_json(run / "run-provenance.json").get("started_at") or ""
    status: dict[str, Any] = {
        "schema": STATUS_SCHEMA,
        "session_id": session_id,
        "ticket_id": contract.get("ticket"),
        "pack_id": contract["pack"].get("id"),
        "status": "prepared",
        "disposition": None,
        "created_at": now,
        "updated_at": now,
        "workdir": contract["worktree"]["path"],
        "prompt_path": str(run / "prompt.md"),
        "prompt_source": contract["prompt"]["source"],
        "executor": contract["command_plan"].get("executor"),
        "model": contract["command_plan"].get("model"),
        "interactive": contract["command_plan"]["interactive"],
        "executor_interactive": contract["command_plan"]["executor_interactive"],
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
        "launch_contract_path": str(contract_path),
        "tmux_session": session_id,
        "tmux_target": session_id,
        "tmux_pane_id": None,
        "tmux_window_target": None,
        "tmux_mode": "dedicated_session",
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
    else:
        from .events import reconstruct_lifecycle
        lifecycle = reconstruct_lifecycle(run / "events.jsonl") if (run / "events.jsonl").is_file() else {"state": {}}
        status["status"] = lifecycle.get("state", {}).get("execution", "prepared")
        status["disposition"] = lifecycle.get("state", {}).get("review")
    atomic_write_json(status_path(settings, session_id), status)
    return status
