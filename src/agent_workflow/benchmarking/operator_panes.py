"""Two-pane observable execution surface for comparative benchmarks."""

from __future__ import annotations

import os
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

from .. import tmux
from ..errors import WorkflowError
from ..process import run
from ..util import atomic_write_json, utc_now
from .live_review import operator_panes_path, runtime_dir


ARMS = ("control_raw", "workflow_full")
MAX_INTERACTIVE_PANES = 8


def _idle_command(arm: str) -> str:
    code = (
        "import time; "
        f"print('benchmark {arm} pane ready', flush=True); "
        "time.sleep(31536000)"
    )
    return shlex.join([sys.executable, "-c", code])


def _valid_panes(value: Mapping[str, Any], run_id: str) -> bool:
    panes = value.get("panes")
    if not isinstance(panes, Mapping) or value.get("run_id") != run_id:
        return False
    for arm in ARMS:
        pane_id = panes.get(arm)
        if not isinstance(pane_id, str):
            return False
        info = tmux.pane_info(pane_id)
        if info is None or info.dead or info.run_id != run_id or info.assignment_id != arm:
            return False
    return True


def _remove_owned_stale_panes(value: Mapping[str, Any], run_id: str) -> None:
    panes = value.get("panes")
    if not isinstance(panes, Mapping):
        return
    for arm in ARMS:
        pane_id = panes.get(arm)
        if not isinstance(pane_id, str):
            continue
        info = tmux.pane_info(pane_id)
        # Never kill a pane that has since been rebound to another run.
        if info is not None and info.run_id == run_id:
            run(["tmux", "kill-pane", "-t", pane_id], check=False)


def _preserve_pane(pane_id: str) -> None:
    """Keep the review pane visible after its foreground command exits."""
    run(["tmux", "set-option", "-p", "-t", pane_id, "remain-on-exit", "on"], check=False)



def operator_pane_preflight() -> dict[str, Any]:
    """Return a non-mutating readiness result for the paired pane surface."""
    if shutil.which("tmux") is None:
        return {
            "passed": False,
            "detail": "tmux executable is not available",
            "window": None,
            "occupied": None,
            "available": None,
            "required": len(ARMS),
            "maximum": MAX_INTERACTIVE_PANES,
        }
    if not os.environ.get("TMUX") or not os.environ.get("TMUX_PANE"):
        return {
            "passed": False,
            "detail": "benchmark run must be launched from inside tmux; two new observable arm panes are required",
            "window": None,
            "occupied": None,
            "available": None,
            "required": len(ARMS),
            "maximum": MAX_INTERACTIVE_PANES,
        }
    target = tmux.current_window_target()
    if not target:
        return {
            "passed": False,
            "detail": "unable to resolve the launching tmux window",
            "window": None,
            "occupied": None,
            "available": None,
            "required": len(ARMS),
            "maximum": MAX_INTERACTIVE_PANES,
        }
    current = tmux.interactive_pane_count(target)
    available = max(0, MAX_INTERACTIVE_PANES - current)
    passed = available >= len(ARMS)
    return {
        "passed": passed,
        "detail": (
            f"window={target}; occupied={current}/{MAX_INTERACTIVE_PANES}; "
            f"available={available}; required={len(ARMS)}"
        ),
        "window": target,
        "occupied": current,
        "available": available,
        "required": len(ARMS),
        "maximum": MAX_INTERACTIVE_PANES,
    }


def ensure_operator_panes(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Create exactly two new panes in the invoking tmux window.

    The invoking command remains in its pane.  Both benchmark arms reuse their
    stable pane IDs across phases, retries, and the final live-review display.
    """
    path = operator_panes_path(plan)
    run_id = str(plan["run_id"])
    if path.is_file():
        import json

        existing = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(existing, dict) and _valid_panes(existing, run_id):
            return existing
        if isinstance(existing, dict):
            _remove_owned_stale_panes(existing, run_id)
    preflight = operator_pane_preflight()
    if not preflight["passed"]:
        if preflight["window"] is None:
            raise WorkflowError(str(preflight["detail"]))
        raise WorkflowError(
            f"benchmark requires two additional panes but the launching window has "
            f"only {preflight['available']} available "
            f"({preflight['occupied']}/{preflight['maximum']} occupied)"
        )
    target = str(preflight["window"])
    root = runtime_dir(plan)
    root.mkdir(parents=True, exist_ok=True)
    panes: dict[str, str] = {}
    try:
        for arm in ARMS:
            pane_id = tmux.split_window(
                target,
                str(plan["coordinator"]["worktree"]),
                _idle_command(arm),
                pane_name=f"benchmark {arm}",
                # Benchmark owns exactly two additional panes; normal agent-pane
                # capacity remains enforced by the shared tmux layout helper.
                max_interactive_agent_panes=MAX_INTERACTIVE_PANES,
                max_interactive_agent_width=2,
                max_interactive_agent_vertical=4,
            )
            tmux.set_pane_binding(pane_id, run_id=str(plan["run_id"]), assignment_id=arm)
            _preserve_pane(pane_id)
            run(["tmux", "set-option", "-p", "-t", pane_id, "@agent-workflow-role", "benchmark-arm"], check=False)
            panes[arm] = pane_id
    except Exception:
        for pane_id in panes.values():
            run(["tmux", "kill-pane", "-t", pane_id], check=False)
        raise
    value = {
        "schema": "agent-workflow/benchmark-operator-panes/v1",
        "run_id": plan["run_id"],
        "window": target,
        "launching_pane": os.environ.get("TMUX_PANE"),
        "panes": panes,
        "created_at": utc_now(),
    }
    atomic_write_json(path, value)
    # Rebalance only the launching window and keep focus on the caller.
    run(["tmux", "select-layout", "-t", target, "tiled"], check=False)
    if os.environ.get("TMUX_PANE"):
        run(["tmux", "select-pane", "-t", os.environ["TMUX_PANE"]], check=False)
    return value



def close_operator_panes(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Close benchmark-owned panes without touching panes rebound to another run."""
    path = operator_panes_path(plan)
    run_id = str(plan["run_id"])
    if not path.is_file():
        return {"run_id": run_id, "closed": 0, "already_closed": 0, "preserved": 0}
    import json

    raw = json.loads(path.read_text(encoding="utf-8"))
    panes = raw.get("panes") if isinstance(raw, Mapping) else None
    closed = 0
    already_closed = 0
    preserved = 0
    if isinstance(panes, Mapping):
        for arm in ARMS:
            pane_id = panes.get(arm)
            if not isinstance(pane_id, str):
                continue
            info = tmux.pane_info(pane_id)
            if info is None:
                already_closed += 1
                continue
            if info.run_id != run_id or info.assignment_id != arm:
                preserved += 1
                continue
            result = run(["tmux", "kill-pane", "-t", pane_id], check=False)
            if result.returncode == 0:
                closed += 1
            else:
                preserved += 1
    raw["closed_at"] = utc_now()
    raw["closed"] = closed
    raw["already_closed"] = already_closed
    raw["preserved"] = preserved
    atomic_write_json(path, raw)
    return {
        "run_id": run_id,
        "closed": closed,
        "already_closed": already_closed,
        "preserved": preserved,
    }

def respawn(
    panes: Mapping[str, Any],
    arm: str,
    *,
    worktree: Path,
    argv: list[str],
    title: str,
) -> str:
    pane_id = str(panes["panes"][arm])
    result = run(
        ["tmux", "respawn-pane", "-k", "-t", pane_id, "-c", str(worktree), shlex.join(argv)],
        check=False,
        timeout_seconds=30,
        max_stdout_bytes=4096,
        max_stderr_bytes=4096,
    )
    if result.returncode != 0:
        raise WorkflowError(f"failed to launch benchmark arm in pane {pane_id}: {result.stderr or result.stdout}")
    tmux.set_pane_binding(pane_id, run_id=str(panes["run_id"]), assignment_id=arm)
    _preserve_pane(pane_id)
    run(["tmux", "set-option", "-p", "-t", pane_id, "@agent-workflow-role", "benchmark-arm"], check=False)
    tmux.set_pane_name(pane_id, title)
    return pane_id


def pane_runtime(value: Mapping[str, Any], arm: str) -> dict[str, Any]:
    return {
        "tmux_window": value.get("window"),
        "tmux_pane_id": value.get("panes", {}).get(arm) if isinstance(value.get("panes"), Mapping) else None,
    }
