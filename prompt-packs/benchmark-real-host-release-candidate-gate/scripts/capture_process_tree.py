#!/usr/bin/env python3
"""Capture process identity/ancestry for a tmux pane or verify captured PIDs are gone."""
from __future__ import annotations
import argparse, json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path

def process_rows():
    out=subprocess.run(["ps","-eo","pid=,ppid=,pgid=,sid=,lstart=,args="],check=True,text=True,capture_output=True).stdout
    rows=[]
    for line in out.splitlines():
        parts=line.strip().split(None,10)
        if len(parts)>=11:
            rows.append({"pid":int(parts[0]),"ppid":int(parts[1]),"pgid":int(parts[2]),"sid":int(parts[3]),"started":" ".join(parts[4:9]),"args":" ".join(parts[9:])})
    return rows

def descendants(rows, root):
    by_parent={}
    for row in rows: by_parent.setdefault(row["ppid"],[]).append(row)
    result=[]; stack=[root]
    while stack:
        parent=stack.pop()
        for child in by_parent.get(parent,[]): result.append(child); stack.append(child["pid"])
    return result

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    s=sub.add_parser("snapshot"); s.add_argument("--pane",required=True); s.add_argument("--output",required=True,type=Path)
    v=sub.add_parser("verify-gone"); v.add_argument("--snapshot",required=True,type=Path); v.add_argument("--output",required=True,type=Path)
    a=p.parse_args(); rows=process_rows()
    if a.cmd=="snapshot":
        pane_pid=int(subprocess.run(["tmux","display-message","-p","-t",a.pane,"#{pane_pid}"],check=True,text=True,capture_output=True).stdout.strip())
        selected=[r for r in rows if r["pid"]==pane_pid]+descendants(rows,pane_pid)
        value={"schema":"agent-workflow/process-tree-snapshot/v1","captured_at":datetime.now(timezone.utc).isoformat(),"pane":a.pane,"pane_pid":pane_pid,"processes":selected}
        a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8"); return 0
    snap=json.loads(a.snapshot.read_text(encoding="utf-8")); live={r["pid"] for r in rows}; old=[p["pid"] for p in snap["processes"]]; remaining=sorted(set(old)&live); value={"schema":"agent-workflow/process-tree-verification/v1","verified_at":datetime.now(timezone.utc).isoformat(),"captured_pids":old,"remaining_pids":remaining,"passed":not remaining}; a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8"); print(json.dumps(value,indent=2)); return 0 if not remaining else 1
if __name__=="__main__": raise SystemExit(main())
