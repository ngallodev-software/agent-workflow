#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import stat
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_workflow.release_evidence import validate_dependency_lock

EXPECTED_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")

errors: list[str] = []

EXCLUDED_DIRS = {
    ".agent-workflow-handoff",
    ".claude",
    ".claude-flow",
    ".codebase-memory",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".swarm",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "scripts.orig",
    "templates.orig",
    "testing-output",
}
EXCLUDED_FILES = {".coverage", "docs/BACKLOG.html"}


def release_files(root: Path = ROOT) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        if any(
            part in EXCLUDED_DIRS or part.endswith(".egg-info")
            for part in rel.parts[:-1]
        ):
            continue
        if any(part == ".git" for part in rel.parts):
            continue
        if rel.as_posix() in EXCLUDED_FILES or rel.suffix in {".pyc", ".sha256", ".zst"}:
            continue
        files.append(path)
    return tuple(sorted(files))

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


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
        return value[1:-1]
    return value


def _backlog_rows() -> dict[str, dict[str, str]]:
    path = ROOT / "docs" / "BACKLOG.md"
    rows: dict[str, dict[str, str]] = {}
    section = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("## "):
            section = raw[3:].strip()
            continue
        if not raw.startswith("|"):
            continue
        cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
        if not cells:
            continue
        item_id = cells[0]
        if item_id in {"ID", "Release", "---"} or set(item_id) <= {"-", ":"}:
            continue
        if not re.fullmatch(r"[A-Z][A-Z0-9-]*", item_id) or "-" not in item_id:
            continue
        if item_id in rows:
            fail(f"docs/BACKLOG.md: duplicate active ID {item_id}")
            continue
        state = ""
        for candidate in cells[1:5]:
            if candidate in {"ready", "blocked", "needs-decision", "deferred", "done", "completed", "in-progress", "in-review"}:
                state = candidate
                break
        rows[item_id] = {"section": section, "state": state}
    return rows


def _manifest_tasks(path: Path) -> list[dict[str, str]]:
    tasks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if raw.startswith("  - "):
            if current is not None:
                tasks.append(current)
            current = {"_line": str(number)}
            remainder = raw[4:].strip()
            key, sep, value = remainder.partition(":")
            if sep:
                current[key.strip()] = _unquote(value)
            continue
        if current is not None and raw.startswith("    "):
            key, sep, value = raw.strip().partition(":")
            if sep:
                current[key.strip()] = _unquote(value)
    if current is not None:
        tasks.append(current)
    return tasks


def _pack_declared_backlog_ids(path: Path) -> set[str]:
    declared: set[str] = set()
    in_items = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("backlog_items:"):
            in_items = True
            continue
        if in_items:
            if raw.startswith("  - "):
                declared.add(_unquote(raw[4:].strip()))
                continue
            if raw and not raw.startswith(" "):
                break
    return declared


def _audit_backlog_and_prompt_pack_ownership() -> None:
    backlog = _backlog_rows()
    packs_root = ROOT / "prompt-packs"
    documented = (ROOT / "docs" / "PROMPT_PACKS.md").read_text(encoding="utf-8")
    global_task_ids: dict[str, str] = {}
    owners: dict[str, set[str]] = {}

    for pack_dir in sorted(path for path in packs_root.iterdir() if path.is_dir()):
        pack_name = pack_dir.name
        if pack_name not in documented:
            fail(f"docs/PROMPT_PACKS.md: active pack {pack_name!r} is not documented")
        pack_yaml = pack_dir / "pack.yaml"
        if not pack_yaml.is_file():
            fail(f"prompt-packs/{pack_name}: missing pack.yaml")
            continue
        match = re.search(r'^pack_id:\s*["\']?([^"\']+)["\']?\s*$', pack_yaml.read_text(encoding="utf-8"), re.MULTILINE)
        if match is None or match.group(1).strip() != pack_name:
            fail(f"prompt-packs/{pack_name}/pack.yaml: pack_id must match directory")
        declared = _pack_declared_backlog_ids(pack_yaml)
        claimed: set[str] = set()
        manifests = sorted(pack_dir.glob("phase-*/task-manifest.yaml"))
        if not manifests:
            fail(f"prompt-packs/{pack_name}: no task manifests")
        for manifest in manifests:
            for task in _manifest_tasks(manifest):
                task_id = task.get("id", "")
                if not task_id:
                    continue
                prior = global_task_ids.get(task_id)
                if prior is not None:
                    fail(f"{manifest.relative_to(ROOT)}: task ID {task_id} already used by {prior}")
                else:
                    global_task_ids[task_id] = str(manifest.relative_to(ROOT))
                task_type = task.get("task_type", "implementation")
                backlog_id = task.get("backlog_id", "")
                if task_type in {"gate", "review"}:
                    if backlog_id:
                        fail(f"{manifest.relative_to(ROOT)}:{task.get('_line')}: gate task {task_id} must not claim backlog_id")
                    continue
                if not backlog_id:
                    fail(f"{manifest.relative_to(ROOT)}:{task.get('_line')}: implementation task {task_id} missing backlog_id")
                    continue
                if backlog_id not in backlog:
                    fail(f"{manifest.relative_to(ROOT)}:{task.get('_line')}: unknown backlog_id {backlog_id}")
                    continue
                if backlog[backlog_id].get("state") == "done":
                    fail(f"{manifest.relative_to(ROOT)}:{task.get('_line')}: active task owns completed backlog item {backlog_id}")
                claimed.add(backlog_id)
                owners.setdefault(backlog_id, set()).add(pack_name)
        if declared != claimed:
            fail(
                f"prompt-packs/{pack_name}/pack.yaml: backlog_items {sorted(declared)} "
                f"do not match task ownership {sorted(claimed)}"
            )

    for backlog_id, pack_names in sorted(owners.items()):
        if len(pack_names) > 1:
            fail(f"docs/BACKLOG.md: {backlog_id} is owned by multiple active packs: {sorted(pack_names)}")

    skill = ROOT / "skills" / "release-drift-auditor" / "SKILL.md"
    if not skill.is_file():
        fail("skills/release-drift-auditor/SKILL.md: missing specialized drift skill")
    for required in [ROOT / "docs" / "references" / "DELEGATION_RUNBOOK.md", ROOT / "skills" / "phase-gate-review" / "SKILL.md"]:
        if "release-drift-auditor" not in required.read_text(encoding="utf-8"):
            fail(f"{required.relative_to(ROOT)}: does not invoke release-drift-auditor")

    future_root = ROOT / "tests" / "future"
    for path in sorted(future_root.glob("test_*.py")):
        ids = set(re.findall(r"\b[A-Z][A-Z0-9-]*-\d+\b", path.read_text(encoding="utf-8")))
        if not ids:
            fail(f"{path.relative_to(ROOT)}: strict future test does not name a backlog ID")
            continue
        unknown = sorted(item for item in ids if item not in backlog)
        if unknown:
            fail(f"{path.relative_to(ROOT)}: unknown backlog IDs {unknown}")


def main(argv: list[str] | None = None) -> int:
    global errors
    errors = []
    parser = argparse.ArgumentParser()
    args = parser.parse_args(argv)
    release_files_root = ROOT
    release_files_list = release_files(release_files_root)

    # Basic text integrity and placeholder policy.
    for path in release_files_list:
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
            fail(
                f"{rel}: unresolved template placeholders outside template assets: "
                f"{sorted(set(placeholders))}"
            )

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
            fail(
                f"{path.relative_to(ROOT)}: frontmatter name {name!r} must match "
                f"directory {skill_dir.name!r}"
            )
        if not description or len(description) < 20:
            fail(f"{path.relative_to(ROOT)}: description is missing or too vague")
        if name in skill_names:
            fail(f"{path.relative_to(ROOT)}: duplicate skill name {name!r}")
        skill_names.add(name)

    # JSON and JSON Schema syntax.
    for path in (path for path in release_files_list if path.suffix == ".json"):
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

    # Release policy and direct dependency lock must be schema-valid and synchronized.
    policy_path = ROOT / "release" / "release-policy.json"
    lock_path = ROOT / "release" / "dependency-lock.json"
    for required in (policy_path, lock_path):
        if not required.is_file() or required.is_symlink():
            fail(f"{required.relative_to(ROOT)}: required regular release metadata file is missing")
    if policy_path.is_file() and lock_path.is_file():
        try:
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            import jsonschema

            policy_schema = json.loads((ROOT / "schemas" / "release-policy.schema.json").read_text(encoding="utf-8"))
            lock_schema = json.loads((ROOT / "schemas" / "dependency-lock.schema.json").read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(policy_schema).validate(policy)
            jsonschema.Draft202012Validator(lock_schema).validate(lock)
            for label, value in (("release policy", policy), ("dependency lock", lock)):
                if value.get("project") != "agent-workflow" or value.get("version") != EXPECTED_VERSION:
                    fail(f"release/{label}: project/version must match VERSION")
            for message in validate_dependency_lock(ROOT, lock):
                fail(f"release/dependency-lock.json: {message}")
            pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
            release_data = set(
                pyproject.get("tool", {})
                .get("setuptools", {})
                .get("data-files", {})
                .get("share/agent-workflow/release", [])
            )
            if "release/*.json" not in release_data:
                fail("pyproject.toml: release policy and dependency lock are not included in built artifacts")
        except Exception as exc:
            fail(f"release metadata validation failed: {exc}")

    # TOML files and documented TOML examples must parse.
    for path in (path for path in release_files_list if path.suffix == ".toml"):
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
        for path in (path for path in release_files_list if path.suffix == ".yaml"):
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
        ROOT / "docs/man/agent-workflow.1": f"agent-workflow {EXPECTED_VERSION}",
        ROOT / "docs/man/agent-workflow-workflow.1": f"agent-workflow {EXPECTED_VERSION}",
        ROOT / "docs/man/agent-workflow-mcp.1": f"agent-workflow {EXPECTED_VERSION}",
        ROOT / "docs/diagrams/REPOSITORY_CHART_PACK.md": f"**Release:** {EXPECTED_VERSION}",
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
        ROOT / "docs" / "references" / "EXECUTION_PROTOCOL.md": [
            ROOT / "src/agent_workflow/assets/prompt-pack-root/EXECUTION_PROTOCOL.md",
            ROOT / "examples/three-phase-pack/EXECUTION_PROTOCOL.md",
        ],
        ROOT / "docs" / "references" / "DELEGATION_RUNBOOK.md": [
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
    for path in [
        ROOT / "install.sh",
        ROOT / "uninstall.sh",
        ROOT / "bin/agent-workflow",
        *sorted((ROOT / "scripts").glob("*.sh")),
        ROOT / "scripts/hooks/agent-workflow-session-reminder",
        ROOT / "scripts/hooks/codebase-memory-session-reminder",
        ROOT / "scripts/hooks/rtk-session-reminder",
    ]:
        if not path.stat().st_mode & stat.S_IXUSR:
            fail(f"{path.relative_to(ROOT)}: is not executable")

    # Local Markdown links must resolve.
    for path in (path for path in release_files_list if path.suffix == ".md"):
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


    # Canonical backlog/prompt-pack ownership and drift policy.
    _audit_backlog_and_prompt_pack_ownership()

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("release assets: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
