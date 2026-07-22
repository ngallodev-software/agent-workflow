from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .errors import WorkflowError
from .process import run

StreamFormat = str


@dataclass(frozen=True)
class ExecutorPlan:
    name: str | None
    argv: tuple[str, ...]
    stream_format: StreamFormat = "text"


def _insert_before_stdin(argv: list[str], values: list[str]) -> list[str]:
    if "-" in argv:
        index = len(argv) - 1 - argv[::-1].index("-")
        return argv[:index] + values + argv[index:]
    return argv + values


def _infer_executor(argv: list[str]) -> str | None:
    """Identify supported executors from an explicit command's executable."""
    if not argv:
        return None
    executable = Path(argv[0]).name.lower()
    if executable == "codex":
        return "codex"
    if executable in {"claude", "claude-code"}:
        return "claude"
    return None


def prepare_executor(
    settings: Settings,
    executor: str | None,
    explicit: list[str] | None,
    *,
    structured: bool = False,
) -> ExecutorPlan:
    if explicit:
        executor = _infer_executor(explicit)
        argv = list(explicit)
        stream_format = "text"
        if structured and executor == "codex":
            if "--json" not in argv:
                argv = _insert_before_stdin(argv, ["--json"])
            stream_format = "codex-jsonl"
        elif structured and executor == "claude":
            if "--print" in argv and "--verbose" not in argv:
                argv.append("--verbose")
            if "--output-format" not in argv:
                argv.extend(["--output-format", "stream-json"])
            stream_format = "claude-stream-json"
        return ExecutorPlan(executor, tuple(argv), stream_format)
    if not executor:
        raise WorkflowError(
            "provide --executor NAME or an explicit command after --"
        )
    try:
        argv = list(settings.executors[executor])
    except KeyError as exc:
        known = ", ".join(sorted(settings.executors)) or "none"
        raise WorkflowError(
            f"unknown executor {executor!r}; configured executors: {known}"
        ) from exc
    if not argv:
        raise WorkflowError(f"executor {executor!r} has an empty command")
    stream_format = "text"
    if executor == "codex" and "--skip-git-repo-check" not in argv:
        argv = _insert_before_stdin(argv, ["--skip-git-repo-check"])
    if structured and executor == "codex":
        if "--json" not in argv:
            argv = _insert_before_stdin(argv, ["--json"])
        stream_format = "codex-jsonl"
    elif structured and executor == "claude":
        if "--print" in argv and "--verbose" not in argv:
            argv.append("--verbose")
        if "--output-format" not in argv:
            argv.extend(["--output-format", "stream-json"])
        stream_format = "claude-stream-json"
    return ExecutorPlan(executor, tuple(argv), stream_format)


def executor_version(plan: ExecutorPlan) -> str | None:
    result = run([plan.argv[0], "--version"], check=False)
    if result.returncode:
        return None
    return (result.stdout or result.stderr).strip() or None


def parse_event(line: str, stream_format: StreamFormat) -> dict[str, Any] | None:
    if stream_format == "text":
        return None
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def event_text(event: dict[str, Any], stream_format: StreamFormat) -> list[str]:
    result: list[str] = []
    if stream_format == "codex-jsonl":
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if isinstance(text, str):
                result.append(text)
        message = event.get("message")
        if isinstance(message, str) and event.get("type") in {
            "error",
            "warning",
        }:
            result.append(message)
    elif stream_format == "claude-stream-json":
        message = event.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text")
                        if isinstance(text, str):
                            result.append(text)
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            result.append(str(event["result"]))
    return result


def event_usage(event: dict[str, Any]) -> dict[str, Any] | None:
    usage = event.get("usage")
    if isinstance(usage, dict):
        return dict(usage)
    item = event.get("item")
    if isinstance(item, dict) and isinstance(item.get("usage"), dict):
        return dict(item["usage"])
    return None
