#!/usr/bin/env python3
"""Reject stale build/lib Python components before a wheel build."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "agent_workflow"
BUILT = ROOT / "build" / "lib" / "agent_workflow"


def main() -> int:
    if not BUILT.exists():
        print("wheel source preflight: no existing build/lib tree")
        return 0
    source_files = {path.relative_to(SOURCE) for path in SOURCE.rglob("*.py")}
    built_files = {path.relative_to(BUILT) for path in BUILT.rglob("*.py")}
    mismatches = sorted(source_files ^ built_files)
    mismatches.extend(
        path for path in sorted(source_files & built_files)
        if (SOURCE / path).read_bytes() != (BUILT / path).read_bytes()
    )
    if mismatches:
        print("stale wheel build components:", file=sys.stderr)
        for path in mismatches:
            print(f"  agent_workflow/{path}", file=sys.stderr)
        print("rebuild from a clean build directory", file=sys.stderr)
        return 1
    print(f"wheel source preflight: {len(source_files)} components current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
