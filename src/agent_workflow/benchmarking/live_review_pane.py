"""Foreground view for one preserved benchmark live-review server."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--stderr", type=Path, required=True)
    args = parser.parse_args()
    print(f"[{args.arm}] live benchmark application: {args.url}", flush=True)
    print("The server is preserved for human assessment. Use benchmark cleanup --stop-live-apps when finished.", flush=True)
    offsets = {args.stdout: 0, args.stderr: 0}
    while _alive(args.pid):
        for path in offsets:
            try:
                with path.open("r", encoding="utf-8", errors="replace") as stream:
                    stream.seek(offsets[path])
                    text = stream.read()
                    offsets[path] = stream.tell()
                if text:
                    print(text, end="" if text.endswith("\n") else "\n", flush=True)
            except OSError:
                pass
        time.sleep(0.25)
    print(f"[{args.arm}] live benchmark server stopped (pid={args.pid}).", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
