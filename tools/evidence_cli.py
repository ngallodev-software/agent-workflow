#!/usr/bin/env python3
"""Standalone, stdlib-only, offline evidence integrity manifest utility.

This tool captures file integrity and command observations, not trusted provenance.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import tempfile
import stat
import subprocess
import threading
import signal
import time
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
    artifacts = [_digest(root, name) for name in names]
    if _files(root) != names:
        raise EvidenceError("evidence file set changed during capture")
    return {"schema": SCHEMA, "artifacts": artifacts}


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




def run_receipt(argv: list[str], cwd: Path, *, timeout: float, max_bytes: int) -> dict[str, object]:
    """Execute one explicit command with bounded captured output; never use a shell."""
    if not argv or any(not isinstance(a, str) or not a or "\\x00" in a for a in argv):
        raise EvidenceError("command argv must be nonempty strings")
    if not 0 < timeout <= 3600 or not 0 <= max_bytes <= 1048576:
        raise EvidenceError("invalid command bounds")
    cwd = cwd.resolve(strict=True)
    if not cwd.is_dir():
        raise EvidenceError("cwd must be a directory")
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    clock = time.monotonic()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    digests = {"stdout": hashlib.sha256(), "stderr": hashlib.sha256()}
    sizes = {"stdout": 0, "stderr": 0}
    timed_out = False
    try:
        process = subprocess.Popen(
            argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, shell=False, start_new_session=(os.name == "posix"),
        )
    except OSError as exc:
        raise EvidenceError(f"command launch failed: {exc}") from exc

    def drain(name: str, stream: object) -> None:
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                sizes[name] += len(chunk)
                digests[name].update(chunk)
                remaining = max_bytes - len(buffers[name])
                if remaining > 0:
                    buffers[name].extend(chunk[:remaining])
        finally:
            stream.close()

    threads = [threading.Thread(target=drain, args=(name, stream), daemon=True)
               for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))]
    for thread in threads:
        thread.start()
    try:
        exit_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait()
        exit_code = None
    for thread in threads:
        thread.join(timeout=5)
    if any(thread.is_alive() for thread in threads):
        raise EvidenceError("output pipes remain open after process exit")
    elapsed = time.monotonic() - clock
    out, err = bytes(buffers["stdout"]), bytes(buffers["stderr"])
    stdout_size, stderr_size = sizes["stdout"], sizes["stderr"]

    return {
        "schema": "agent-evidence/command-receipt/v1",
        "argv": argv,
        "cwd": str(cwd),
        "started_at": started,
        "duration_seconds": round(elapsed, 6),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout": {"size": stdout_size, "sha256": digests["stdout"].hexdigest(), "captured": out.decode("utf-8", errors="replace"), "truncated": stdout_size > max_bytes},
        "stderr": {"size": stderr_size, "sha256_prefix": digests["stderr"].hexdigest(), "captured": err.decode("utf-8", errors="replace"), "truncated": stderr_size > max_bytes},
    }


def publish_json(destination: Path, value: dict[str, object]) -> None:
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise EvidenceError("destination already exists")
    fd, temporary = tempfile.mkstemp(prefix=".evidence-", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        os.unlink(temporary)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("capture", "verify"):
        p = sub.add_parser(name)
        p.add_argument("root", type=Path)
        p.add_argument("manifest", type=Path)
    p = sub.add_parser("inspect")
    p.add_argument("manifest", type=Path)
    p = sub.add_parser("run", help="execute explicit argv and publish a bounded command receipt")
    p.add_argument("--cwd", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--max-output-bytes", type=int, default=65536)
    p.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        if args.action == "run":
            command = args.command[1:] if args.command[:1] == ["--"] else args.command
            receipt = run_receipt(command, args.cwd, timeout=args.timeout, max_bytes=args.max_output_bytes)
            publish_json(args.receipt, receipt)
            print(json.dumps({"exit_code": receipt["exit_code"], "timed_out": receipt["timed_out"], "receipt": str(args.receipt)}, sort_keys=True))
            return 124 if receipt["timed_out"] else (receipt["exit_code"] if isinstance(receipt["exit_code"], int) else 1)
        if args.action == "inspect":
            value = _load(args.manifest)
            print(json.dumps({"schema": SCHEMA, "count": len(value["artifacts"])}, sort_keys=True))
        elif args.action == "capture":
            root = args.root.resolve(strict=True)
            destination = args.manifest.resolve()
            if destination == root or root in destination.parents:
                raise EvidenceError("manifest must be outside evidence root")
            value = capture(root)
            # Publish complete manifests only; a crash leaves a temporary file,
            # never a truncated manifest at the requested destination.
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                raise EvidenceError("manifest destination already exists")
            fd, temporary = tempfile.mkstemp(prefix=".evidence-", suffix=".tmp", dir=destination.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(value, stream, sort_keys=True, separators=(",", ":"))
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                # Exclusive hard-link publication rejects competing writers.
                os.link(temporary, destination)
                directory_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                os.unlink(temporary)
            print(json.dumps({"schema": SCHEMA, "count": len(value["artifacts"])}, sort_keys=True))
        else:
            print(json.dumps({"verified": verify(args.root, args.manifest)}, sort_keys=True))
    except (EvidenceError, OSError) as exc:
        print(f"evidence: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
