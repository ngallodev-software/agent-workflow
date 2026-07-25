from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contracts import read_contract, validate_instance
from .errors import WorkflowError
from .scheduler import SchedulerService
from .util import atomic_write_json, expand_path
from .workflow_receipt import seal_workflow, verify_workflow_receipt
from .workflow import (
    WORKFLOW_NODE_RESULT_SCHEMA,
    ensure_workflow_events_file,
    normalize_snapshot,
    read_stored_workflow_snapshot,
    snapshot_sha256,
    write_workflow_projection,
    workflow_events_path,
    workflow_lock,
    workflow_run_path,
    workflow_snapshot_path,
    workflow_status_path,
)


def _result(action: str, workflow_id: str, result: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    data = {
        "schema": WORKFLOW_NODE_RESULT_SCHEMA,
        "workflow_id": workflow_id,
        "action": action,
        "result": dict(result),
        **extra,
    }
    validate_instance(data, WORKFLOW_NODE_RESULT_SCHEMA, artifact="workflow node result")
    return data


def _workflow_io_error(action: str, exc: OSError) -> WorkflowError:
    return WorkflowError(f"workflow {action} failed: {exc}")


def _matching_started_snapshot(run_dir: Path, supplied: Mapping[str, Any]) -> dict[str, Any]:
    stored_path = workflow_snapshot_path(run_dir)
    if not stored_path.exists() and not stored_path.is_symlink():
        raise WorkflowError("workflow has not been started")
    stored = read_stored_workflow_snapshot(stored_path)
    if snapshot_sha256(stored) != snapshot_sha256(supplied):
        raise WorkflowError("supplied workflow snapshot does not match the started snapshot")
    return stored


def _write_projection(run_dir: Path, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return write_workflow_projection(
        snapshot=snapshot,
        snapshot_path=workflow_snapshot_path(run_dir),
        events_path=workflow_events_path(run_dir),
        status_path=workflow_status_path(run_dir),
        run_path=workflow_run_path(run_dir),
    )


@dataclass(frozen=True)
class WorkflowService:
    scheduler: SchedulerService

    def validate(self, snapshot_path: Path) -> dict[str, Any]:
        snapshot_file = expand_path(snapshot_path)
        snapshot = normalize_snapshot(read_contract(snapshot_file))
        return _result(
            "validate",
            str(snapshot["workflow_id"]),
            {"snapshot_sha256": snapshot_sha256(snapshot), "node_count": len(snapshot["nodes"])},
            snapshot_path=str(snapshot_file),
        )
    def start(self, snapshot_path: Path) -> dict[str, Any]:
        snapshot_file = expand_path(snapshot_path)
        snapshot = normalize_snapshot(read_contract(snapshot_file))
        run_dir = self.scheduler.run_dir
        try:
            with workflow_lock(run_dir):
                stored_snapshot = workflow_snapshot_path(run_dir)
                if stored_snapshot.exists() or stored_snapshot.is_symlink():
                    raise WorkflowError(f"workflow already started: {snapshot['workflow_id']}")
                if workflow_run_path(run_dir).exists() or workflow_run_path(run_dir).is_symlink():
                    raise WorkflowError(
                        f"workflow run projection exists without canonical snapshot: {run_dir}"
                    )
                atomic_write_json(stored_snapshot, snapshot, mode=0o444)
                ensure_workflow_events_file(run_dir)
                _write_projection(run_dir, snapshot)
        except OSError as exc:
            raise _workflow_io_error("start", exc) from exc
        schedule = self.scheduler.launch_eligible(snapshot)
        try:
            with workflow_lock(run_dir):
                _write_projection(run_dir, snapshot)
        except OSError as exc:
            raise _workflow_io_error("start", exc) from exc
        return _result(
            "start",
            str(snapshot["workflow_id"]),
            {"run_count": len(schedule["plans"]), "plans": schedule["plans"], "results": schedule["results"]},
            snapshot_path=str(workflow_snapshot_path(run_dir)),
            events_path=str(workflow_events_path(run_dir)),
            status_path=str(workflow_status_path(run_dir)),
            run_path=str(workflow_run_path(run_dir)),
            started=True,
            resumed=False,
            scheduled=[str(item["node_id"]) for item in schedule["plans"]],
        )

    def status(self, snapshot_path: Path) -> dict[str, Any]:
        supplied = normalize_snapshot(read_contract(expand_path(snapshot_path)))
        snapshot = _matching_started_snapshot(self.scheduler.run_dir, supplied)
        try:
            with workflow_lock(self.scheduler.run_dir):
                ensure_workflow_events_file(self.scheduler.run_dir)
                run = _write_projection(self.scheduler.run_dir, snapshot)
        except OSError as exc:
            raise _workflow_io_error("status", exc) from exc
        return _result("status", str(snapshot["workflow_id"]), run["status"])

    def resume(self, snapshot_path: Path) -> dict[str, Any]:
        snapshot_file = expand_path(snapshot_path)
        supplied = normalize_snapshot(read_contract(snapshot_file))
        run_dir = self.scheduler.run_dir
        try:
            snapshot = _matching_started_snapshot(run_dir, supplied)
            ensure_workflow_events_file(run_dir)
        except OSError as exc:
            raise _workflow_io_error("resume", exc) from exc
        schedule = self.scheduler.launch_eligible(snapshot)
        try:
            with workflow_lock(run_dir):
                _write_projection(run_dir, snapshot)
        except OSError as exc:
            raise _workflow_io_error("resume", exc) from exc
        return _result(
            "resume",
            str(snapshot["workflow_id"]),
            {"run_count": len(schedule["plans"]), "plans": schedule["plans"], "results": schedule["results"]},
            snapshot_path=str(workflow_snapshot_path(run_dir)),
            events_path=str(workflow_events_path(run_dir)),
            status_path=str(workflow_status_path(run_dir)),
            run_path=str(workflow_run_path(run_dir)),
            started=False,
            resumed=True,
            scheduled=[str(item["node_id"]) for item in schedule["plans"]],
        )

    def seal(self, snapshot_path: Path) -> dict[str, Any]:
        supplied = normalize_snapshot(read_contract(expand_path(snapshot_path)))
        snapshot = _matching_started_snapshot(self.scheduler.run_dir, supplied)
        evidence = seal_workflow(settings=self.scheduler.settings, run_dir=self.scheduler.run_dir)
        return _result(
            "seal",
            str(snapshot["workflow_id"]),
            {
                "receipt_sha256": evidence["receipt_sha256"],
                "verified": evidence["verified"],
                "workflow_state": evidence["receipt"]["workflow_state"],
            },
            receipt_path=evidence["receipt_path"],
        )

    def verify(self, snapshot_path: Path) -> dict[str, Any]:
        supplied = normalize_snapshot(read_contract(expand_path(snapshot_path)))
        snapshot = _matching_started_snapshot(self.scheduler.run_dir, supplied)
        evidence = verify_workflow_receipt(
            settings=self.scheduler.settings, run_dir=self.scheduler.run_dir
        )
        return _result(
            "verify",
            str(snapshot["workflow_id"]),
            {
                "receipt_sha256": evidence["receipt_sha256"],
                "verified": evidence["verified"],
                "workflow_state": evidence["receipt"]["workflow_state"],
            },
            receipt_path=evidence["receipt_path"],
        )
