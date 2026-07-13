#!/usr/bin/env python3
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('path', type=Path)
p.add_argument('--session')
p.add_argument('--workdir')
p.add_argument('--prompt')
p.add_argument('--log')
p.add_argument('--status', required=True)
p.add_argument('--exit-code', type=int)
a = p.parse_args()
try:
    data = json.loads(a.path.read_text(encoding='utf-8')) if a.path.exists() else {}
except Exception:
    data = {}
for key in ('session','workdir','prompt','log'):
    value = getattr(a, key)
    if value is not None:
        data[key] = value
data['status'] = a.status
if a.status == 'launched':
    data['started_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
else:
    data['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
if a.exit_code is not None:
    data['exit_code'] = a.exit_code
a.path.parent.mkdir(parents=True, exist_ok=True)
a.path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
