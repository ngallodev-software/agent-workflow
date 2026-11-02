#!/usr/bin/env python3
"""Standalone, stdlib-only, offline evidence integrity manifest utility.

This tool does not execute commands or establish trusted provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path, PurePosixPath

SCHEMA = "agent-evidence/bundle/v1"
MAX_MANIFEST_BYTES = 16 * 1024 * 1024


class EvidenceError(Exception):
    pass


def _path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise EvidenceError("invalid artifact path")
    p = PurePosixPath(value)
    if p.is_absolute() or p.as_posix() != value or any(x in ("", ".", "..") for x in value.split("/")):
        raise EvidenceError(f"unsafe artifact path: {value!r}")
    return value


def _files(root: Path) -> list[str]:
    found: list[str] = []

    def walk(directory: Path, prefix: str = "") -> None:
        with os.scandir(directory) as entries:
            children = sorted(entries, key=lambda x: x.name)
        for entry in children:
            rel = _path(prefix + entry.name)
            if entry.is_symlink():
                raise EvidenceError(f"symlink forbidden: {rel}")
            if entry.is_dir(follow_symlinks=False):
                walk(Path(entry.path), rel + "/")
            elif entry.is_file(follow_symlinks=False):
                found.append(rel)
            else:
                raise EvidenceError(f"unsupported filesystem entry: {rel}")

    walk(root)
    return found


def _digest(root: Path, rel: str) -> dict[str, object]:
    parts = _path(rel).split("/")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(root, flags)
        try:
            for part in parts[:-1]:
                nxt = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = nxt
            file_fd = os.open(parts[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=fd)
        finally:
            os.close(fd)
        with os.fdopen(file_fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise EvidenceError(f"not a regular file: {rel}")
            h = hashlib.sha256()
            size = 0
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
                size += len(chunk)
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns) or size != after.st_size:
                raise EvidenceError(f"artifact changed during read: {rel}")
            return {"path": rel, "size": size, "sha256": h.hexdigest()}
    except OSError as exc:
        raise EvidenceError(f"cannot read {rel}: {exc}") from exc


def capture(root: Path) -> dict[str, object]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise EvidenceError("root must be a directory")
    names = _files(root)
    if not names:
        raise EvidenceError("empty evidence directory")
    return {"schema": SCHEMA, "artifacts": [_digest(root, name) for name in names]}


def _load(manifest: Path) -> dict[str, object]:
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > MAX_MANIFEST_BYTES:
        raise EvidenceError("manifest must be a regular file within size limit")
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError) as exc:
        raise EvidenceError(f"invalid manifest: {exc}") from exc
    if not isinstance(value, dict) or set(value) != {"schema", "artifacts"} or value["schema"] != SCHEMA:
        raise EvidenceError("unsupported manifest schema")
    entries = value["artifacts"]
    if not isinstance(entries, list) or not entries:
        raise EvidenceError("manifest must have artifacts")
    previous = ""
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"path", "size", "sha256"}:
            raise EvidenceError("invalid artifact entry")
        name = _path(item["path"])
        if name <= previous:
            raise EvidenceError("artifact paths must be unique and sorted")
        previous = name
        if type(item["size"]) is not int or item["size"] < 0:
            raise EvidenceError("invalid artifact size")
        digest = item["sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise EvidenceError("invalid SHA-256 digest")
    return value


def verify(root: Path, manifest: Path) -> int:
    expected = _load(manifest)
    actual = capture(root)
    if actual["artifacts"] != expected["artifacts"]:
        raise EvidenceError("evidence file set, size, or digest mismatch")
    return len(actual["artifacts"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("capture", "verify"):
        p = sub.add_parser(name)
        p.add_argument("root", type=Path)
        p.add_argument("manifest", type=Path)
    p = sub.add_parser("inspect")
    p.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == "inspect":
            value = _load(args.manifest)
            print(json.dumps({"schema": SCHEMA, "count": len(value["artifacts"])}, sort_keys=True))
        elif args.action == "capture":
            root = args.root.resolve(strict=True)
            destination = args.manifest.resolve()
            if destination == root or root in destination.parents:
                raise EvidenceError("manifest must be outside evidence root")
            value = capture(root)
            # Exclusive creation avoids silently replacing an existing manifest.
            with args.manifest.open("x", encoding="utf-8") as stream:
                json.dump(value, stream, sort_keys=True, separators=(",", ":"))
                stream.write("\n")
            print(json.dumps({"schema": SCHEMA, "count": len(value["artifacts"])}, sort_keys=True))
        else:
            print(json.dumps({"verified": verify(args.root, args.manifest)}, sort_keys=True))
    except (EvidenceError, OSError) as exc:
        print(f"evidence: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
