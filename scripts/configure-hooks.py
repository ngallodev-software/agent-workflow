#!/usr/bin/env python3
"""Install agent-workflow reminder/discovery hooks into Codex and Claude."""

from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
from pathlib import Path


def regular_file(path: Path, label: str) -> None:
    if path.is_symlink():
        raise SystemExit(f"refusing to configure {label}: symlink path: {path}")
    if path.exists() and not path.is_file():
        raise SystemExit(f"refusing to configure {label}: not a regular file: {path}")


def atomic_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode or 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def configure_codex(path: Path, hooks_dir: Path, cbm_gate: str) -> None:
    regular_file(path, "Codex hooks")
    marker = "# agent-workflow managed reminder hooks"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in existing:
        print(f"kept existing agent-workflow Codex hooks: {path}")
        return
    entries = [
        ("agent-workflow-session-reminder", "Loading agent-workflow delegation policy"),
        ("rtk-session-reminder", "Loading RTK command policy"),
        ("codebase-memory-session-reminder", "Loading codebase-memory discovery policy"),
    ]
    block = [marker]
    for name, status in entries:
        block.extend(
            [
                "[[hooks.SessionStart]]",
                "[[hooks.SessionStart.hooks]]",
                'type = "command"',
                f"command = {json.dumps(str(hooks_dir / name))}",
                "timeout = 10",
                f"statusMessage = {json.dumps(status)}",
                "",
            ]
        )
    if cbm_gate:
        block.extend(
            [
                "[[hooks.PreToolUse]]",
                'matcher = "^(Read|Grep|Glob)$"',
                "",
                "[[hooks.PreToolUse.hooks]]",
                'type = "command"',
                f"command = {json.dumps(cbm_gate)}",
                "timeout = 10",
                'statusMessage = "Checking graph-first code discovery"',
                "",
            ]
        )
    separator = "\n" if existing and not existing.endswith("\n\n") else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(existing + separator + "\n".join(block), encoding="utf-8")
    print(f"configured agent-workflow Codex hooks: {path}")


def add_claude_hook(hooks: dict[str, object], event: str, command: str, matcher: str | None = None) -> None:
    groups = hooks.setdefault(event, [])
    if not isinstance(groups, list):
        raise SystemExit(f"Claude hooks.{event} is not an array")
    group = next(
        (item for item in groups if isinstance(item, dict) and item.get("matcher") == matcher),
        None,
    )
    if group is None:
        group = {"hooks": []}
        if matcher is not None:
            group["matcher"] = matcher
        groups.append(group)
    entries = group.setdefault("hooks", [])
    if not isinstance(entries, list):
        raise SystemExit(f"Claude hooks.{event}.hooks is not an array")
    if not any(isinstance(item, dict) and item.get("command") == command for item in entries):
        entries.append({"type": "command", "command": command})


def configure_claude(path: Path, hooks_dir: Path, cbm_gate: str) -> None:
    regular_file(path, "Claude hooks")
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"refusing to configure Claude hooks: invalid JSON: {path}: {exc}") from exc
    else:
        data = {}
    if not isinstance(data, dict):
        raise SystemExit(f"refusing to configure Claude hooks: top-level JSON is not an object: {path}")
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise SystemExit(f"refusing to configure Claude hooks: hooks is not an object: {path}")
    add_claude_hook(hooks, "SessionStart", str(hooks_dir / "agent-workflow-session-reminder"))
    add_claude_hook(hooks, "SessionStart", str(hooks_dir / "rtk-session-reminder"))
    add_claude_hook(hooks, "SessionStart", str(hooks_dir / "codebase-memory-session-reminder"))
    if cbm_gate:
        add_claude_hook(hooks, "PreToolUse", cbm_gate, "Read|Grep|Glob")
    atomic_json(path, data)
    print(f"configured agent-workflow Claude hooks: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-config", type=Path, required=True)
    parser.add_argument("--claude-config", type=Path, required=True)
    parser.add_argument("--hooks-dir", type=Path, required=True)
    parser.add_argument("--cbm-gate", default="")
    parser.add_argument("--claude-cbm-gate", default="")
    args = parser.parse_args()
    configure_codex(args.codex_config, args.hooks_dir, args.cbm_gate)
    configure_claude(args.claude_config, args.hooks_dir, args.claude_cbm_gate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
