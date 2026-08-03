#!/usr/bin/env python3
"""Create a deterministic SHA-256 manifest for regular evidence files."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(); p.add_argument("root",type=Path); p.add_argument("--output",type=Path); a=p.parse_args(); root=a.root.resolve(); rows=[]
    for path in sorted(root.rglob("*")):
        if path.is_symlink(): raise SystemExit(f"symlink rejected: {path}")
        if path.is_file() and (a.output is None or path.resolve()!=a.output.resolve()): rows.append({"path":path.relative_to(root).as_posix(),"size":path.stat().st_size,"sha256":sha(path)})
    value={"schema":"agent-workflow/evidence-manifest/v1","files":rows}; output=a.output or root/"EVIDENCE_MANIFEST.json"; output.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8"); print(output); return 0
if __name__=="__main__": raise SystemExit(main())
