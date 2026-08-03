"""Foregroundable durable supervisor and bounded remediation controller."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import tmux
from .config import Settings
from .contracts import read_launch_contract
from .diagnostics import diagnose_observation
from .errors import WorkflowError
from .finalization import finalize_run
from .index_store import sync_index
from .health import (
    permission_signal,
    record_health_sample,
    record_incident,
    record_permission_event,
    record_remediation,
    record_terminal_capture,
    remediation_count,
)
from .process import secret_values_from_argv
from .sessions import interrupt, observe, restart, steer
from .state import (
    TERMINAL_STATUSES,
    list_statuses,
    read_status,
    repair_status,
    run_dir,
    runs_root,
)
from .util import utc_now

SUPERVISOR_REPORT_SCHEMA = "agent-workflow/supervisor-report/v1"


@dataclass(frozen=True)
class SupervisorOptions:
    capture_interactive: bool
    capture_lines: int
    probe_stalled: bool
    interrupt_stalled: bool
    restart_orphaned: bool
    max_remediation_attempts: int
    sync_index: bool

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        capture_interactive: bool | None = None,
        capture_lines: int | None = None,
        probe_stalled: bool | None = None,
        interrupt_stalled: bool | None = None,
        restart_orphaned: bool | None = None,
        max_remediation_attempts: int | None = None,
        sync_index_enabled: bool | None = None,
    ) -> "SupervisorOptions":
        return cls(
            capture_interactive=(
                settings.supervisor_capture_interactive
                if capture_interactive is None
                else capture_interactive
            ),
            capture_lines=capture_lines or settings.supervisor_capture_lines,
            probe_stalled=(
                settings.supervisor_probe_stalled
                if probe_stalled is None
                else probe_stalled
            ),
            interrupt_stalled=(
                settings.supervisor_interrupt_stalled
                if interrupt_stalled is None
                else interrupt_stalled
            ),
            restart_orphaned=(
                settings.supervisor_restart_orphaned
                if restart_orphaned is None
                else restart_orphaned
            ),
            max_remediation_attempts=(
                max_remediation_attempts
                or settings.supervisor_max_remediation_attempts
            ),
            sync_index=(
                settings.supervisor_sync_index
                if sync_index_enabled is None
                else sync_index_enabled
            ),
        )


def _json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _heartbeat_pids(run: Path) -> tuple[int | None, int | None]:
    heartbeat = _json_object(run / "heartbeat.json")
    runner = heartbeat.get("runner_pid")
    executor = heartbeat.get("executor_pid")
    if not isinstance(executor, int) and isinstance(heartbeat.get("pid"), int):
        executor = heartbeat["pid"]
    return (
        runner if isinstance(runner, int) else None,
        executor if isinstance(executor, int) else None,
    )


def _secret_values(run: Path) -> tuple[str, ...]:
    try:
        contract = read_launch_contract(run / "launch-contract.json")
    except WorkflowError:
        return ()
    argv = contract.get("command_plan", {}).get("argv", [])
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        return ()
    return secret_values_from_argv(argv)


def _capture_interactive(
    settings: Settings,
    session_id: str,
    status: dict[str, Any],
    options: SupervisorOptions,
) -> dict[str, Any] | None:
    if not options.capture_interactive or not bool(
        status.get("executor_interactive", status.get("interactive", False))
    ):
        return None
    pane = tmux.resolve_status_pane(status)
    if pane is None or pane.dead or not pane.pane_id:
        return None
    content = tmux.capture(pane.pane_id, options.capture_lines)
    return record_terminal_capture(
        run_dir(settings, session_id),
        session_id=session_id,
        pane_id=pane.pane_id,
        content=content,
        secret_values=_secret_values(run_dir(settings, session_id)),
    )


def _inspect_noninteractive_permission(run: Path, session_id: str) -> None:
    for source_name, path in (
        ("executor_stderr", run / "executor-stderr.log"),
        ("executor_output", run / "output.log"),
    ):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[-16384:]
        except OSError:
            continue
        signal = permission_signal(text)
        if signal is None:
            continue
        import hashlib

        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        record_permission_event(
            run,
            session_id=session_id,
            state=signal,
            source=source_name,
            evidence_sha256=digest,
        )
        return


def _safe_repair_projections(settings: Settings) -> list[dict[str, Any]]:
    repaired: list[dict[str, Any]] = []
    root = runs_root(settings)
    for candidate in sorted(path for path in root.iterdir() if path.is_dir()):
        session_id = candidate.name
        status_path = candidate / "status.json"
        has_authority = (candidate / "launch-contract.json").is_file()
        corrupt = False
        if status_path.is_file():
            try:
                # Validate the full status contract, not only JSON syntax. A
                # projection with valid JSON but an invalid schema is still
                # rebuildable from immutable launch/lifecycle authority.
                read_status(settings, session_id)
            except (OSError, json.JSONDecodeError, WorkflowError):
                corrupt = True
        if has_authority and (not status_path.is_file() or corrupt):
            try:
                repaired_status = repair_status(settings, session_id)
            except WorkflowError as exc:
                record_remediation(
                    candidate,
                    session_id=session_id,
                    incident_id=None,
                    rule_id="SAFE-REPAIR-STATUS-v1",
                    action="repair_status_projection",
                    outcome="failed",
                    reason=str(exc),
                )
                continue
            event = record_remediation(
                candidate,
                session_id=session_id,
                incident_id=None,
                rule_id="SAFE-REPAIR-STATUS-v1",
                action="repair_status_projection",
                outcome="applied",
                reason="rebuilt mutable status from immutable launch/lifecycle authority",
            )
            repaired.append({"status": repaired_status, "remediation": event})
    return repaired


def _apply_remediation(
    settings: Settings,
    session_id: str,
    observation: dict[str, Any],
    incident: dict[str, Any] | None,
    category: str | None,
    options: SupervisorOptions,
) -> list[dict[str, Any]]:
    run = run_dir(settings, session_id)
    incident_id = str(incident.get("incident_id")) if incident else None
    applied: list[dict[str, Any]] = []

    if category == "process_alive_no_progress":
        probe_rule = "SAFE-PROBE-STALL-v1"
        probes = remediation_count(run, probe_rule)
        if options.probe_stalled and probes < options.max_remediation_attempts:
            try:
                message = steer(
                    settings,
                    session_id,
                    actor="agent-workflow-supervisor",
                    content=(
                        "Automated health probe: report the current step, any blocker or "
                        "permission request, and the next expected durable progress event."
                    ),
                )
            except WorkflowError as exc:
                outcome = record_remediation(
                    run,
                    session_id=session_id,
                    incident_id=incident_id,
                    rule_id=probe_rule,
                    action="request_progress_probe",
                    outcome="failed",
                    reason=str(exc),
                )
            else:
                try:
                    post_action = observe(settings, session_id)
                except WorkflowError as exc:
                    outcome = record_remediation(
                        run,
                        session_id=session_id,
                        incident_id=incident_id,
                        rule_id=probe_rule,
                        action="request_progress_probe",
                        outcome="failed",
                        reason=f"probe delivery succeeded but post-action observation failed: {exc}",
                        details={
                            "message_id": message.get("message_id"),
                            "delivery_outcome": message.get("delivery_outcome"),
                            "verification": "failed",
                        },
                    )
                else:
                    outcome = record_remediation(
                        run,
                        session_id=session_id,
                        incident_id=incident_id,
                        rule_id=probe_rule,
                        action="request_progress_probe",
                        outcome="requested",
                        reason="semantic progress exceeded the configured stall threshold",
                        details={
                            "message_id": message.get("message_id"),
                            "delivery_outcome": message.get("delivery_outcome"),
                            "verification": "authoritative_post_action_observation",
                            "post_action_observation": {
                                "observed_state": post_action.get("observed_state"),
                                "status": post_action.get("status"),
                                "tmux_alive": post_action.get("tmux_alive"),
                                "failure_category": post_action.get("failure_category"),
                                "seconds_since_semantic_progress": post_action.get(
                                    "seconds_since_semantic_progress"
                                ),
                                "last_event": post_action.get("last_event"),
                            },
                        },
                    )
            applied.append(outcome)
        elif options.interrupt_stalled:
            interrupt_rule = "OPT-IN-INTERRUPT-STALL-v1"
            if remediation_count(run, interrupt_rule) < options.max_remediation_attempts:
                try:
                    result = interrupt(settings, session_id)
                except WorkflowError as exc:
                    outcome = record_remediation(
                        run,
                        session_id=session_id,
                        incident_id=incident_id,
                        rule_id=interrupt_rule,
                        action="interrupt_stalled_executor",
                        outcome="failed",
                        reason=str(exc),
                    )
                else:
                    outcome = record_remediation(
                        run,
                        session_id=session_id,
                        incident_id=incident_id,
                        rule_id=interrupt_rule,
                        action="interrupt_stalled_executor",
                        outcome="applied",
                        reason="operator policy explicitly authorized bounded interruption",
                        details={"status": result.get("status")},
                    )
                applied.append(outcome)

    if category == "process_missing" and options.restart_orphaned:
        rule = "OPT-IN-RESTART-ORPHAN-v1"
        if remediation_count(run, rule) < options.max_remediation_attempts:
            try:
                result = restart(settings, session_id)
            except WorkflowError as exc:
                outcome = record_remediation(
                    run,
                    session_id=session_id,
                    incident_id=incident_id,
                    rule_id=rule,
                    action="restart_orphaned_executor",
                    outcome="failed",
                    reason=str(exc),
                )
            else:
                outcome = record_remediation(
                    run,
                    session_id=session_id,
                    incident_id=incident_id,
                    rule_id=rule,
                    action="restart_orphaned_executor",
                    outcome="applied",
                    reason="operator policy explicitly authorized a lineage-preserving retry",
                    details={"new_session_id": result.get("session_id")},
                )
            applied.append(outcome)
    return applied


def supervise_once(
    settings: Settings,
    *,
    session_ids: Iterable[str] | None = None,
    options: SupervisorOptions | None = None,
) -> dict[str, Any]:
    options = options or SupervisorOptions.from_settings(settings)
    selected = set(session_ids or ())
    repaired = _safe_repair_projections(settings)
    results: list[dict[str, Any]] = []

    for status in list_statuses(settings):
        session_id = str(status.get("session_id", ""))
        if not session_id or (selected and session_id not in selected):
            continue
        if str(status.get("status")) in TERMINAL_STATUSES:
            continue
        run = run_dir(settings, session_id)
        capture_error: str | None = None
        try:
            _capture_interactive(settings, session_id, status, options)
        except WorkflowError as exc:
            capture_error = str(exc)
        _inspect_noninteractive_permission(run, session_id)
        runner_pid, executor_pid = _heartbeat_pids(run)
        pane_id = status.get("tmux_pane_id")
        record_health_sample(
            run,
            session_id=session_id,
            runner_pid=runner_pid,
            executor_pid=executor_pid,
            tmux_pane_id=str(pane_id) if pane_id else None,
        )
        try:
            observation = observe(settings, session_id)
        except WorkflowError as exc:
            observation = {
                **status,
                "observed_state": "observation_failed",
                "failure_category": "evidence_corrupt",
                "error": str(exc),
                "latest_health": {},
            }
        category, severity, summary = diagnose_observation(observation)
        if capture_error and category is None:
            category, severity, summary = (
                "terminal_capture_unavailable",
                "medium",
                "interactive terminal evidence could not be captured",
            )
        evidence = {
            "observed_state": observation.get("observed_state"),
            "failure_category": observation.get("failure_category"),
            "permission_state": observation.get("permission_state"),
            "seconds_since_semantic_progress": observation.get(
                "seconds_since_semantic_progress"
            ),
            "tmux_alive": observation.get("tmux_alive"),
            "executor_alive": observation.get("latest_health", {})
            .get("executor", {})
            .get("alive"),
            "capture_error": capture_error,
        }
        incident = (
            record_incident(
                run,
                session_id=session_id,
                category=category,
                severity=severity,
                summary=summary,
                evidence=evidence,
            )
            if category
            else None
        )
        finalization: dict[str, Any] | None = None
        finalization_error: str | None = None
        if category == "process_missing":
            try:
                finalization = finalize_run(
                    settings,
                    session_id,
                    observation=observation,
                    actor="agent-workflow-supervisor",
                    reason="supervisor confirmed terminal executor loss",
                )
            except WorkflowError as exc:
                finalization_error = str(exc)
        remediations = (
            []
            if category == "process_missing"
            else _apply_remediation(
                settings, session_id, observation, incident, category, options
            )
        )
        results.append(
            {
                "session_id": session_id,
                "observed_state": observation.get("observed_state"),
                "incident": incident,
                "finalization": finalization,
                "finalization_error": finalization_error,
                "remediations": remediations,
                "seconds_since_semantic_progress": observation.get(
                    "seconds_since_semantic_progress"
                ),
            }
        )

    index_report: dict[str, Any] | None = None
    if options.sync_index:
        try:
            index_report = sync_index(settings)
        except WorkflowError as exc:
            from .index_store import database_path

            index_report = {
                "schema": "agent-workflow/index-sync-report/v1",
                "database": str(database_path(settings)),
                "authority": "json-jsonl-sealed-receipts",
                "indexed": [],
                "indexed_count": 0,
                "skipped": [],
                "skipped_count": 0,
                "pruned": [],
                "error_count": 1,
                "errors": [{"session_id": None, "error": str(exc)}],
            }

    return {
        "schema": SUPERVISOR_REPORT_SCHEMA,
        "recorded_at": utc_now(),
        "options": {
            "capture_interactive": options.capture_interactive,
            "capture_lines": options.capture_lines,
            "probe_stalled": options.probe_stalled,
            "interrupt_stalled": options.interrupt_stalled,
            "restart_orphaned": options.restart_orphaned,
            "max_remediation_attempts": options.max_remediation_attempts,
            "sync_index": options.sync_index,
        },
        "repaired_projection_count": len(repaired),
        "repaired_projections": repaired,
        "run_count": len(results),
        "runs": results,
        "index_sync": index_report,
    }


def supervise_loop(
    settings: Settings,
    *,
    interval_seconds: int | None = None,
    max_cycles: int | None = None,
    session_ids: Iterable[str] | None = None,
    options: SupervisorOptions | None = None,
) -> list[dict[str, Any]]:
    interval = interval_seconds or settings.supervisor_interval_seconds
    if interval < 1:
        raise WorkflowError("supervisor interval must be at least one second")
    if max_cycles is not None and max_cycles < 1:
        raise WorkflowError("supervisor max_cycles must be positive or omitted")
    reports: list[dict[str, Any]] = []
    cycle = 0
    while max_cycles is None or cycle < max_cycles:
        reports.append(
            supervise_once(
                settings,
                session_ids=session_ids,
                options=options,
            )
        )
        cycle += 1
        if max_cycles is not None and cycle >= max_cycles:
            break
        time.sleep(interval)
    return reports
