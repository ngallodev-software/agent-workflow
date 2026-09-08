#!/usr/bin/env python3
"""Check or apply the repository's explicit semantic-version bump."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "VERSION"
PYPROJECT = ROOT / "pyproject.toml"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PROJECT_VERSION = re.compile(r'(?m)^version = "([^"]+)"$')
JSON_VERSION = object()
AUTHORITIES = (
    (PYPROJECT, PROJECT_VERSION),
    (ROOT / "agent-workflow.yaml", re.compile(r"(?m)^version: (\S+)$")),
    (ROOT / "src/agent_workflow/__init__.py", re.compile(r'__version__ = "([^"]+)"')),
    (ROOT / "docs/man/agent-workflow-workflow.1", re.compile(r"agent-workflow ([0-9.]+)")),
    (ROOT / "docs/man/agent-workflow-index.1", re.compile(r"agent-workflow ([0-9.]+)")),
    (ROOT / "release/release-policy.json", JSON_VERSION),
    (ROOT / "release/dependency-lock.json", JSON_VERSION),
)


def authority_matches(path: Path, pattern: object) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if pattern is JSON_VERSION:
        document = json.loads(text)
        value = document.get("version")
        return [value] if isinstance(value, str) else []
    return pattern.findall(text)  # type: ignore[union-attr]


def replace_authority(path: Path, pattern: object, current: str, next_version: str) -> None:
    text = path.read_text(encoding="utf-8")
    if pattern is JSON_VERSION:
        schema_match = re.search(r'(?m)^(?P<indent>[ \t]+)"schema":', text)
        if schema_match is None:
            raise SystemExit(f"{path.relative_to(ROOT)} has no schema property")
        indent = re.escape(schema_match.group("indent"))
        version_pattern = re.compile(rf'(?m)^{indent}"version": "{re.escape(current)}",?$')
        updated, count = version_pattern.subn(
            lambda match: match.group(0).replace(current, next_version), text, count=1
        )
        if count != 1:
            raise SystemExit(f"{path.relative_to(ROOT)} has no top-level version authority")
    else:
        updated = pattern.sub(  # type: ignore[union-attr]
            lambda match: match.group(0).replace(current, next_version), text, count=1
        )
    path.write_text(updated, encoding="utf-8")


def read_version() -> str:
    value = VERSION.read_text(encoding="utf-8").strip()
    if not SEMVER.fullmatch(value):
        raise SystemExit(f"VERSION is not a semantic version: {value!r}")
    return value


def check() -> str:
    version = read_version()
    for path, pattern in AUTHORITIES:
        matches = authority_matches(path, pattern)
        if matches != [version]:
            raise SystemExit(f"VERSION={version} disagrees with {path.relative_to(ROOT)}={matches!r}")
    cli_parser = (ROOT / "src/agent_workflow/cli_parser.py").read_text(encoding="utf-8")
    if 'version=f"%(prog)s {__version__}"' not in cli_parser:
        raise SystemExit("cli_parser.py does not derive --version from __version__")
    doctor = (ROOT / "src/agent_workflow/doctor.py").read_text(encoding="utf-8")
    if '"version": __version__' not in doctor:
        raise SystemExit("doctor.py does not derive its version from __version__")
    return version


def bumped(version: str, kind: str) -> str:
    major, minor, patch = (int(item) for item in version.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--bump", choices=("major", "minor", "patch"))
    args = parser.parse_args()
    if args.check:
        print(check())
        return
    current = check()
    next_version = bumped(current, args.bump)
    VERSION.write_text(next_version + "\n", encoding="utf-8")
    for path, pattern in AUTHORITIES:
        replace_authority(path, pattern, current, next_version)
    print(next_version)


if __name__ == "__main__":
    main()
