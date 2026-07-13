from __future__ import annotations
from typing import Any
from .config import Settings
from .errors import WorkflowError
from .util import atomic_write_json, read_json, validate_id
TERMINAL_STATUSES={"completed","failed","interrupted","killed","accepted","rejected"}
def runs_root(settings: Settings):
    root=settings.state_root/"runs"; root.mkdir(parents=True,exist_ok=True); return root
def run_dir(settings: Settings, session_id: str):
    validate_id(session_id,"session ID"); return runs_root(settings)/session_id
def status_path(settings: Settings, session_id: str): return run_dir(settings,session_id)/"status.json"
def read_status(settings: Settings, session_id: str): return read_json(status_path(settings,session_id))
def write_status(settings: Settings, session_id: str, data: dict[str,Any]): atomic_write_json(status_path(settings,session_id),data)
def update_status(settings: Settings, session_id: str, **changes: Any):
    path=status_path(settings,session_id)
    if not path.exists(): raise WorkflowError(f"unknown session: {session_id}")
    data=read_json(path); data.update(changes); atomic_write_json(path,data); return data
def list_statuses(settings: Settings):
    items=[]
    for path in sorted(runs_root(settings).glob("*/status.json")):
        try: items.append(read_json(path))
        except WorkflowError: pass
    return items
