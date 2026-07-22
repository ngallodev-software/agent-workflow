from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .manifests import yaml
from .miniyaml import load_task_manifest


def _manifest(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    value = yaml.safe_load(text) if yaml is not None else load_task_manifest(text)
    return value if isinstance(value, dict) else {}


def _next_action(row: dict[str, Any]) -> str:
    session = row["session"]
    state = row["status"]
    if row.get("error"):
        return f"agent-workflow status {session} --json"
    if state == "missing":
        return f"agent-workflow launch {session} ..."
    if state in {"prepared", "launched", "running", "interruption_requested"}:
        return f"agent-workflow status {session}"
    if state in {"failed", "interrupted", "killed"}:
        return f"agent-workflow restart {session}"
    if not row.get("score_verdict"):
        return f"agent-workflow eval score {session}"
    if row.get("disposition") != "accepted":
        return f"agent-workflow review {session} --actor ID --reason TEXT"
    return "next dependency-unblocked ticket"


def build_ledger(pack_root: Path, runs_root: Path) -> dict[str, Any]:
    pack_root = pack_root.resolve()
    runs_root = runs_root.resolve()
    rows: list[dict[str, Any]] = []
    for phase_path in sorted(pack_root.glob("phase-*/task-manifest.yaml")):
        manifest = _manifest(phase_path)
        for task in manifest.get("tasks", []):
            if not isinstance(task, dict):
                continue
            session = str(task.get("session", ""))
            status_path = runs_root / session / "status.json"
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
            score_set = runs_root / session / "scores" / "score-set.json"
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
                if attempt.get("ticket_id") == task.get("id") or candidate.parent.name == session:
                    attempts.append(
                        {
                            "session": candidate.parent.name,
                            "status": attempt.get("status"),
                            "retry_of": attempt.get("retry_of"),
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
            row = {
                "phase": phase_path.parent.name,
                "ticket": str(task.get("id", "")),
                "dependencies": list(task.get("dependencies", [])),
                "session": session,
                "status": status.get("status", "missing"),
                "disposition": status.get("disposition"),
                "retry_of": status.get("retry_of"),
                "executor": status.get("executor"),
                "score_verdict": score_verdict,
                "accepted_revision": status.get("accepted_revision"),
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
            if by_ticket.get(dependency, {}).get("disposition") != "accepted"
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
    headings = ("PHASE", "TICKET", "SESSION", "STATUS", "REVIEW", "SCORE", "NEXT")
    lines = ["\t".join(headings)]
    for row in value["rows"]:
        lines.append(
            "\t".join(
                str(row.get(key) or "-")
                for key in (
                    "phase",
                    "ticket",
                    "session",
                    "status",
                    "disposition",
                    "score_verdict",
                    "next_action",
                )
            )
        )
    return "\n".join(lines) + "\n"
