#!/usr/bin/env python3
"""Compatibility status writer for legacy prompt-pack helper scripts."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--session")
    parser.add_argument("--workdir")
    parser.add_argument("--prompt")
    parser.add_argument("--log")
    parser.add_argument("--status", required=True)
    parser.add_argument("--exit-code", type=int)
    args = parser.parse_args()
    try:
        data = json.loads(args.path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    for key in ("session", "workdir", "prompt", "log"):
        value = getattr(args, key)
        if value is not None:
            data[key] = value
    now = datetime.now(timezone.utc).isoformat()
    data["status"] = args.status
    data["updated_at"] = now
    if args.status in {"launched", "running"}:
        data.setdefault("started_at", now)
    if args.status in {"completed", "failed", "interrupted", "killed"}:
        data["finished_at"] = now
    if args.exit_code is not None:
        data["exit_code"] = args.exit_code
    args.path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".status.", dir=args.path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, args.path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
