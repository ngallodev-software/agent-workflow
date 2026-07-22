from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

from ..errors import WorkflowError
from ..util import atomic_write_json, sha256_file
from .junit import parse_junit


@dataclass(frozen=True)
class CommandSpec:
    id: str
    argv: tuple[str, ...]
    cwd: str = "."
    timeout_seconds: int = 300
    result_format: Literal["junit", "exit-code"] = "exit-code"
    junit_path: str | None = None


def specs_from_data(values: Sequence[dict[str, Any]]) -> list[CommandSpec]:
    return [
        CommandSpec(
            id=str(value["id"]),
            argv=tuple(str(item) for item in value["argv"]),
            cwd=str(value.get("cwd", ".")),
            timeout_seconds=int(value.get("timeout_seconds", 300)),
            result_format=value.get("result_format", "exit-code"),
            junit_path=value.get("junit_path"),
        )
        for value in values
    ]


def _safe_child(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise WorkflowError(f"{label} escapes fixture root: {relative}") from exc
    return path


def collect_commands(
    fixture_root: Path,
    specs: Sequence[CommandSpec],
    *,
    phase: Literal["baseline", "post"],
    receipt_dir: Path,
) -> dict[str, Any]:
    fixture_root = fixture_root.resolve()
    phase_root = receipt_dir / phase
    phase_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spec in specs:
        if not spec.id or spec.id in seen or not spec.argv:
            raise WorkflowError(f"invalid or duplicate command ID: {spec.id!r}")
        seen.add(spec.id)
        cwd = _safe_child(fixture_root, spec.cwd, "command cwd")
        command_root = phase_root / spec.id
        command_root.mkdir(parents=True, exist_ok=False)
        command_path = command_root / "command.json"
        stdout_path = command_root / "stdout.log"
        stderr_path = command_root / "stderr.log"
        started = time.monotonic()
        timed_out = False
        try:
            result = subprocess.run(
                spec.argv,
                cwd=cwd,
                capture_output=True,
                check=False,
                timeout=spec.timeout_seconds,
            )
            exit_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
        except OSError as exc:
            exit_code = 127
            stdout = b""
            stderr = str(exc).encode()
        stdout_path.write_bytes(stdout)
        stderr_path.write_bytes(stderr)
        command = {
            "schema": "agent-workflow/command-collection/v1",
            "id": spec.id,
            "phase": phase,
            "argv": list(spec.argv),
            "cwd": spec.cwd,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "duration_seconds": round(time.monotonic() - started, 6),
            "result_format": spec.result_format,
            "stdout_sha256": sha256_file(stdout_path),
            "stderr_sha256": sha256_file(stderr_path),
            "junit": None,
        }
        if spec.result_format == "junit":
            if not spec.junit_path:
                raise WorkflowError(f"JUnit command {spec.id!r} has no junit_path")
            junit_source = _safe_child(fixture_root, spec.junit_path, "JUnit path")
            junit_target = command_root / "junit.xml"
            if not junit_source.is_file():
                command["junit"] = {"error": "missing"}
            else:
                junit_target.write_bytes(junit_source.read_bytes())
                command["junit"] = {
                    "sha256": sha256_file(junit_target),
                    "tests": parse_junit(junit_target),
                }
        atomic_write_json(command_path, command)
        results.append(command)
    collection = {
        "schema": "agent-workflow/command-collection-set/v1",
        "phase": phase,
        "commands": results,
    }
    atomic_write_json(receipt_dir / f"commands-{phase}.json", collection)
    return collection
