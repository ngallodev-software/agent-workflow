#!/usr/bin/env python3
"""Poll benchmark arm panes and retain timestamped captures proving visible changes."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

ARMS=("control_raw","workflow_full")

def read(path: Path): return json.loads(path.read_text(encoding="utf-8"))
def capture(pane: str) -> str:
    return subprocess.run(["tmux","capture-pane","-p","-t",pane,"-S","-300"], text=True, capture_output=True, check=True).stdout

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--plan",required=True,type=Path); p.add_argument("--output-dir",required=True,type=Path); p.add_argument("--interval",type=float,default=2.0); p.add_argument("--timeout",type=float,default=1200.0); a=p.parse_args()
    plan=read(a.plan.resolve()); coord=Path(plan["coordinator"]["worktree"]); run_dir=Path(plan["coordinator"]["run_dir"]); runtime=coord/".agent-workflow-benchmark-runtime"/str(plan["run_id"]); panes_file=runtime/"operator-panes.json"
    a.output_dir.mkdir(parents=True,exist_ok=True); started=time.monotonic(); panes=None; records={arm:[] for arm in ARMS}
    while time.monotonic()-started < a.timeout:
        if panes is None and panes_file.is_file(): panes=read(panes_file)
        if panes:
            for arm in ARMS:
                pane=str(panes["panes"][arm]); text=capture(pane); stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"); path=a.output_dir/f"{arm}-{stamp}.txt"; path.write_text(text,encoding="utf-8"); records[arm].append({"captured_at":stamp,"path":path.name,"sha256":hashlib.sha256(text.encode()).hexdigest(),"bytes":len(text.encode())})
        state=None
        state_path=run_dir/"run.json"
        if state_path.is_file(): state=read(state_path).get("state")
        if state in {"awaiting_human_review","completed","failed"} and panes:
            break
        time.sleep(max(0.25,a.interval))
    summary={"schema":"agent-workflow/benchmark-pane-monitor/v1","run_id":plan["run_id"],"operator_panes":panes,"records":records,"unique_hashes":{arm:len({r["sha256"] for r in rows}) for arm,rows in records.items()},"observed_changes":{arm:len({r["sha256"] for r in rows})>=2 for arm,rows in records.items()},"terminal_state":read(run_dir/"run.json").get("state") if (run_dir/"run.json").is_file() else None}
    (a.output_dir/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"run_id":plan["run_id"],"observed_changes":summary["observed_changes"],"terminal_state":summary["terminal_state"]},indent=2))
    return 0 if all(summary["observed_changes"].values()) else 2
if __name__=="__main__": raise SystemExit(main())
