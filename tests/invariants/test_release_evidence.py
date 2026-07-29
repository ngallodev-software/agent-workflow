from __future__ import annotations

import json
import subprocess
import tomllib
from copy import deepcopy
from pathlib import Path

import jsonschema

from agent_workflow.release_evidence import collect_release_evidence
from tests.conftest import REPO_ROOT


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path


def _junit(path: Path, *, failures: int = 0, errors: int = 0) -> Path:
    path.write_text(
        f'<testsuite tests="2" failures="{failures}" errors="{errors}" skipped="1"></testsuite>',
        encoding="utf-8",
    )
    return path


def test_mcp_is_a_core_host_dependency() -> None:
    metadata = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "mcp==1.28.1" in metadata["project"]["dependencies"]
    lock = _load(REPO_ROOT / "release" / "dependency-lock.json")
    mcp = next(package for package in lock["packages"] if package["name"] == "mcp")
    assert set(mcp["groups"]) == {"mcp", "runtime"}


def test_release_evidence_preserves_open_governance_blockers_and_writes_durable_artifacts(
    tmp_path: Path,
) -> None:
    output = tmp_path / "evidence"
    summary = collect_release_evidence(
        root=REPO_ROOT,
        output_dir=output,
        policy_path=REPO_ROOT / "release" / "release-policy.json",
        lock_path=REPO_ROOT / "release" / "dependency-lock.json",
        test_results=_junit(tmp_path / "pytest.xml"),
    )

    assert summary["status"] == "blocked"
    checks = {item["id"]: item for item in summary["checks"]}
    assert checks["license-metadata"]["status"] == "blocked"
    assert checks["security-channel"]["status"] == "blocked"
    assert checks["compatibility-matrix"]["status"] == "blocked"
    assert checks["dependency-lock"]["status"] == "pass"
    assert checks["structured-tests"]["status"] == "pass"

    for filename, schema_name in (
        ("release-evidence.json", "release-evidence.schema.json"),
        ("build-provenance.json", "build-provenance.schema.json"),
    ):
        value = _load(output / filename)
        schema = _load(REPO_ROOT / "schemas" / schema_name)
        jsonschema.Draft202012Validator(schema).validate(value)

    sbom = _load(output / "sbom.cdx.json")
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert {component["name"] for component in sbom["components"]} >= {
        "jsonschema",
        "pytest",
        "mcp",
    }
    provenance = _load(output / "build-provenance.json")
    assert len(provenance["source"]["tree_sha256"]) == 64
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    assert provenance["source"]["git_revision"] == revision
    assert isinstance(provenance["source"]["git_dirty"], bool)


def test_dependency_lock_drift_and_failed_junit_are_machine_failures(tmp_path: Path) -> None:
    lock = _load(REPO_ROOT / "release" / "dependency-lock.json")
    lock["packages"] = [item for item in lock["packages"] if item["name"] != "jsonschema"]
    summary = collect_release_evidence(
        root=REPO_ROOT,
        output_dir=tmp_path / "evidence",
        policy_path=REPO_ROOT / "release" / "release-policy.json",
        lock_path=_write(tmp_path / "dependency-lock.json", lock),
        test_results=_junit(tmp_path / "pytest.xml", failures=1),
    )
    checks = {item["id"]: item for item in summary["checks"]}
    assert summary["status"] == "technical_failure"
    assert checks["dependency-lock"]["status"] == "fail"
    assert "jsonschema" in checks["dependency-lock"]["detail"]
    assert checks["structured-tests"]["status"] == "fail"


def test_configured_release_claims_fail_closed_without_matching_repository_evidence(
    tmp_path: Path,
) -> None:
    policy = deepcopy(_load(REPO_ROOT / "release" / "release-policy.json"))
    policy["license"] = {
        "status": "configured",
        "backlog_id": "REL-001",
        "spdx_expression": "Apache-2.0",
        "file": "LICENSE",
        "distribution_policy": "Public distribution under Apache-2.0.",
    }
    policy["security_channel"] = {
        "status": "configured",
        "backlog_id": "REL-002",
        "contact": "security@example.invalid",
        "response_policy": "Acknowledge within two business days.",
    }
    policy["compatibility"]["status"] = "supported"
    policy["compatibility"]["combinations"] = [
        {**item, "status": "verified"} for item in policy["compatibility"]["combinations"]
    ]
    summary = collect_release_evidence(
        root=REPO_ROOT,
        output_dir=tmp_path / "evidence",
        policy_path=_write(tmp_path / "release-policy.json", policy),
        lock_path=REPO_ROOT / "release" / "dependency-lock.json",
        test_results=_junit(tmp_path / "pytest.xml"),
    )
    checks = {item["id"]: item for item in summary["checks"]}
    assert summary["status"] == "technical_failure"
    assert checks["license-metadata"]["status"] == "fail"
    assert checks["security-channel"]["status"] == "fail"
    assert checks["compatibility-matrix"]["status"] == "fail"


def test_release_evidence_cli_can_enforce_known_blockers(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "python3",
            "scripts/release-evidence.py",
            "--output-dir",
            str(tmp_path / "evidence"),
            "--test-results",
            str(_junit(tmp_path / "pytest.xml")),
            "--enforce-blockers",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert _load(tmp_path / "evidence" / "release-evidence.json")["status"] == "blocked"


def test_supported_compatibility_claim_rejects_unbound_or_tampered_evidence(
    tmp_path: Path,
) -> None:
    policy = deepcopy(_load(REPO_ROOT / "release" / "release-policy.json"))
    policy["compatibility"]["status"] = "supported"
    policy["compatibility"]["combinations"] = [
        {**item, "status": "verified"} for item in policy["compatibility"]["combinations"]
    ]
    policy["compatibility"]["evidence"] = [
        {
            "combination_id": item["id"],
            "path": "README.md",
            "sha256": "0" * 64,
        }
        for item in policy["compatibility"]["combinations"]
    ]
    summary = collect_release_evidence(
        root=REPO_ROOT,
        output_dir=tmp_path / "evidence",
        policy_path=_write(tmp_path / "release-policy.json", policy),
        lock_path=REPO_ROOT / "release" / "dependency-lock.json",
        test_results=_junit(tmp_path / "pytest.xml"),
    )
    check = next(item for item in summary["checks"] if item["id"] == "compatibility-matrix")
    assert summary["status"] == "technical_failure"
    assert check["status"] == "fail"
    assert "digest mismatch" in check["detail"]


def test_enforced_cli_keeps_technical_failures_distinct_from_open_blockers(
    tmp_path: Path,
) -> None:
    lock = _load(REPO_ROOT / "release" / "dependency-lock.json")
    lock["packages"] = [item for item in lock["packages"] if item["name"] != "jsonschema"]
    result = subprocess.run(
        [
            "python3",
            "scripts/release-evidence.py",
            "--output-dir",
            str(tmp_path / "evidence"),
            "--dependency-lock",
            str(_write(tmp_path / "dependency-lock.json", lock)),
            "--test-results",
            str(_junit(tmp_path / "pytest.xml")),
            "--enforce-blockers",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert _load(tmp_path / "evidence" / "release-evidence.json")["status"] == "technical_failure"


def test_junit_evidence_rejects_unknown_root_or_zero_test_success(tmp_path: Path) -> None:
    for name, xml in (
        ("unknown.xml", "<result/>"),
        ("empty.xml", '<testsuite tests="0" failures="0" errors="0" skipped="0"/>'),
    ):
        junit = tmp_path / name
        junit.write_text(xml, encoding="utf-8")
        summary = collect_release_evidence(
            root=REPO_ROOT,
            output_dir=tmp_path / f"evidence-{name}",
            policy_path=REPO_ROOT / "release" / "release-policy.json",
            lock_path=REPO_ROOT / "release" / "dependency-lock.json",
            test_results=junit,
        )
        check = next(item for item in summary["checks"] if item["id"] == "structured-tests")
        assert summary["status"] == "technical_failure"
        assert check["status"] == "fail"
