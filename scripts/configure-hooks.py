#!/usr/bin/env python3
"""Install agent-workflow reminder/discovery hooks into Codex and Claude."""

from __future__ import annotations

import argparse
import json
import os
import shlex
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


def codex_gate_command(hooks_dir: Path, cbm_gate: str) -> str:
    return shlex.join([str(hooks_dir / "codex-code-discovery-gate"), cbm_gate])


def render_codex_hooks(hooks_dir: Path, cbm_gate: str) -> str:
    entries = [
        ("agent-workflow-run-reminder", "Loading agent-workflow delegation policy"),
        ("rtk-session-reminder", "Loading RTK command policy"),
        ("codebase-memory-session-reminder", "Loading codebase-memory discovery policy"),
    ]
    block = ["# agent-workflow managed reminder hooks"]
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
                'matcher = "^Bash$"',
                "",
                "[[hooks.PreToolUse.hooks]]",
                'type = "command"',
                f"command = {json.dumps(codex_gate_command(hooks_dir, cbm_gate))}",
                "timeout = 10",
                'statusMessage = "Checking graph-first code discovery"',
                "",
            ]
        )
    block.append("# end agent-workflow managed reminder hooks")
    return "\n".join(block)


def configure_codex(path: Path, hooks_dir: Path, cbm_gate: str) -> None:
    regular_file(path, "Codex hooks")
    begin = "# agent-workflow managed reminder hooks"
    end = "# end agent-workflow managed reminder hooks"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    managed = render_codex_hooks(hooks_dir, cbm_gate)

    # Collapse every historical Agent-Workflow managed block to one canonical
    # block. Older releases could leave a terminal block without an end marker.
    kept: list[str] = []
    remaining = existing
    while begin in remaining:
        prefix, remainder = remaining.split(begin, 1)
        kept.append(prefix.rstrip())
        if end in remainder:
            _owned, remaining = remainder.split(end, 1)
            remaining = remaining.lstrip()
        else:
            # A legacy unterminated managed block was terminal by contract.
            remaining = ""
            break
    kept.append(remaining.strip())
    content = "\n\n".join(part for part in [*kept, managed] if part).strip()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + ("\n" if content else ""), encoding="utf-8")
    print(f"configured agent-workflow Codex hooks: {path}")

def _owned_hook_command(command: object, hooks_dir: Path) -> bool:
    if not isinstance(command, str) or not command:
        return False
    try:
        first = shlex.split(command)[0]
    except (ValueError, IndexError):
        return False
    try:
        Path(first).resolve().relative_to(hooks_dir.resolve())
    except (OSError, ValueError):
        return False
    return True


def _strip_owned_claude_hooks(
    hooks: dict[str, object], hooks_dir: Path, extra_owned: tuple[str, ...] = ()
) -> None:
    for event, groups in list(hooks.items()):
        if not isinstance(groups, list):
            continue
        retained_groups: list[object] = []
        for group in groups:
            if not isinstance(group, dict):
                retained_groups.append(group)
                continue
            entries = group.get("hooks")
            if not isinstance(entries, list):
                retained_groups.append(group)
                continue
            retained = [
                entry
                for entry in entries
                if not (
                    isinstance(entry, dict)
                    and (
                        _owned_hook_command(entry.get("command"), hooks_dir)
                        or entry.get("command") in extra_owned
                    )
                )
            ]
            if retained:
                updated = dict(group)
                updated["hooks"] = retained
                retained_groups.append(updated)
        hooks[event] = retained_groups


def add_claude_hook(
    hooks: dict[str, object],
    event: str,
    command: str,
    matcher: str | None = None,
) -> None:
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

    # Remove every hook command previously installed from our managed hook
    # directory, regardless of duplicate event/matcher grouping, then add one
    # canonical set. Unrelated user hooks are preserved.
    _strip_owned_claude_hooks(
        hooks,
        hooks_dir,
        (cbm_gate,) if cbm_gate else (),
    )
    add_claude_hook(hooks, "SessionStart", str(hooks_dir / "agent-workflow-run-reminder"))
    add_claude_hook(hooks, "SessionStart", str(hooks_dir / "rtk-session-reminder"))
    add_claude_hook(hooks, "SessionStart", str(hooks_dir / "codebase-memory-session-reminder"))
    if cbm_gate:
        add_claude_hook(hooks, "PreToolUse", cbm_gate, "Read|Grep|Glob")
    atomic_json(path, data)
    print(f"configured agent-workflow Claude hooks: {path}")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-config", type=Path, required=True)
    parser.add_argument("--claude-settings", type=Path, required=True)
    parser.add_argument("--hooks-dir", type=Path, required=True)
    parser.add_argument("--cbm-gate", default="")
    parser.add_argument("--claude-cbm-gate", default="")
    args = parser.parse_args()
    configure_codex(args.codex_config, args.hooks_dir, args.cbm_gate)
    configure_claude(args.claude_settings, args.hooks_dir, args.claude_cbm_gate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
