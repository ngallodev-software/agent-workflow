"""Parser-backed validation for executable Agent-Workflow skill examples.

Skills are documentation/product-interface assets, not a second command schema. Shell
fences may contain executable ``agent-workflow`` examples; this module extracts those
examples and validates their argv against the live core parser with plugins disabled.
Inline command names remain prose references and are intentionally outside this check.
"""

from __future__ import annotations

import argparse
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from .cli_parser import build_parser
from .plugins import EMPTY_PLUGIN_REGISTRY

_SHELL_FENCE_LANGUAGES = frozenset({"bash", "sh", "shell", "console"})
_FENCE_RE = re.compile(r"^```(?P<language>[A-Za-z0-9_-]*)\s*$")


@dataclass(frozen=True)
class SkillCommandExample:
    path: Path
    line: int
    command: str


class _ParserError(Exception):
    pass


class _RaisingArgumentParser(argparse.ArgumentParser):
    """ArgumentParser variant that reports errors without writing/terminating."""

    def error(self, message: str) -> None:
        raise _ParserError(message)


def _logical_shell_lines(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    logical: list[tuple[int, str]] = []
    pending = ""
    pending_line = 0
    for line_no, raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("$ "):
            stripped = stripped[2:].lstrip()
        if not pending:
            pending_line = line_no
        if stripped.endswith("\\"):
            pending += stripped[:-1].rstrip() + " "
            continue
        pending += stripped
        logical.append((pending_line, pending))
        pending = ""
        pending_line = 0
    if pending:
        logical.append((pending_line, pending.rstrip()))
    return logical


def extract_skill_command_examples(path: Path) -> tuple[SkillCommandExample, ...]:
    """Return executable ``agent-workflow`` commands from shell-fenced skill blocks."""

    examples: list[SkillCommandExample] = []
    in_shell_fence = False
    block_lines: list[tuple[int, str]] = []

    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fence = _FENCE_RE.match(raw.strip())
        if fence:
            if in_shell_fence:
                for command_line, command in _logical_shell_lines(block_lines):
                    if command == "agent-workflow" or command.startswith("agent-workflow "):
                        examples.append(SkillCommandExample(path, command_line, command))
                in_shell_fence = False
                block_lines = []
            else:
                language = fence.group("language").lower()
                in_shell_fence = language in _SHELL_FENCE_LANGUAGES
                block_lines = []
            continue
        if in_shell_fence:
            block_lines.append((line_no, raw))

    return tuple(examples)


def _parser() -> argparse.ArgumentParser:
    # The core parser is the public command authority for skills. Configured plugin
    # commands are deliberately excluded from the normal skill vocabulary.
    parser = build_parser(EMPTY_PLUGIN_REGISTRY)
    parser.__class__ = _RaisingArgumentParser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for child in action.choices.values():
                _raise_parser_errors_recursively(child)
    return parser


def _raise_parser_errors_recursively(parser: argparse.ArgumentParser) -> None:
    parser.__class__ = _RaisingArgumentParser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for child in action.choices.values():
                _raise_parser_errors_recursively(child)


def validate_skill_command_examples(
    skills_root: Path,
) -> tuple[str, ...]:
    """Validate shell-fenced Agent-Workflow skill examples against the live parser."""

    parser = _parser()
    errors: list[str] = []
    for path in sorted(skills_root.glob("*/SKILL.md")):
        for example in extract_skill_command_examples(path):
            try:
                argv = shlex.split(example.command)
            except ValueError as exc:
                rel = path.relative_to(skills_root.parent)
                errors.append(f"{rel}:{example.line}: invalid shell command: {exc}")
                continue
            if not argv or argv[0] != "agent-workflow":
                continue
            try:
                parser.parse_args(argv[1:])
            except (_ParserError, SystemExit) as exc:
                detail = str(exc) or "parser rejected command"
                rel = path.relative_to(skills_root.parent)
                errors.append(
                    f"{rel}:{example.line}: command does not match live parser: "
                    f"{example.command!r}: {detail}"
                )
    return tuple(errors)
