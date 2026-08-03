#!/usr/bin/env python3
"""Capture a machine-readable snapshot of the invoking tmux window and sessions."""
from __future__ import annotations
import argparse, json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path


def tmux(*args: str) -> str:
    return subprocess.run(["tmux", *args], check=True, text=True, capture_output=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not os.environ.get("TMUX") or not os.environ.get("TMUX_PANE"):
        raise SystemExit("must run from inside tmux")
    fmt = "#{session_name}\t#{window_id}\t#{window_index}\t#{window_name}\t#{pane_id}\t#{pane_active}\t#{pane_dead}\t#{pane_pid}\t#{pane_title}\t#{pane_current_command}\t#{@agent-workflow-role}\t#{@agent-workflow-run-id}\t#{@agent-workflow-assignment-id}"
    lines = tmux("list-panes", "-a", "-F", fmt).splitlines()
    panes=[]
    for line in lines:
        values=(line.split("\t") + [""]*13)[:13]
        panes.append(dict(zip(["session","window_id","window_index","window_name","pane_id","active","dead","pid","title","command","role","run_id","assignment_id"], values)))
    sessions = tmux("list-sessions", "-F", "#{session_name}\t#{session_id}\t#{session_windows}\t#{session_attached}").splitlines()
    value={
      "schema":"agent-workflow/tmux-snapshot/v1",
      "captured_at":datetime.now(timezone.utc).isoformat(),
      "invoking_pane":os.environ["TMUX_PANE"],
      "panes":panes,
      "sessions":[dict(zip(["name","id","windows","attached"], (line.split("\t")+[""]*4)[:4])) for line in sessions],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
    print(args.output)
    return 0
if __name__ == "__main__": raise SystemExit(main())
