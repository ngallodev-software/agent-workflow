from __future__ import annotations
import os
from dataclasses import dataclass
from .process import require_command, run
@dataclass(frozen=True)
class PaneInfo:
    pid: int|None; dead: bool; command: str|None
def ensure_tmux(): require_command("tmux")
def session_exists(session_id: str) -> bool:
    ensure_tmux(); return run(["tmux","has-session","-t",session_id],check=False).returncode==0
def create_session(session_id: str, workdir: str, runner: str):
    ensure_tmux(); run(["tmux","new-session","-d","-s",session_id,"-c",workdir,runner])
def pane_info(session_id: str):
    if not session_exists(session_id): return None
    line=(run(["tmux","list-panes","-t",session_id,"-F","#{pane_pid}	#{pane_dead}	#{pane_current_command}"]).stdout.splitlines() or [""])[0]
    parts=line.split("	",2)
    if len(parts)!=3: return PaneInfo(None,False,None)
    try: pid=int(parts[0])
    except ValueError: pid=None
    return PaneInfo(pid,parts[1]=="1",parts[2] or None)
def capture(session_id: str, lines: int) -> str:
    return run(["tmux","capture-pane","-p","-t",session_id,"-S",f"-{lines}"]).stdout
def attach(session_id: str):
    ensure_tmux(); os.execvp("tmux",["tmux","attach-session","-t",session_id])
def interrupt(session_id: str): run(["tmux","send-keys","-t",session_id,"C-c"])
def kill(session_id: str): run(["tmux","kill-session","-t",session_id],check=False)
