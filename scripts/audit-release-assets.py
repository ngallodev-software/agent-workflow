#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")

errors: list[str] = []

EXCLUDED_DIRS = {
    ".codebase-memory",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "scripts.orig",
    "templates.orig",
}
EXCLUDED_FILES = {".coverage", "MANIFEST.sha256"}


def release_files() -> tuple[Path, ...]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(ROOT)
        if any(
            part in EXCLUDED_DIRS or part.endswith(".egg-info")
            for part in rel.parts[:-1]
        ):
            continue
        if rel.name in EXCLUDED_FILES or rel.suffix in {".pyc", ".sha256", ".zst"}:
            continue
        files.append(path)
    return tuple(sorted(files))


parser = argparse.ArgumentParser()
parser.add_argument(
    "--write-manifest",
    action="store_true",
    help="regenerate the repository release manifest before validating it",
)
args = parser.parse_args()
RELEASE_FILES = release_files()

if args.write_manifest:
    manifest_lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
        f"{path.relative_to(ROOT).as_posix()}"
        for path in RELEASE_FILES
    ]
    (ROOT / "MANIFEST.sha256").write_text(
        "\n".join(manifest_lines) + "\n", encoding="utf-8"
    )


def fail(message: str) -> None:
    errors.append(message)


def parse_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        fail(f"{path.relative_to(ROOT)}: missing opening YAML frontmatter delimiter")
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        fail(f"{path.relative_to(ROOT)}: missing closing YAML frontmatter delimiter")
        return {}
    data: dict[str, str] = {}
    for index, line in enumerate(lines[1:end], 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep or not key.strip() or not value.strip():
            fail(f"{path.relative_to(ROOT)}:{index}: invalid frontmatter entry")
            continue
        data[key.strip()] = value.strip().strip('"\'')
    return data


# Basic text integrity and placeholder policy.
for path in RELEASE_FILES:
    data = path.read_bytes()
    rel = path.relative_to(ROOT)
    if b"\x00" in data:
        fail(f"{rel}: contains NUL bytes")
    if b"\r\n" in data:
        fail(f"{rel}: contains CRLF line endings")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        continue
    placeholders = PLACEHOLDER_RE.findall(text)
    if placeholders and not (
        str(rel).startswith("templates/")
        or str(rel).startswith("src/agent_workflow/assets/")
        or rel == Path("src/agent_workflow/pack.py")
        or rel == Path("scripts/audit-release-assets.py")
    ):
        fail(f"{rel}: unresolved template placeholders outside template assets: {sorted(set(placeholders))}")

# Skills must be discoverable and correctly named.
skill_names: set[str] = set()
for skill_dir in sorted((ROOT / "skills").iterdir()):
    if not skill_dir.is_dir():
        continue
    path = skill_dir / "SKILL.md"
    if not path.is_file():
        fail(f"skills/{skill_dir.name}: missing SKILL.md")
        continue
    metadata = parse_frontmatter(path)
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if name != skill_dir.name:
        fail(f"{path.relative_to(ROOT)}: frontmatter name {name!r} must match directory {skill_dir.name!r}")
    if not description or len(description) < 20:
        fail(f"{path.relative_to(ROOT)}: description is missing or too vague")
    if name in skill_names:
        fail(f"{path.relative_to(ROOT)}: duplicate skill name {name!r}")
    skill_names.add(name)

# JSON and JSON Schema syntax.
for path in (path for path in RELEASE_FILES if path.suffix == ".json"):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
        continue
    if path.parent.name == "schemas":
        try:
            import jsonschema
            jsonschema.Draft202012Validator.check_schema(value)
        except ImportError:
            pass
        except Exception as exc:
            fail(f"{path.relative_to(ROOT)}: invalid JSON Schema: {exc}")

# TOML files and documented TOML examples must parse.
for path in (path for path in RELEASE_FILES if path.suffix == ".toml"):
    try:
        tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        fail(f"{path.relative_to(ROOT)}: invalid TOML: {exc}")
readme = (ROOT / "README.md").read_text(encoding="utf-8")
for index, block in enumerate(re.findall(r"```toml\n(.*?)```", readme, re.DOTALL), 1):
    try:
        tomllib.loads(block)
    except tomllib.TOMLDecodeError as exc:
        fail(f"README.md: TOML block {index} is invalid: {exc}")

# YAML syntax, including unexpanded templates.
try:
    import yaml
except ImportError:
    yaml = None
if yaml is not None:
    for path in (path for path in RELEASE_FILES if path.suffix == ".yaml"):
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"{path.relative_to(ROOT)}: invalid YAML: {exc}")

# Version consistency in authoritative metadata and runtime surfaces.
version_locations = {
    ROOT / "VERSION": EXPECTED_VERSION,
    ROOT / "pyproject.toml": f'version = "{EXPECTED_VERSION}"',
    ROOT / "agent-workflow.yaml": f"version: {EXPECTED_VERSION}",
    ROOT / "src/agent_workflow/__init__.py": f'__version__ = "{EXPECTED_VERSION}"',
    ROOT / "src/agent_workflow/cli.py": f'%(prog)s {EXPECTED_VERSION}',
    ROOT / "src/agent_workflow/doctor.py": f'"version": "{EXPECTED_VERSION}"',
}
for path, needle in version_locations.items():
    if needle not in path.read_text(encoding="utf-8"):
        fail(f"{path.relative_to(ROOT)}: missing expected version marker {needle!r}")

# Portable copies must not drift from their canonical source.
portable_scripts = {
    "archive-prompt-pack.sh",
    "check-delegation.sh",
    "create-ticket-worktree.sh",
    "foreground-delegation.sh",
    "launch-delegation.sh",
    "restart-delegation.sh",
    "stop-delegation.sh",
    "validate-prompt-pack.sh",
}
for canonical in sorted(
    path for path in (ROOT / "scripts").glob("*.sh")
    if path.name in portable_scripts
):
    for mirror_root in [
        ROOT / "templates/prompt-pack/scripts",
        ROOT / "src/agent_workflow/assets/prompt-pack-root/scripts",
    ]:
        mirror = mirror_root / canonical.name
        if not mirror.is_file():
            fail(f"{mirror.relative_to(ROOT)}: missing mirror of scripts/{canonical.name}")
        elif mirror.read_bytes() != canonical.read_bytes():
            fail(f"{mirror.relative_to(ROOT)}: differs from canonical scripts/{canonical.name}")

mirror_groups = {
    ROOT / "EXECUTION_PROTOCOL.md": [
        ROOT / "src/agent_workflow/assets/prompt-pack-root/EXECUTION_PROTOCOL.md",
        ROOT / "examples/three-phase-pack/EXECUTION_PROTOCOL.md",
    ],
    ROOT / "DELEGATION_RUNBOOK.md": [
        ROOT / "src/agent_workflow/assets/prompt-pack-root/DELEGATION_RUNBOOK.md",
        ROOT / "examples/three-phase-pack/DELEGATION_RUNBOOK.md",
    ],
    ROOT / "templates/prompt-pack/ROOT_README.md": [
        ROOT / "src/agent_workflow/assets/prompt-pack-root/README.md",
    ],
    ROOT / "templates/prompt-pack/pack.yaml": [
        ROOT / "src/agent_workflow/assets/prompt-pack-root/pack.yaml",
    ],
    ROOT / "templates/prompt-pack/references-README.md": [
        ROOT / "src/agent_workflow/assets/prompt-pack-root/references/README.md",
    ],
    ROOT / "templates/prompt-pack/CODE_STRUCTURE_OUTLINES.md": [
        ROOT / "src/agent_workflow/assets/prompt-pack-root/references/code-structure-outlines.md",
    ],
    ROOT / "templates/prompt-pack/PHASE_README.md": [
        ROOT / "src/agent_workflow/assets/phase/README.md",
    ],
    ROOT / "templates/prompt-pack/MASTER_IMPLEMENTATION_PROMPT.md": [
        ROOT / "src/agent_workflow/assets/phase/MASTER_IMPLEMENTATION_PROMPT.md",
    ],
    ROOT / "templates/prompt-pack/task-manifest.yaml": [
        ROOT / "src/agent_workflow/assets/phase/task-manifest.yaml",
    ],
    ROOT / "templates/prompt-pack/TICKET_PROMPT.md": [
        ROOT / "src/agent_workflow/assets/phase/tickets/P{{PHASE_NUMBER}}-00-baseline-and-preflight.md",
    ],
    ROOT / "templates/TICKET_COMPLETION.md": [
        ROOT / "src/agent_workflow/assets/prompt-pack-root/templates/TICKET_COMPLETION.md",
    ],
    ROOT / "templates/PHASE_GATE_REPORT.md": [
        ROOT / "src/agent_workflow/assets/prompt-pack-root/templates/PHASE_GATE_REPORT.md",
    ],
    ROOT / "templates/source-baseline.example.json": [
        ROOT / "src/agent_workflow/assets/prompt-pack-root/templates/source-baseline.example.json",
    ],
}
for canonical, mirrors in mirror_groups.items():
    for mirror in mirrors:
        if not mirror.is_file():
            fail(f"{mirror.relative_to(ROOT)}: missing mirror of {canonical.relative_to(ROOT)}")
        elif mirror.read_bytes() != canonical.read_bytes():
            fail(
                f"{mirror.relative_to(ROOT)}: differs from canonical "
                f"{canonical.relative_to(ROOT)}"
            )

# Shell entrypoints must be executable.
for path in [ROOT / "install.sh", ROOT / "uninstall.sh", ROOT / "bin/agent-workflow", *sorted((ROOT / "scripts").glob("*.sh"))]:
    if not path.stat().st_mode & stat.S_IXUSR:
        fail(f"{path.relative_to(ROOT)}: is not executable")

# Local Markdown links must resolve.
for path in (path for path in RELEASE_FILES if path.suffix == ".md"):
    text = path.read_text(encoding="utf-8")
    for target in LINK_RE.findall(text):
        target = target.strip().split()[0].strip("<>")
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = target.split("#", 1)[0]
        if not target:
            continue
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            fail(f"{path.relative_to(ROOT)}: local link escapes repository: {target}")
            continue
        if not resolved.exists():
            fail(f"{path.relative_to(ROOT)}: broken local link: {target}")

# Manifest must cover every regular non-symlink file except itself.
manifest = ROOT / "MANIFEST.sha256"
if manifest.is_file():
    listed: dict[str, str] = {}
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        digest, sep, rel = line.partition("  ")
        if not sep or len(digest) != 64:
            fail(f"MANIFEST.sha256:{number}: malformed line")
            continue
        if rel in listed:
            fail(f"MANIFEST.sha256:{number}: duplicate path {rel}")
        listed[rel] = digest
    actual = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in RELEASE_FILES
    }
    for rel in sorted(actual.keys() - listed.keys()):
        fail(f"MANIFEST.sha256: missing file {rel}")
    for rel in sorted(listed.keys() - actual.keys()):
        fail(f"MANIFEST.sha256: lists nonexistent file {rel}")
    for rel in sorted(actual.keys() & listed.keys()):
        if actual[rel] != listed[rel]:
            fail(f"MANIFEST.sha256: checksum mismatch for {rel}")
else:
    fail("MANIFEST.sha256: missing")

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(1)
print("release assets: valid")
