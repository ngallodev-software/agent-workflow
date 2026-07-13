from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .config import as_dict, load_settings
from .doctor import run_doctor
from .errors import WorkflowError
from .manifests import validate_pack, write_checksum_manifest
from .pack import archive as archive_pack
from .pack import scaffold as scaffold_pack
from .sessions import interrupt as interrupt_session
from .sessions import kill as kill_session
from .sessions import launch as launch_session
from .sessions import observe
from .sessions import restart as restart_session
from .sessions import terminate as terminate_session
from .state import list_statuses, read_status
from .tmux import attach as attach_tmux
from .util import expand_path
from .worktrees import create as create_worktree
from .worktrees import list_worktrees
from .worktrees import remove as remove_worktree


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def _print_table(
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str]],
) -> None:
    if not rows:
        print("No records.")
        return
    widths = {key: len(title) for key, title in columns}
    for row in rows:
        for key, _ in columns:
            widths[key] = max(widths[key], len(str(row.get(key, ""))))
    print("  ".join(title.ljust(widths[key]) for key, title in columns))
    print("  ".join("-" * widths[key] for key, _ in columns))
    for row in rows:
        print(
            "  ".join(
                str(row.get(key, "")).ljust(widths[key])
                for key, _ in columns
            )
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-workflow")
    parser.add_argument(
        "--version", action="version", version="%(prog)s 0.1.0"
    )
    parser.add_argument("--config", type=Path, help="override config.toml path")
    parser.add_argument(
        "--json",
        action="store_true",
        help="machine-readable output where supported",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor", help="check environment and configuration")

    config = commands.add_parser("config", help="configuration commands")
    config_commands = config.add_subparsers(
        dest="config_command", required=True
    )
    config_commands.add_parser("show", help="show resolved configuration")

    worktree = commands.add_parser("worktree", help="Git worktree commands")
    worktree_commands = worktree.add_subparsers(
        dest="worktree_command", required=True
    )
    create = worktree_commands.add_parser(
        "create", help="create an isolated ticket worktree"
    )
    create.add_argument("repo", type=Path)
    create.add_argument("ticket_id")
    create.add_argument("base_ref")
    create.add_argument("--dest", type=Path)
    create.add_argument("--branch")
    create.add_argument("--allow-dirty", action="store_true")

    remove = worktree_commands.add_parser("remove", help="remove a worktree")
    remove.add_argument("repo", type=Path)
    remove.add_argument("worktree", type=Path)
    remove.add_argument("--force", action="store_true")
    remove.add_argument("--delete-branch", action="store_true")

    listing = worktree_commands.add_parser(
        "list", help="list repository worktrees"
    )
    listing.add_argument("repo", type=Path)

    launch = commands.add_parser(
        "launch", help="launch a prompt in a fresh tmux session"
    )
    launch.add_argument("session_id")
    launch.add_argument("workdir", type=Path)
    launch.add_argument("prompt", type=Path)
    launch.add_argument("--ticket")
    launch.add_argument("--pack")
    launch.add_argument("--executor")
    launch.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow launching from a Git worktree with uncommitted changes",
    )

    commands.add_parser("list", help="list delegation runs")

    status = commands.add_parser("status", help="inspect a delegation")
    status.add_argument("session_id")
    status.add_argument(
        "--capture", type=int, nargs="?", const=-1, default=0
    )

    attach = commands.add_parser("attach", help="foreground a delegation")
    attach.add_argument("session_id")

    tail = commands.add_parser("tail", help="follow a delegation log")
    tail.add_argument("session_id")
    tail.add_argument("--lines", type=int, default=50)

    interrupt = commands.add_parser(
        "interrupt", help="send Ctrl-C without deleting the session"
    )
    interrupt.add_argument("session_id")

    terminate = commands.add_parser(
        "terminate", help="interrupt, wait, then kill tmux if needed"
    )
    terminate.add_argument("session_id")
    terminate.add_argument("--grace-seconds", type=int, default=8)

    kill = commands.add_parser(
        "kill", help="immediately kill tmux and preserve evidence"
    )
    kill.add_argument("session_id")

    restart = commands.add_parser(
        "restart", help="restart a saved delegation in a new session"
    )
    restart.add_argument("session_id")
    restart.add_argument("--new-session")

    pack = commands.add_parser("pack", help="prompt-pack commands")
    pack_commands = pack.add_subparsers(dest="pack_command", required=True)

    scaffold = pack_commands.add_parser(
        "scaffold", help="create a new prompt-pack skeleton"
    )
    scaffold.add_argument("destination", type=Path)
    scaffold.add_argument("--phases", type=int, default=3)
    scaffold.add_argument("--name")

    validate = pack_commands.add_parser(
        "validate", help="validate pack structure and checksums"
    )
    validate.add_argument("source", type=Path)
    validate.add_argument("--skip-checksums", action="store_true")

    checksum = pack_commands.add_parser(
        "checksum", help="write MANIFEST.sha256"
    )
    checksum.add_argument("source", type=Path)

    archive = pack_commands.add_parser(
        "archive", help="validate and create a deterministic tar.zst"
    )
    archive.add_argument("source", type=Path)
    archive.add_argument("output", type=Path)

    return parser


def _parse_args(
    parser: argparse.ArgumentParser,
    argv: list[str] | None,
) -> argparse.Namespace:
    raw = list(sys.argv[1:] if argv is None else argv)
    explicit_command: list[str] | None = None
    if "--" in raw:
        separator = raw.index("--")
        if "launch" not in raw[:separator]:
            parser.error("-- COMMAND is only supported by launch")
        explicit_command = raw[separator + 1 :]
        raw = raw[:separator]
        if not explicit_command:
            parser.error("missing explicit command after --")
    # argparse normally requires global options before the subcommand.  The
    # workflow CLI accepts --json and --config in either position because the
    # documented/operator-friendly form is often `command --json`.  Only the
    # portion before an explicit launch `-- COMMAND...` separator is normalized.
    normalized_globals: list[str] = []
    normalized_rest: list[str] = []
    index = 0
    while index < len(raw):
        token = raw[index]
        if token == "--json":
            normalized_globals.append(token)
            index += 1
            continue
        if token == "--config":
            if index + 1 >= len(raw):
                parser.error("argument --config: expected one argument")
            normalized_globals.extend([token, raw[index + 1]])
            index += 2
            continue
        if token.startswith("--config="):
            normalized_globals.append(token)
            index += 1
            continue
        normalized_rest.append(token)
        index += 1

    args = parser.parse_args(normalized_globals + normalized_rest)
    setattr(args, "explicit_command", explicit_command)
    return args


def _print_mapping(data: dict[str, Any]) -> None:
    for key, value in data.items():
        if key == "capture" and value:
            print("--- terminal capture ---")
            print(str(value).rstrip())
        elif isinstance(value, (dict, list)):
            print(f"{key}: {json.dumps(value, sort_keys=True)}")
        else:
            print(f"{key}: {value}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = _parse_args(parser, argv)
    try:
        settings = load_settings(args.config)
        data: Any

        if args.command == "doctor":
            data = run_doctor(settings)
        elif args.command == "config":
            data = as_dict(settings)
        elif args.command == "worktree":
            if args.worktree_command == "create":
                data = create_worktree(
                    settings,
                    repo=args.repo,
                    ticket_id=args.ticket_id,
                    base_ref=args.base_ref,
                    destination=args.dest,
                    branch=args.branch,
                    allow_dirty=args.allow_dirty,
                )
            elif args.worktree_command == "remove":
                data = remove_worktree(
                    args.repo,
                    args.worktree,
                    force=args.force,
                    delete_branch=args.delete_branch,
                )
            else:
                data = list_worktrees(args.repo)
        elif args.command == "launch":
            data = launch_session(
                settings,
                session_id=args.session_id,
                workdir=args.workdir,
                prompt_path=args.prompt,
                executor=args.executor,
                explicit_command=args.explicit_command,
                ticket_id=args.ticket,
                pack_id=args.pack,
                allow_dirty=args.allow_dirty,
            )
        elif args.command == "list":
            rows: list[dict[str, Any]] = []
            for item in list_statuses(settings):
                session_id = str(item.get("session_id", ""))
                try:
                    rows.append(observe(settings, session_id))
                except WorkflowError:
                    rows.append(item)
            if args.json:
                _print_json(rows)
            else:
                _print_table(
                    rows,
                    [
                        ("session_id", "SESSION"),
                        ("ticket_id", "TICKET"),
                        ("status", "DURABLE"),
                        ("observed_state", "OBSERVED"),
                        ("branch", "BRANCH"),
                    ],
                )
            return 0
        elif args.command == "status":
            capture_lines = (
                settings.capture_lines if args.capture == -1 else args.capture
            )
            data = observe(settings, args.session_id, capture_lines)
        elif args.command == "attach":
            read_status(settings, args.session_id)
            attach_tmux(args.session_id)
            return 0
        elif args.command == "tail":
            status_data = read_status(settings, args.session_id)
            log = Path(str(status_data["log_path"]))
            os.execvp("tail", ["tail", "-n", str(args.lines), "-f", str(log)])
        elif args.command == "interrupt":
            data = interrupt_session(settings, args.session_id)
        elif args.command == "terminate":
            data = terminate_session(
                settings, args.session_id, args.grace_seconds
            )
        elif args.command == "kill":
            data = kill_session(settings, args.session_id)
        elif args.command == "restart":
            data = restart_session(
                settings, args.session_id, args.new_session
            )
        elif args.command == "pack":
            if args.pack_command == "scaffold":
                data = scaffold_pack(
                    args.destination, args.phases, args.name
                )
            elif args.pack_command == "validate":
                report = validate_pack(
                    expand_path(args.source),
                    verify_checksums=not args.skip_checksums,
                )
                data = report.as_dict()
                if args.json:
                    _print_json(data)
                else:
                    print(f"pack: {report.root}")
                    print(
                        f"phases: {report.phases}; tasks: {report.tasks}; "
                        f"valid: {report.ok}"
                    )
                    for warning in report.warnings:
                        print(f"warning: {warning}")
                    for error in report.errors:
                        print(f"error: {error}", file=sys.stderr)
                return 0 if report.ok else 1
            elif args.pack_command == "checksum":
                path = write_checksum_manifest(expand_path(args.source))
                data = {"manifest": str(path)}
            else:
                data = archive_pack(settings, args.source, args.output)
        else:
            parser.error("unhandled command")
            return 2

        if args.json:
            _print_json(data)
        elif isinstance(data, dict):
            _print_mapping(data)
        else:
            _print_json(data)
        return 0
    except WorkflowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
