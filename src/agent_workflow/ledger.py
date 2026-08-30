from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .approval import is_approved
from .errors import WorkflowError
from .manifests import load_pack_manifest
from .repository_closeout import (
    repository_closeout_summary,
    validate_repository_closeout_payload,
)


def _next_action(row: dict[str, Any]) -> str:
    agent_run_id = row["agent_run_id"]
    state = row["status"]
    if row.get("error"):
        return f"agent-workflow agent-run status {agent_run_id} --json"
    if state == "missing":
        return f"agent-workflow agent-run prepare {agent_run_id} ..."
    if state in {"prepared", "running", "interruption_requested"}:
        return f"agent-workflow agent-run status {agent_run_id}"
    if state in {"failed", "interrupted", "terminated"}:
        return f"agent-workflow agent-run restart {agent_run_id}"
    if state == "retired":
        return f"agent-workflow agent-run status {agent_run_id}"
    if row.get("evaluation_required") and not row.get("score_verdict"):
        return f"agent-workflow eval score {agent_run_id}"
    if row.get("disposition") not in {"accepted", "force-accepted"}:
        return f"agent-workflow agent-run review {agent_run_id} --actor ID --reason TEXT"
    return "next dependency-unblocked ticket"


def _closeout_summary(run_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = run_dir / "repository-closeout.json"
    if not path.is_file():
        return None, None
    try:
        receipt = validate_repository_closeout_payload(
            path.read_bytes(), artifact=str(path)
        )
    except (OSError, WorkflowError) as exc:
        # Preserve the task row and make closeout corruption visible to operators.
        return None, f"invalid repository-closeout.json: {exc}"
    return repository_closeout_summary(receipt), None


def build_ledger(pack_root: Path, runs_root: Path) -> dict[str, Any]:
    pack_root = pack_root.resolve()
    runs_root = runs_root.resolve()
    manifest = load_pack_manifest(pack_root)
    rows: list[dict[str, Any]] = []
    for phase in manifest.get("phases", []):
        if not isinstance(phase, dict):
            continue
        phase_name = str(phase.get("directory") or phase.get("id") or "")
        for task in phase.get("tasks", []):
            if not isinstance(task, dict):
                continue
            agent_run_id = str(task.get("agent_run_id", ""))
            status_path = runs_root / agent_run_id / "status.json"
            status: dict[str, Any] = {}
            error = None
            if status_path.is_file():
                try:
                    candidate = json.loads(status_path.read_text(encoding="utf-8"))
                    if isinstance(candidate, dict):
                        status = candidate
                    else:
                        error = "status is not an object"
                except (OSError, json.JSONDecodeError) as exc:
                    error = f"invalid status.json: {exc}"
            score_set = runs_root / agent_run_id / "scores" / "score-set.json"
            score_verdict = None
            if score_set.is_file():
                try:
                    score_verdict = json.loads(
                        score_set.read_text(encoding="utf-8")
                    ).get("verdict")
                except (OSError, json.JSONDecodeError, AttributeError) as exc:
                    error = f"invalid score-set.json: {exc}"
            attempts: list[dict[str, Any]] = []
            for candidate in sorted(runs_root.glob("*/status.json")):
                try:
                    attempt = json.loads(candidate.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(attempt, dict):
                    continue
                if attempt.get("ticket_id") == task.get("id") or candidate.parent.name == agent_run_id:
                    attempt_score = None
                    attempt_score_path = candidate.parent / "scores" / "score-set.json"
                    if attempt_score_path.is_file():
                        try:
                            attempt_score = json.loads(attempt_score_path.read_text(encoding="utf-8")).get("verdict")
                        except (OSError, json.JSONDecodeError, AttributeError):
                            attempt_score = None
                    attempt_ledger = {}
                    attempt_ledger_path = candidate.parent / "ledger-row.json"
                    if attempt_ledger_path.is_file():
                        try:
                            value = json.loads(attempt_ledger_path.read_text(encoding="utf-8"))
                            attempt_ledger = value if isinstance(value, dict) else {}
                        except (OSError, json.JSONDecodeError):
                            attempt_ledger = {}
                    attempt_closeout, attempt_closeout_error = _closeout_summary(candidate.parent)
                    if attempt_closeout_error:
                        error = error or attempt_closeout_error
                    attempts.append(
                        {
                            "agent_run_id": candidate.parent.name,
                            "status": attempt.get("status"),
                            "retry_of_agent_run_id": attempt.get("retry_of_agent_run_id"),
                            "executor_result": attempt_ledger.get("executor_result") or attempt.get("executor_result"),
                            "completion_result": attempt_ledger.get("completion_result") or attempt.get("completion_result"),
                            "policy_result": attempt_ledger.get("policy_result") or attempt.get("policy_result"),
                            "acceptance_eligible": bool(attempt_ledger.get("acceptance_eligible", attempt.get("acceptance_eligible", False))),
                            "attempt_classification": attempt_ledger.get("attempt_classification") or attempt.get("attempt_classification"),
                            "score_verdict": attempt_score or attempt_ledger.get("evaluation_result"),
                            "evaluation_state": attempt_ledger.get("evaluation_state") or attempt.get("evaluation_state"),
                            "repository_closeout": attempt_closeout,
                        }
                    )
            elapsed = None
            if status.get("created_at") and status.get("finished_at"):
                try:
                    elapsed = (
                        datetime.fromisoformat(status["finished_at"])
                        - datetime.fromisoformat(status["created_at"])
                    ).total_seconds()
                except (TypeError, ValueError):
                    error = error or "invalid lifecycle timestamp"
            repository_closeout, closeout_error = _closeout_summary(runs_root / agent_run_id)
            if closeout_error:
                error = error or closeout_error
            row = {
                "phase": phase_name,
                "ticket": str(task.get("id", "")),
                "dependencies": list(task.get("dependencies", [])),
                "agent_run_id": agent_run_id,
                "status": status.get("status", "missing"),
                "disposition": status.get("disposition"),
                "retry_of_agent_run_id": status.get("retry_of_agent_run_id"),
                "executor": status.get("executor"),
                "executor_result": status.get("executor_result"),
                "completion_result": status.get("completion_result"),
                "policy_result": status.get("policy_result"),
                "acceptance_eligible": bool(status.get("acceptance_eligible", False)),
                "attempt_classification": status.get("attempt_classification"),
                "evaluation_required": bool(status.get("evaluation_path")),
                "evaluation_state": ("missing-score-set" if status.get("evaluation_path") and not score_verdict else "complete" if status.get("evaluation_path") else "not-planned"),
                "score_verdict": score_verdict,
                "accepted_revision": status.get("accepted_revision"),
                "repository_closeout": repository_closeout,
                "error": error,
                "attempts": attempts,
                "attempt_count": len(attempts),
                "elapsed_seconds": elapsed,
            }
            row["next_action"] = _next_action(row)
            rows.append(row)
    by_ticket = {row["ticket"]: row for row in rows}
    for row in rows:
        blocked = [
            dependency
            for dependency in row["dependencies"]
            if (
                (dependency_row := by_ticket.get(dependency)) is None
                or not is_approved(runs_root / dependency_row["agent_run_id"])
            )
        ]
        if blocked and row["status"] == "missing" and not row.get("error"):
            row["next_action"] = "wait for dependencies: " + ", ".join(blocked)
    return {
        "schema": "agent-workflow/ledger/v1",
        "pack_root": str(pack_root),
        "runs_root": str(runs_root),
        "rows": rows,
    }


def render_ledger(value: dict[str, Any]) -> str:
    headings = (
        "PHASE",
        "TICKET",
        "AGENT RUN",
        "STATUS",
        "REVIEW",
        "SCORE",
        "LOCAL",
        "REMOTE",
        "COMMIT",
        "PUSH",
        "MERGE",
        "NEXT",
    )
    lines = ["\t".join(headings)]
    for row in value["rows"]:
        closeout = row.get("repository_closeout") or {}
        claims = closeout.get("claims") or {}
        local = closeout.get("local_head")
        remote = closeout.get("remote_revision_after")
        lines.append(
            "\t".join(
                (
                    str(row.get("phase") or "-"),
                    str(row.get("ticket") or "-"),
                    str(row.get("agent_run_id") or "-"),
                    str(row.get("status") or "-"),
                    str(row.get("disposition") or "-"),
                    str(row.get("score_verdict") or "-"),
                    str(local[:12] if isinstance(local, str) else "-"),
                    str(remote[:12] if isinstance(remote, str) else "-"),
                    "yes" if claims.get("committed") is True else "no" if claims.get("committed") is False else "-",
                    "yes" if claims.get("pushed") is True else "no" if claims.get("pushed") is False else "-",
                    "yes" if claims.get("merged") is True else "no" if claims.get("merged") is False else "-",
                    str(row.get("next_action") or "-"),
                )
            )
        )
    return "\n".join(lines) + "\n"
