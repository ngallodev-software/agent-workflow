from __future__ import annotations

import json
import re
import subprocess

import jsonschema

from tests.conftest import InstalledProduct, REPO_ROOT


def test_release_asset_audit_is_the_single_static_repository_gate() -> None:
    result = subprocess.run(
        ["python3", "scripts/audit-release-assets.py"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_all_published_json_schemas_are_valid_draft_2020_12() -> None:
    schemas = sorted((REPO_ROOT / "schemas").glob("*.json"))
    assert schemas
    for path in schemas:
        jsonschema.Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_shell_entrypoints_and_installer_are_syntax_valid() -> None:
    paths = [REPO_ROOT / "install.sh", REPO_ROOT / "uninstall.sh", REPO_ROOT / "bin" / "agent-workflow"]
    paths.extend(sorted((REPO_ROOT / "scripts").glob("*.sh")))
    for path in paths:
        subprocess.run(["bash", "-n", str(path)], check=True)


def test_documented_commands_match_the_installed_public_surface(
    installed_product: InstalledProduct, product_env: dict[str, str]
) -> None:
    help_text = installed_product.run("--help", env=product_env, check=True).stdout
    command_group = re.search(r"\{([a-z][a-z0-9,-]+)\}", help_text)
    assert command_group is not None, help_text
    public_commands = set(command_group.group(1).split(","))
    assert {"launch", "status", "workflow", "pack", "eval"} <= public_commands

    canonical_docs = [REPO_ROOT / "README.md", *sorted((REPO_ROOT / "docs").glob("*.md"))]
    documented: set[str] = set()
    for path in canonical_docs:
        text = path.read_text(encoding="utf-8")
        fence_languages = "bash|sh|shell|text" if path.name == "COMMAND_REFERENCE.md" else "bash|sh|shell"
        blocks = re.findall(rf"```(?:{fence_languages})\n(.*?)```", text, flags=re.DOTALL)
        for block in blocks:
            for match in re.finditer(
                r"^\s*agent-workflow\s+([a-z][a-z0-9-]+)(?:\s|$)",
                block,
                flags=re.MULTILINE,
            ):
                documented.add(match.group(1))
    assert documented <= public_commands, f"unknown documented commands: {sorted(documented - public_commands)}"

    command_reference = (REPO_ROOT / "docs" / "COMMAND_REFERENCE.md").read_text(encoding="utf-8")
    assert "agent-workflow eval compare BASELINE.json CANDIDATE.json --output PATH" in command_reference
