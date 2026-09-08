"""Foregroundable durable supervisor and bounded remediation controller."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .config import Settings
from .contracts import read_agent_run_contract
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
    remediation_count,
)
from .process import secret_values_from_argv
from .agent_runs import interrupt, observe, restart, steer
from .run_lifecycle import authoritative_execution_status
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
        probe_stalled: bool | None = None,
        interrupt_stalled: bool | None = None,
        restart_orphaned: bool | None = None,
        max_remediation_attempts: int | None = None,
        sync_index_enabled: bool | None = None,
    ) -> "SupervisorOptions":
        return cls(
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
        contract = read_agent_run_contract(run / "agent-run-contract.json")
    except WorkflowError:
        return ()
    argv = contract.get("worker_plan", {}).get("argv", [])
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        return ()
    return secret_values_from_argv(argv)


def _inspect_noninteractive_permission(run: Path, agent_run_id: str) -> None:
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
            agent_run_id=agent_run_id,
            state=signal,
            source=source_name,
            evidence_sha256=digest,
        )
        return


def _safe_repair_projections(settings: Settings) -> list[dict[str, Any]]:
    repaired: list[dict[str, Any]] = []
    root = runs_root(settings)
    for candidate in sorted(path for path in root.iterdir() if path.is_dir()):
        agent_run_id = candidate.name
        status_path = candidate / "status.json"
        has_authority = (candidate / "agent-run-contract.json").is_file()
        corrupt = False
        if status_path.is_file():
            try:
                # Validate the full status contract, not only JSON syntax. A
                # projection with valid JSON but an invalid schema is still
                # rebuildable from immutable launch/lifecycle authority.
                read_status(settings, agent_run_id)
            except (OSError, json.JSONDecodeError, WorkflowError):
                corrupt = True
        if has_authority and (not status_path.is_file() or corrupt):
            try:
                repaired_status = repair_status(settings, agent_run_id)
            except WorkflowError as exc:
                record_remediation(
                    candidate,
                    agent_run_id=agent_run_id,
                    incident_id=None,
                    rule_id="SAFE-REPAIR-STATUS-v1",
                    action="repair_status_projection",
                    outcome="failed",
                    reason=str(exc),
                )
                continue
            event = record_remediation(
                candidate,
                agent_run_id=agent_run_id,
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
    agent_run_id: str,
    observation: dict[str, Any],
    incident: dict[str, Any] | None,
    category: str | None,
    options: SupervisorOptions,
) -> list[dict[str, Any]]:
    run = run_dir(settings, agent_run_id)
    incident_id = str(incident.get("incident_id")) if incident else None
    applied: list[dict[str, Any]] = []

    if category == "process_alive_no_progress":
        probe_rule = "SAFE-PROBE-STALL-v1"
        probes = remediation_count(run, probe_rule)
        if options.probe_stalled and probes < options.max_remediation_attempts:
            try:
                message = steer(
                    settings,
                    agent_run_id,
                    actor="agent-workflow-supervisor",
                    content=(
                        "Automated health probe: report the current step, any blocker or "
                        "permission request, and the next expected durable progress event."
                    ),
                )
            except WorkflowError as exc:
                outcome = record_remediation(
                    run,
                    agent_run_id=agent_run_id,
                    incident_id=incident_id,
                    rule_id=probe_rule,
                    action="request_progress_probe",
                    outcome="failed",
                    reason=str(exc),
                )
            else:
                try:
                    post_action = observe(settings, agent_run_id)
                except WorkflowError as exc:
                    outcome = record_remediation(
                        run,
                        agent_run_id=agent_run_id,
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
                        agent_run_id=agent_run_id,
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
                    result = interrupt(settings, agent_run_id)
                except WorkflowError as exc:
                    outcome = record_remediation(
                        run,
                        agent_run_id=agent_run_id,
                        incident_id=incident_id,
                        rule_id=interrupt_rule,
                        action="interrupt_stalled_executor",
                        outcome="failed",
                        reason=str(exc),
                    )
                else:
                    outcome = record_remediation(
                        run,
                        agent_run_id=agent_run_id,
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
                result = restart(settings, agent_run_id)
            except WorkflowError as exc:
                outcome = record_remediation(
                    run,
                    agent_run_id=agent_run_id,
                    incident_id=incident_id,
                    rule_id=rule,
                    action="restart_orphaned_executor",
                    outcome="failed",
                    reason=str(exc),
                )
            else:
                outcome = record_remediation(
                    run,
                    agent_run_id=agent_run_id,
                    incident_id=incident_id,
                    rule_id=rule,
                    action="restart_orphaned_executor",
                    outcome="applied",
                    reason="operator policy explicitly authorized a lineage-preserving retry",
                    details={"new_agent_run_id": result.get("agent_run_id")},
                )
            applied.append(outcome)
    return applied


def supervise_once(
    settings: Settings,
    *,
    agent_run_ids: Iterable[str] | None = None,
    options: SupervisorOptions | None = None,
) -> dict[str, Any]:
    options = options or SupervisorOptions.from_settings(settings)
    selected = set(agent_run_ids or ())
    repaired = _safe_repair_projections(settings)
    results: list[dict[str, Any]] = []

    for status in list_statuses(settings):
        agent_run_id = str(status.get("agent_run_id", ""))
        if not agent_run_id or (selected and agent_run_id not in selected):
            continue
        run = run_dir(settings, agent_run_id)
        try:
            if authoritative_execution_status(run) in TERMINAL_STATUSES:
                continue
        except WorkflowError:
            # Preserve fail-closed observation behavior below; corrupt lifecycle
            # authority must not be hidden by a stale mutable status projection.
            pass
        _inspect_noninteractive_permission(run, agent_run_id)
        runner_pid, executor_pid = _heartbeat_pids(run)
        try:
            record_health_sample(
                run,
                agent_run_id=agent_run_id,
                runner_pid=runner_pid,
                executor_pid=executor_pid,
            )
        except WorkflowError as exc:
            # Historical sealed journals can be deliberately read-only while a
            # stale projection still lists the run as active.  Do not let that
            # projection disable supervision of every other run.
            results.append(
                {
                    **status,
                    "observed_state": "health_journal_unwritable",
                    "failure_category": "evidence_corrupt",
                    "error": str(exc),
                }
            )
            continue
        try:
            observation = observe(settings, agent_run_id)
        except WorkflowError as exc:
            observation = {
                **status,
                "observed_state": "observation_failed",
                "failure_category": "evidence_corrupt",
                "error": str(exc),
                "latest_health": {},
            }
        category, severity, summary = diagnose_observation(observation)
        evidence = {
            "observed_state": observation.get("observed_state"),
            "failure_category": observation.get("failure_category"),
            "permission_state": observation.get("permission_state"),
            "seconds_since_semantic_progress": observation.get(
                "seconds_since_semantic_progress"
            ),
            "executor_alive": observation.get("latest_health", {})
            .get("executor", {})
            .get("alive"),
        }
        incident = (
            record_incident(
                run,
                agent_run_id=agent_run_id,
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
                    agent_run_id,
                    observation=observation,
                    actor="agent-workflow-supervisor",
                    reason="supervisor confirmed worker process loss",
                )
            except WorkflowError as exc:
                finalization_error = str(exc)
        remediations = (
            []
            if category == "process_missing"
            else _apply_remediation(
                settings, agent_run_id, observation, incident, category, options
            )
        )
        results.append(
            {
                "agent_run_id": agent_run_id,
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
            from .index_db import database_path

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
                "errors": [{"agent_run_id": None, "error": str(exc)}],
            }

    return {
        "schema": SUPERVISOR_REPORT_SCHEMA,
        "recorded_at": utc_now(),
        "options": {
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
    agent_run_ids: Iterable[str] | None = None,
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
                agent_run_ids=agent_run_ids,
                options=options,
            )
        )
        cycle += 1
        if max_cycles is not None and cycle >= max_cycles:
            break
        time.sleep(interval)
    return reports
