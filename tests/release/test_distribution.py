from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
import zipfile
from copy import deepcopy
from pathlib import Path

import jsonschema

from agent_workflow.release_evidence import collect_release_evidence
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




def test_test_authority_audit_blocks_silent_suite_growth(tmp_path: Path) -> None:
    policy = json.loads((REPO_ROOT / "tests" / "test-authority.json").read_text(encoding="utf-8"))
    blocked_policy = tmp_path / "blocked-test-authority.json"
    policy["layers"]["invariants"]["max_files"] = 0
    blocked_policy.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

    cases = [
        ([sys.executable, "scripts/audit-test-suite.py", "--skip-collection"], 0, "test authority audit: passed"),
        (
            [
                sys.executable,
                "scripts/audit-test-suite.py",
                "--skip-collection",
                "--policy",
                str(blocked_policy),
            ],
            1,
            "invariants files grew",
        ),
    ]
    for command, expected_code, expected_text in cases:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
        assert result.returncode == expected_code, result.stdout + result.stderr
        assert expected_text in result.stdout + result.stderr

    testing = (REPO_ROOT / "docs" / "TESTING.md").read_text(encoding="utf-8")
    protocol = (REPO_ROOT / "docs" / "references" / "EXECUTION_PROTOCOL.md").read_text(encoding="utf-8")
    preflight = (REPO_ROOT / "docs" / "references" / "WORKTREE_PREFLIGHT.md").read_text(encoding="utf-8")
    assert "tests/test-authority.json" in testing
    assert "scripts/audit-test-suite.py" in testing
    assert "test-authority" in protocol
    assert "persistence=false" in preflight
    assert "$XDG_CACHE_HOME/agent-workflow/codebase-memory/<worktree-id>/" in preflight
    assert "git status --porcelain=v2 -z" in preflight
    assert "256 MiB" in preflight


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


def test_built_wheel_excludes_repository_only_ci_assets(tmp_path: Path) -> None:
    output = tmp_path / "dist"
    output.mkdir()
    result = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--no-build-isolation", "--wheel-dir", str(output)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheels = sorted(output.glob("agent_workflow-*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
    forbidden = ("Jenkinsfile", "jenkins-local-job", ".github/workflows")
    assert not any(any(token in name for token in forbidden) for name in names)
    assert not any("__pycache__/" in name or name.endswith(".pyc") for name in names)


def test_optional_mcp_profile_rejects_missing_pinned_sdk_before_client_registration(
    tmp_path: Path,
) -> None:
    fake_python = tmp_path / "python-without-mcp"
    fake_python.write_text(
        f"#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then exit 1; fi\n"
        f"exec {sys.executable!r} \"$@\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    home = tmp_path / "home"
    env = {
        **os.environ,
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
    }
    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "install-source.sh"),
            "--no-deps",
            "--no-skills",
            "--no-hooks",
            "--extras",
            "mcp",
            "--python",
            str(fake_python),
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode != 0
    assert "MCP support requires mcp==1.28.1" in result.stderr
    assert not (home / ".codex" / "config.toml").exists()
    assert not (home / ".claude.json").exists()



def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path


def _write_junit(path: Path, *, failures: int = 0, errors: int = 0) -> Path:
    path.write_text(
        f'<testsuite tests="2" failures="{failures}" errors="{errors}" skipped="1"></testsuite>',
        encoding="utf-8",
    )
    return path


def test_release_evidence_contract_and_cli_outcomes_are_one_release_gate(tmp_path: Path) -> None:
    metadata = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "mcp==1.28.1" not in metadata["project"]["dependencies"]
    assert metadata["project"]["optional-dependencies"]["mcp"] == ["mcp==1.28.1"]
    assert "PyYAML>=6.0.3,<7" in metadata["project"]["dependencies"]
    lock = _load_json(REPO_ROOT / "release" / "dependency-lock.json")
    mcp = next(package for package in lock["packages"] if package["name"] == "mcp")
    pyyaml = next(package for package in lock["packages"] if package["name"] == "PyYAML")
    assert set(mcp["groups"]) == {"mcp"}
    assert set(pyyaml["groups"]) == {"runtime"}

    happy_output = tmp_path / "evidence-happy"
    summary = collect_release_evidence(
        root=REPO_ROOT,
        output_dir=happy_output,
        policy_path=REPO_ROOT / "release" / "release-policy.json",
        lock_path=REPO_ROOT / "release" / "dependency-lock.json",
        test_results=_write_junit(tmp_path / "pytest-happy.xml"),
    )
    assert summary["status"] == "blocked"
    checks = {item["id"]: item for item in summary["checks"]}
    assert checks["license-metadata"]["status"] == "pass"
    assert checks["security-channel"]["status"] == "blocked"
    assert checks["compatibility-matrix"]["status"] == "blocked"
    assert checks["dependency-lock"]["status"] == "pass"
    assert checks["structured-tests"]["status"] == "pass"
    for filename, schema_name in (
        ("release-evidence.json", "release-evidence.schema.json"),
        ("build-provenance.json", "build-provenance.schema.json"),
    ):
        jsonschema.Draft202012Validator(
            _load_json(REPO_ROOT / "schemas" / schema_name)
        ).validate(_load_json(happy_output / filename))
    sbom = _load_json(happy_output / "sbom.cdx.json")
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert {component["name"] for component in sbom["components"]} >= {
        "jsonschema",
        "pytest",
        "mcp",
    }
    provenance = _load_json(happy_output / "build-provenance.json")
    assert len(provenance["source"]["tree_sha256"]) == 64
    if (REPO_ROOT / ".git").exists():
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        assert provenance["source"]["git_revision"] == revision
        assert isinstance(provenance["source"]["git_dirty"], bool)
    else:
        assert provenance["source"]["git_revision"] is None
        assert provenance["source"]["git_dirty"] is None

    drifted_lock = deepcopy(lock)
    drifted_lock["packages"] = [
        item for item in drifted_lock["packages"] if item["name"] != "jsonschema"
    ]
    failed = collect_release_evidence(
        root=REPO_ROOT,
        output_dir=tmp_path / "evidence-failed",
        policy_path=REPO_ROOT / "release" / "release-policy.json",
        lock_path=_write_json(tmp_path / "dependency-lock-failed.json", drifted_lock),
        test_results=_write_junit(tmp_path / "pytest-failed.xml", failures=1),
    )
    failed_checks = {item["id"]: item for item in failed["checks"]}
    assert failed["status"] == "technical_failure"
    assert failed_checks["dependency-lock"]["status"] == "fail"
    assert "jsonschema" in failed_checks["dependency-lock"]["detail"]
    assert failed_checks["structured-tests"]["status"] == "fail"

    configured = deepcopy(_load_json(REPO_ROOT / "release" / "release-policy.json"))
    configured["license"] = {
        "status": "configured",
        "backlog_id": "REL-001",
        "spdx_expression": "MIT",
        "file": "MISSING-LICENSE",
        "distribution_policy": "Public distribution under MIT.",
    }
    configured["security_channel"] = {
        "status": "configured",
        "backlog_id": "REL-002",
        "contact": "security@example.invalid",
        "response_policy": "Acknowledge within two business days.",
    }
    configured["compatibility"]["status"] = "supported"
    configured["compatibility"]["combinations"] = [
        {**item, "status": "verified"}
        for item in configured["compatibility"]["combinations"]
    ]
    configured_result = collect_release_evidence(
        root=REPO_ROOT,
        output_dir=tmp_path / "evidence-configured",
        policy_path=_write_json(tmp_path / "release-policy-configured.json", configured),
        lock_path=REPO_ROOT / "release" / "dependency-lock.json",
        test_results=_write_junit(tmp_path / "pytest-configured.xml"),
    )
    configured_checks = {item["id"]: item for item in configured_result["checks"]}
    assert configured_result["status"] == "technical_failure"
    assert configured_checks["license-metadata"]["status"] == "fail"
    assert configured_checks["security-channel"]["status"] == "fail"
    assert configured_checks["compatibility-matrix"]["status"] == "fail"

    tampered = deepcopy(_load_json(REPO_ROOT / "release" / "release-policy.json"))
    tampered["compatibility"]["status"] = "supported"
    tampered["compatibility"]["combinations"] = [
        {**item, "status": "verified"}
        for item in tampered["compatibility"]["combinations"]
    ]
    tampered["compatibility"]["evidence"] = [
        {"combination_id": item["id"], "path": "README.md", "sha256": "0" * 64}
        for item in tampered["compatibility"]["combinations"]
    ]
    tampered_result = collect_release_evidence(
        root=REPO_ROOT,
        output_dir=tmp_path / "evidence-tampered",
        policy_path=_write_json(tmp_path / "release-policy-tampered.json", tampered),
        lock_path=REPO_ROOT / "release" / "dependency-lock.json",
        test_results=_write_junit(tmp_path / "pytest-tampered.xml"),
    )
    compatibility = next(
        item for item in tampered_result["checks"] if item["id"] == "compatibility-matrix"
    )
    assert tampered_result["status"] == "technical_failure"
    assert compatibility["status"] == "fail"
    assert "digest mismatch" in compatibility["detail"]

    for name, xml in (
        ("unknown.xml", "<result/>"),
        ("empty.xml", '<testsuite tests="0" failures="0" errors="0" skipped="0"/>'),
    ):
        junit = tmp_path / name
        junit.write_text(xml, encoding="utf-8")
        invalid = collect_release_evidence(
            root=REPO_ROOT,
            output_dir=tmp_path / f"evidence-{name}",
            policy_path=REPO_ROOT / "release" / "release-policy.json",
            lock_path=REPO_ROOT / "release" / "dependency-lock.json",
            test_results=junit,
        )
        structured = next(
            item for item in invalid["checks"] if item["id"] == "structured-tests"
        )
        assert invalid["status"] == "technical_failure"
        assert structured["status"] == "fail"

    blocked_cli = subprocess.run(
        [
            sys.executable,
            "scripts/release-evidence.py",
            "--output-dir",
            str(tmp_path / "evidence-cli-blocked"),
            "--test-results",
            str(_write_junit(tmp_path / "pytest-cli-blocked.xml")),
            "--enforce-blockers",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert blocked_cli.returncode == 3, blocked_cli.stdout + blocked_cli.stderr
    assert _load_json(tmp_path / "evidence-cli-blocked" / "release-evidence.json")["status"] == "blocked"

    technical_cli = subprocess.run(
        [
            sys.executable,
            "scripts/release-evidence.py",
            "--output-dir",
            str(tmp_path / "evidence-cli-technical"),
            "--dependency-lock",
            str(_write_json(tmp_path / "dependency-lock-cli.json", drifted_lock)),
            "--test-results",
            str(_write_junit(tmp_path / "pytest-cli-technical.xml")),
            "--enforce-blockers",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert technical_cli.returncode == 2, technical_cli.stdout + technical_cli.stderr
    assert _load_json(tmp_path / "evidence-cli-technical" / "release-evidence.json")["status"] == "technical_failure"
