#!/usr/bin/env python3
"""Write the deterministic checksum manifest for release distribution files."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    files = sorted(
        path
        for path in args.output_dir.iterdir()
        if path.is_file() and path.suffix in {".whl", ".gz"}
    )
    if not files:
        raise SystemExit("no wheel or source/archive files found for checksum manifest")
    manifest = args.output_dir / "SHA256SUMS"
    manifest.write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in files),
        encoding="utf-8",
    )
    print(f"checksums: {len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
