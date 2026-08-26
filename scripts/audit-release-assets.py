#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import stat
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_workflow.release_evidence import validate_dependency_lock
from agent_workflow.manifests import load_pack_manifest, validate_pack
from agent_workflow.pack import scaffold as scaffold_pack
from agent_workflow.benchmarking.contracts import validate_executor_config, validate_spec
from agent_workflow.benchmarking.service import materialize_builtin_suite
from agent_workflow.skill_examples import validate_skill_command_examples
from agent_workflow.skill_evals import validate_primary_skill_behavior

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
BINARY_SUFFIXES = {".gif", ".ico", ".jpeg", ".jpg", ".png", ".webp"}


def release_files(root: Path = ROOT) -> tuple[Path, ...]:
    ignored: set[Path] = set()
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "--stdin", "-z"],
            input="".join(
                f"{path.relative_to(root).as_posix()}\0"
                for path in root.rglob("*")
                if path.is_file() and not path.is_symlink()
            ).encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        ignored = {root / item for item in result.stdout.decode().split("\0") if item}
    except OSError:
        pass
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if path in ignored:
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
        if raw.startswith("### "):
            heading = raw[4:].strip()
            title_ids = heading.split("—", 1)[0].strip()
            ids = [item.strip() for item in title_ids.split("/")]
            for item_id in ids:
                if not re.fullmatch(r"[A-Z][A-Z0-9-]*-\d+", item_id):
                    continue
                if item_id in rows:
                    fail(f"docs/BACKLOG.md: duplicate active ID {item_id}")
                else:
                    rows[item_id] = {"section": section, "state": ""}
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


def _audit_backlog_and_prompt_pack_ownership() -> None:
    backlog = _backlog_rows()
    packs_root = ROOT / "prompt-packs"
    documented = (ROOT / "docs" / "PROMPT_PACKS.md").read_text(encoding="utf-8")
    global_task_ids: dict[str, str] = {}
    owners: dict[str, set[str]] = {}

    pack_dirs = (
        sorted(path for path in packs_root.iterdir() if path.is_dir() and (path / "pack.yaml").is_file())
        if packs_root.is_dir()
        else []
    )
    for pack_dir in pack_dirs:
        pack_name = pack_dir.name
        if pack_name not in documented:
            fail(f"docs/PROMPT_PACKS.md: active pack {pack_name!r} is not documented")
        report = validate_pack(pack_dir)
        if not report.ok:
            for error in report.errors:
                fail(f"prompt-packs/{pack_name}: {error}")
            continue
        try:
            manifest = load_pack_manifest(pack_dir)
        except Exception as exc:
            fail(f"prompt-packs/{pack_name}/pack.yaml: {exc}")
            continue
        if manifest.get("pack_id") != pack_name:
            fail(f"prompt-packs/{pack_name}/pack.yaml: pack_id must match directory")
        declared = {str(item) for item in manifest.get("backlog_items", [])}
        claimed: set[str] = set()
        for phase_index, phase in enumerate(manifest.get("phases", [])):
            if not isinstance(phase, dict):
                continue
            for task_index, task in enumerate(phase.get("tasks", [])):
                if not isinstance(task, dict):
                    continue
                task_id = str(task.get("id", ""))
                if not task_id:
                    continue
                location = f"prompt-packs/{pack_name}/pack.yaml:phases[{phase_index}].tasks[{task_index}]"
                prior = global_task_ids.get(task_id)
                if prior is not None:
                    fail(f"{location}: task ID {task_id} already used by {prior}")
                else:
                    global_task_ids[task_id] = location
                task_type = str(task.get("task_type", "implementation"))
                backlog_id = str(task.get("backlog_id") or "")
                if task_type in {"gate", "review", "historical"}:
                    if backlog_id:
                        fail(f"{location}: {task_type} task {task_id} must not claim backlog_id")
                    continue
                if not backlog_id:
                    fail(f"{location}: implementation task {task_id} missing backlog_id")
                    continue
                if backlog_id not in backlog:
                    fail(f"{location}: unknown backlog_id {backlog_id}")
                    continue
                if backlog[backlog_id].get("state") == "done":
                    fail(f"{location}: active task owns completed backlog item {backlog_id}")
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
    for required in [ROOT / "skills" / "phase-gate-review" / "SKILL.md"]:
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



def _audit_builtin_benchmark_layouts() -> None:
    """Validate canonical layered built-ins and reject a duplicate authoring mirror."""
    duplicate_root = ROOT / "benchmarks" / "specs"
    if duplicate_root.exists():
        fail(f"{duplicate_root.relative_to(ROOT)}: duplicate benchmark source mirror must not exist")

    package_root = ROOT / "src" / "agent_workflow" / "assets" / "benchmarks"
    if not package_root.is_dir():
        fail(f"{package_root.relative_to(ROOT)}: built-in benchmark assets are missing")
        return

    shared_root = package_root / "_shared"
    if not shared_root.is_dir():
        fail(f"{shared_root.relative_to(ROOT)}: shared benchmark layers are missing")
        return

    for suite in sorted(path for path in package_root.iterdir() if path.is_dir() and path.name != "_shared"):
        layout_path = suite / "suite-layout.json"
        try:
            layout = json.loads(layout_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            fail(f"{layout_path.relative_to(ROOT)}: invalid built-in suite layout: {exc}")
            continue
        layers = layout.get("layers") if isinstance(layout, dict) else None
        if not isinstance(layers, list) or not layers:
            fail(f"{layout_path.relative_to(ROOT)}: layers must be a non-empty list")
            continue

        layer_files: dict[Path, Path] = {}
        for layer in layers:
            if not isinstance(layer, str) or not layer.startswith("_shared/"):
                fail(f"{layout_path.relative_to(ROOT)}: invalid shared layer {layer!r}")
                continue
            layer_root = package_root / layer
            if not layer_root.is_dir():
                fail(f"{layout_path.relative_to(ROOT)}: missing shared layer {layer}")
                continue
            for path in layer_root.rglob("*"):
                if not path.is_file() or path.is_symlink():
                    continue
                rel = path.relative_to(layer_root)
                previous = layer_files.get(rel)
                if previous is not None:
                    fail(
                        f"{layout_path.relative_to(ROOT)}: shared layers overlap at {rel}; "
                        f"{previous.relative_to(ROOT)} and {path.relative_to(ROOT)}"
                    )
                else:
                    layer_files[rel] = path

        for path in suite.rglob("*"):
            if not path.is_file() or path.is_symlink() or path == layout_path:
                continue
            rel = path.relative_to(suite)
            shared = layer_files.get(rel)
            if shared is not None and shared.read_bytes() == path.read_bytes():
                fail(f"{path.relative_to(ROOT)}: duplicates identical content already supplied by a shared layer")

        try:
            with tempfile.TemporaryDirectory(prefix=f"aw-benchmark-{suite.name}-") as temp_dir:
                materialized = materialize_builtin_suite(Path(temp_dir) / suite.name, suite.name)
                validate_spec(materialized / "benchmark-spec.json")
                validate_executor_config(materialized / "executors" / "synthetic.json")
        except Exception as exc:
            fail(f"{layout_path.relative_to(ROOT)}: built-in suite does not materialize cleanly: {exc}")


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
        if rel.suffix.lower() in BINARY_SUFFIXES:
            continue
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
            or rel == Path("HANDOFF_SOURCE_MANIFEST.json")
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

    # Executable skill examples must stay synchronized with the live core parser.
    # Inline command references are prose; shell-fenced examples are the checked contract.
    for skill_error in validate_skill_command_examples(ROOT / "skills"):
        fail(skill_error)
    for skill_error in validate_primary_skill_behavior(
        ROOT / "skills" / "agent-workflow" / "SKILL.md",
        ROOT / "evals" / "skills" / "agent-workflow.json",
    ):
        fail(skill_error)

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
        ROOT / "src/agent_workflow/cli_parser.py": 'from . import __version__',
        ROOT / "src/agent_workflow/doctor.py": '"version": __version__',
        ROOT / "docs/man/agent-workflow-workflow.1": f"agent-workflow {EXPECTED_VERSION}",
        ROOT / "docs/man/agent-workflow-index.1": f"agent-workflow {EXPECTED_VERSION}",
    }
    for path, needle in version_locations.items():
        if needle not in path.read_text(encoding="utf-8"):
            fail(f"{path.relative_to(ROOT)}: missing expected version marker {needle!r}")

    # Phase 0 agent-efficiency baseline is generated from the live parser/launch
    # context and guards against unmeasured agent-facing drift without adding a
    # separate unit-test surface.
    efficiency_baseline = ROOT / "release" / "agent-efficiency-baseline.json"
    if not efficiency_baseline.is_file():
        fail("release/agent-efficiency-baseline.json: Phase 0 efficiency baseline is missing")
    else:
        try:
            baseline = json.loads(efficiency_baseline.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            fail(f"release/agent-efficiency-baseline.json: invalid baseline: {exc}")
        else:
            if baseline.get("schema") != "agent-workflow/agent-efficiency-baseline/v1":
                fail("release/agent-efficiency-baseline.json: unexpected schema")
            if baseline.get("application_version") != "0.9.0":
                fail("release/agent-efficiency-baseline.json: must retain the 0.9.0 Phase 0 comparison version")
            roles = baseline.get("roles")
            if not isinstance(roles, dict) or set(roles) != {"implementation", "review", "orchestrator"}:
                fail("release/agent-efficiency-baseline.json: missing Phase 0 role measurements")
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "measure-agent-efficiency.py")],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        if result.returncode != 0:
            fail("scripts/measure-agent-efficiency.py: current measurement failed")
        else:
            try:
                current_efficiency = json.loads(result.stdout)
            except json.JSONDecodeError:
                fail("scripts/measure-agent-efficiency.py: current measurement is not valid JSON")
            else:
                targets = baseline.get("targets", {})
                current_roles = current_efficiency.get("roles", {})
                for role in ("implementation", "review", "orchestrator"):
                    role_value = current_roles.get(role, {})
                    command_limit = targets.get(f"{role}_role_commands_max")
                    card_limit = targets.get(f"{role}_role_card_bytes_max")
                    if not isinstance(command_limit, int) or not isinstance(card_limit, int):
                        fail(f"release/agent-efficiency-baseline.json: missing {role} surface targets")
                        continue
                    if role_value.get("command_count", command_limit + 1) > command_limit:
                        fail(
                            f"command profile {role}: exceeds {command_limit}-command agent-visible budget"
                        )
                    if role_value.get("command_card_bytes", card_limit + 1) > card_limit:
                        fail(
                            f"command profile {role}: exceeds {card_limit}-byte command-card budget"
                        )

    # Packaged scaffold assets are the single prompt-pack source. Repository mirror
    # trees and compatibility helper copies must not reappear.
    stale_prompt_pack_mirrors = [
        ROOT / "templates" / "prompt-pack",
        ROOT / "templates" / "TICKET_COMPLETION.md",
        ROOT / "templates" / "PHASE_GATE_REPORT.md",
        ROOT / "templates" / "source-baseline.example.json",
        ROOT / "scripts" / "archive-prompt-pack.sh",
        ROOT / "scripts" / "check-delegation.sh",
        ROOT / "scripts" / "create-ticket-worktree.sh",
        ROOT / "scripts" / "launch-delegation.sh",
        ROOT / "scripts" / "restart-delegation.sh",
        ROOT / "scripts" / "stop-delegation.sh",
        ROOT / "scripts" / "validate-prompt-pack.sh",
    ]
    for path in stale_prompt_pack_mirrors:
        if path.exists():
            fail(f"{path.relative_to(ROOT)}: obsolete prompt-pack source mirror must not exist")

    required_scaffold_assets = [
        ROOT / "src/agent_workflow/assets/prompt-pack-root/README.md",
        ROOT / "src/agent_workflow/assets/prompt-pack-root/templates/TICKET_COMPLETION.md",
        ROOT / "src/agent_workflow/assets/prompt-pack-root/templates/PHASE_GATE_REPORT.md",
        ROOT / "src/agent_workflow/assets/prompt-pack-root/templates/source-baseline.example.json",
        ROOT / "src/agent_workflow/assets/prompt-pack-root/scripts/validate-prompt-pack.sh",
        ROOT / "src/agent_workflow/assets/phase/README.md",
        ROOT / "src/agent_workflow/assets/phase/MASTER_IMPLEMENTATION_PROMPT.md",
        ROOT / "src/agent_workflow/assets/phase/tickets/P{{PHASE_NUMBER}}-00-baseline-and-preflight.md",
    ]
    for path in required_scaffold_assets:
        if not path.is_file():
            fail(f"{path.relative_to(ROOT)}: canonical packaged scaffold asset is missing")

    # Validate the product behavior rather than byte parity between duplicate trees.
    with tempfile.TemporaryDirectory(prefix="agent-workflow-scaffold-audit-") as tmp:
        destination = Path(tmp) / "audit-pack"
        try:
            scaffold_pack(destination, 2, "audit-pack")
            report = validate_pack(destination)
            if not report.ok:
                for error in report.errors:
                    fail(f"generated prompt-pack scaffold: {error}")
            for script in sorted((destination / "scripts").glob("*.sh")):
                if not script.stat().st_mode & stat.S_IXUSR:
                    fail(f"generated prompt-pack scaffold: {script.name} is not executable")
        except Exception as exc:
            fail(f"generated prompt-pack scaffold failed: {exc}")

    # Shell entrypoints must be executable.
    for path in [
        ROOT / "install.sh",
        ROOT / "uninstall.sh",
        ROOT / "bin/agent-workflow",
        *sorted((ROOT / "scripts").glob("*.sh")),
        ROOT / "scripts/hooks/agent-workflow-run-reminder",
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


    # Canonical benchmark package parity and backlog/prompt-pack ownership.
    _audit_builtin_benchmark_layouts()
    _audit_backlog_and_prompt_pack_ownership()

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("release assets: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
