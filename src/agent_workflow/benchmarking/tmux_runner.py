"""Run one benchmark provider command inside an interactive tmux pane."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--stdout", required=True)
    parser.add_argument("--stderr", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--max-stdout", type=int, required=True)
    parser.add_argument("--max-stderr", type=int, required=True)
    parser.add_argument("--allow-env", action="append", default=[])
    parser.add_argument("--set-env", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    try:
        separator = raw.index("--")
    except ValueError:
        print("benchmark tmux runner requires a provider command after --", file=sys.stderr)
        return 2
    options = _parser().parse_args(raw[:separator])
    command = raw[separator + 1 :]
    if not command:
        print("benchmark tmux runner received no provider command", file=sys.stderr)
        return 2

    environment = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "LC_ALL": "C",
        "LANG": "C",
        "LANGUAGE": "C",
        "TZ": "UTC",
    }
    for name in options.allow_env:
        if name in os.environ:
            environment[name] = os.environ[name]
    for item in options.set_env:
        name, separator, value = item.partition("=")
        if not separator or not name or "\x00" in item:
            print(f"invalid benchmark environment assignment: {item!r}", file=sys.stderr)
            return 2
        environment[name] = value

    started = time.monotonic()
    result_path = Path(options.result)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    returncode = 127
    timed_out = False
    error_category = None

    def drain(source: object, destination: object, limit: int, state: dict[str, bool]) -> None:
        total = 0
        while True:
            chunk = source.read(65536)  # type: ignore[union-attr]
            if not chunk:
                break
            remaining = max(0, limit - total)
            if remaining:
                destination.write(chunk[:remaining])  # type: ignore[union-attr]
                destination.flush()  # type: ignore[union-attr]
            if len(chunk) > remaining:
                state["truncated"] = True
            total += len(chunk)

    print(f"benchmark agent pane starting: {' '.join(command)}", flush=True)
    try:
        with (
            Path(options.prompt).open("rb") as prompt,
            Path(options.stdout).open("wb") as stdout_file,
            Path(options.stderr).open("wb") as stderr_file,
        ):
            process = subprocess.Popen(
                command,
                cwd=options.cwd,
                env=environment,
                stdin=prompt,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            stdout_state = {"truncated": False}
            stderr_state = {"truncated": False}
            stdout_thread = threading.Thread(
                target=drain, args=(process.stdout, stdout_file, options.max_stdout, stdout_state), daemon=True
            )
            stderr_thread = threading.Thread(
                target=drain, args=(process.stderr, stderr_file, options.max_stderr, stderr_state), daemon=True
            )
            stdout_thread.start()
            stderr_thread.start()
            try:
                returncode = process.wait(timeout=options.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                error_category = "timeout"
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    returncode = process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    returncode = process.wait()
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)
    except OSError as exc:
        error_category = "launch_failed"
        print(f"benchmark agent launch failed: {exc}", file=sys.stderr, flush=True)

    duration = round(time.monotonic() - started, 6)
    payload = {
        "returncode": returncode,
        "timed_out": timed_out,
        "error_category": error_category,
        "duration_seconds": duration,
        "stdout_truncated": stdout_state["truncated"] if "stdout_state" in locals() else False,
        "stderr_truncated": stderr_state["truncated"] if "stderr_state" in locals() else False,
    }
    result_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    print(f"benchmark agent pane finished: returncode={returncode} duration={duration}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
