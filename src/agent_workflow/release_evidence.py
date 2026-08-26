from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import tomllib
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import jsonschema

from .util import atomic_write_canonical_json, sha256_bytes, sha256_file


SCHEMA = "agent-workflow/release-evidence/v1"
PROVENANCE_SCHEMA = "agent-workflow/build-provenance/v1"

_EXCLUDED_DIRS = {
    ".agent-workflow-handoff",
    ".claude",
    ".claude-flow",
    ".codebase-memory",
    ".delegations",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".swarm",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "testing-output",
}
_EXCLUDED_SUFFIXES = {".pyc", ".sha256", ".zst"}
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


@dataclass(frozen=True)
class FileEvidence:
    path: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _display_path(path: Path, root: Path, output_dir: Path) -> str:
    for parent in (root, output_dir):
        try:
            return path.resolve().relative_to(parent.resolve()).as_posix()
        except ValueError:
            continue
    return path.name


def _file_evidence(path: Path, root: Path, output_dir: Path) -> FileEvidence:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"evidence path must be a regular file: {path}")
    return FileEvidence(
        path=_display_path(path, root, output_dir),
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
    )


def _load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"JSON input must be a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON input must be an object: {path}")
    return value


def _validate(root: Path, value: dict[str, Any], schema_name: str) -> None:
    schema_path = root / "schemas" / schema_name
    schema = _load_json(schema_path)
    jsonschema.Draft202012Validator(schema).validate(value)


def _requirement_name(requirement: str) -> str:
    match = _NAME_RE.match(requirement.strip())
    if match is None:
        raise ValueError(f"unsupported dependency requirement: {requirement!r}")
    return match.group(0).lower().replace("_", "-")


def _pyproject_requirements(root: Path) -> dict[str, dict[str, set[str]]]:
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    groups: dict[str, list[str]] = {
        "build": list(metadata.get("build-system", {}).get("requires", [])),
        "runtime": list(metadata.get("project", {}).get("dependencies", [])),
    }
    for group, requirements in metadata.get("project", {}).get("optional-dependencies", {}).items():
        groups[str(group)] = list(requirements)

    expected: dict[str, dict[str, set[str]]] = {}
    for group, requirements in groups.items():
        for requirement in requirements:
            name = _requirement_name(requirement)
            record = expected.setdefault(name, {"groups": set(), "requirements": set()})
            record["groups"].add(group)
            record["requirements"].add(requirement)
    return expected


def validate_dependency_lock(root: Path, lock: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = _pyproject_requirements(root)
    actual: dict[str, dict[str, Any]] = {}
    for package in lock.get("packages", []):
        name = str(package.get("name", "")).lower().replace("_", "-")
        if name in actual:
            errors.append(f"duplicate dependency lock entry: {name}")
            continue
        actual[name] = package

    for name in sorted(expected):
        if name not in actual:
            errors.append(f"dependency lock missing direct requirement: {name}")
            continue
        package = actual[name]
        groups = set(package.get("groups", []))
        requirements = set(package.get("source_requirements", []))
        if groups != expected[name]["groups"]:
            errors.append(
                f"dependency lock groups differ for {name}: expected {sorted(expected[name]['groups'])}, "
                f"found {sorted(groups)}"
            )
        if requirements != expected[name]["requirements"]:
            errors.append(
                f"dependency lock source requirements differ for {name}: "
                f"expected {sorted(expected[name]['requirements'])}, found {sorted(requirements)}"
            )
        version = str(package.get("version", ""))
        if not version or any(token in version for token in "<>=~,; "):
            errors.append(f"dependency lock version is not exact for {name}: {version!r}")

    extras = sorted(set(actual) - set(expected))
    if extras:
        errors.append(f"dependency lock contains undeclared direct requirements: {extras}")
    return errors


def _release_inventory(root: Path, output_dir: Path) -> Iterable[Path]:
    output_resolved = output_dir.resolve()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in _EXCLUDED_DIRS or part.endswith(".egg-info") for part in rel.parts[:-1]):
            continue
        resolved = path.resolve()
        try:
            resolved.relative_to(output_resolved)
            continue
        except ValueError:
            pass
        if path.is_symlink():
            raise ValueError(f"release source inventory contains a symlink: {rel.as_posix()}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"release source inventory contains an irregular entry: {rel.as_posix()}")
        if rel.suffix in _EXCLUDED_SUFFIXES:
            continue
        yield path


def source_tree_sha256(root: Path, output_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in _release_inventory(root, output_dir):
        rel = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(rel).to_bytes(8, "big"))
        digest.update(rel)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _git_source(root: Path) -> tuple[str | None, bool | None]:
    if not (root / ".git").exists():
        return None, None
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, text=True, capture_output=True, check=False
    )
    if revision.returncode != 0 or status.returncode != 0:
        return None, None
    return revision.stdout.strip(), bool(status.stdout.strip())


def _junit_check(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "id": "structured-tests",
            "status": "not_run",
            "detail": "No JUnit XML test result was supplied.",
            "backlog_id": "REL-005",
        }
    try:
        root = ET.parse(path).getroot()
        if root.tag == "testsuite":
            suites = [root]
        elif root.tag == "testsuites":
            suites = list(root.findall("testsuite"))
        else:
            raise ValueError(f"unsupported JUnit root element: {root.tag}")
        if not suites:
            raise ValueError("JUnit XML contains no test suites")
        totals = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
        for suite in suites:
            for key in totals:
                totals[key] += int(suite.attrib.get(key, "0"))
        if totals["tests"] <= 0:
            raise ValueError("JUnit XML records no tests")
    except (ET.ParseError, ValueError) as exc:
        return {
            "id": "structured-tests",
            "status": "fail",
            "detail": f"JUnit XML is invalid: {exc}",
            "backlog_id": "REL-005",
        }
    status = "pass" if totals["failures"] == 0 and totals["errors"] == 0 else "fail"
    detail = (
        f"JUnit XML records {totals['tests']} tests, {totals['failures']} failures, "
        f"{totals['errors']} errors, and {totals['skipped']} skipped."
    )
    return {"id": "structured-tests", "status": status, "detail": detail, "backlog_id": "REL-005"}


def _repo_regular_file(root: Path, relative: str) -> Path | None:
    candidate = root / relative
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    if candidate.is_symlink() or not candidate.is_file():
        return None
    return candidate


def _compatibility_evidence_errors(root: Path, compatibility: dict[str, Any]) -> list[str]:
    combination_ids = {item["id"] for item in compatibility["combinations"]}
    seen: set[str] = set()
    errors: list[str] = []
    for item in compatibility.get("evidence", []):
        combination_id = item["combination_id"]
        if combination_id not in combination_ids:
            errors.append(f"unknown compatibility combination evidence: {combination_id}")
            continue
        if combination_id in seen:
            errors.append(f"duplicate compatibility evidence: {combination_id}")
            continue
        seen.add(combination_id)
        path = _repo_regular_file(root, item["path"])
        if path is None:
            errors.append(f"compatibility evidence is missing or outside the repository: {item['path']}")
        elif sha256_file(path) != item["sha256"]:
            errors.append(f"compatibility evidence digest mismatch: {item['path']}")
    return errors


def _policy_checks(root: Path, policy: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    license_policy = policy["license"]
    if license_policy["status"] != "configured":
        checks.append(
            {
                "id": "license-metadata",
                "status": "blocked",
                "detail": "No maintainer-approved license and distribution policy are configured.",
                "backlog_id": "REL-001",
            }
        )
    else:
        license_file = _repo_regular_file(root, str(license_policy.get("file", "")))
        project_license = pyproject.get("project", {}).get("license")
        configured_spdx = license_policy.get("spdx_expression")
        if license_file is None:
            status, detail = "fail", "Configured license file is missing or is not a regular file."
        elif not configured_spdx or project_license != configured_spdx:
            status, detail = "fail", "Release policy and pyproject license metadata do not match."
        elif not license_policy.get("distribution_policy"):
            status, detail = "fail", "Configured license is missing a distribution policy."
        else:
            status, detail = "pass", "License file, SPDX metadata, and distribution policy agree."
        checks.append(
            {"id": "license-metadata", "status": status, "detail": detail, "backlog_id": "REL-001"}
        )

    security_policy = policy["security_channel"]
    if security_policy["status"] != "configured":
        checks.append(
            {
                "id": "security-channel",
                "status": "blocked",
                "detail": "No monitored private vulnerability-reporting channel is configured.",
                "backlog_id": "REL-002",
            }
        )
    else:
        contact = str(security_policy.get("contact") or "").strip()
        security_text = (root / "SECURITY.md").read_text(encoding="utf-8")
        placeholder = not contact or any(token in contact.lower() for token in ("example.", "placeholder", "todo"))
        if placeholder:
            status, detail = "fail", "Configured security contact is empty or a placeholder."
        elif contact not in security_text:
            status, detail = "fail", "Configured security contact is not published in SECURITY.md."
        elif not security_policy.get("response_policy"):
            status, detail = "fail", "Configured security channel is missing a response policy."
        else:
            status, detail = "pass", "A non-placeholder monitored channel and response policy are configured."
        checks.append(
            {"id": "security-channel", "status": status, "detail": detail, "backlog_id": "REL-002"}
        )

    compatibility = policy["compatibility"]
    verified = [item for item in compatibility["combinations"] if item["status"] == "verified"]
    evidence = compatibility.get("evidence", [])
    if compatibility["status"] != "supported":
        checks.append(
            {
                "id": "compatibility-matrix",
                "status": "blocked",
                "detail": (
                    f"Candidate matrix {compatibility['matrix_id']} is declared, but clean-host support "
                    "evidence has not been accepted."
                ),
                "backlog_id": "REL-003",
            }
        )
    elif len(verified) != len(compatibility["combinations"]):
        checks.append(
            {
                "id": "compatibility-matrix",
                "status": "fail",
                "detail": "Supported compatibility policy contains unverified combinations.",
                "backlog_id": "REL-003",
            }
        )
    elif compatibility.get("evidence_required", True) and len(evidence) < len(verified):
        checks.append(
            {
                "id": "compatibility-matrix",
                "status": "fail",
                "detail": "Supported compatibility policy lacks one evidence reference per verified combination.",
                "backlog_id": "REL-003",
            }
        )
    else:
        evidence_errors = _compatibility_evidence_errors(root, compatibility)
        checks.append(
            {
                "id": "compatibility-matrix",
                "status": "fail" if evidence_errors else "pass",
                "detail": (
                    "; ".join(evidence_errors)
                    if evidence_errors
                    else f"Compatibility matrix {compatibility['matrix_id']} is supported and evidence-bound."
                ),
                "backlog_id": "REL-003",
            }
        )
    return checks


def _cyclonedx_sbom(project: str, version: str, lock: dict[str, Any], tree_sha256: str) -> dict[str, Any]:
    project_ref = f"pkg:pypi/{project}@{version}"
    components: list[dict[str, Any]] = []
    dependency_refs: list[str] = []
    for package in sorted(lock["packages"], key=lambda item: str(item["name"]).lower()):
        reference = f"pkg:pypi/{package['name']}@{package['version']}"
        dependency_refs.append(reference)
        components.append(
            {
                "type": "library",
                "bom-ref": reference,
                "name": package["name"],
                "version": package["version"],
                "purl": reference,
                "scope": "required" if "runtime" in package["groups"] else "optional",
                "properties": [
                    {"name": "agent-workflow:dependency-groups", "value": ",".join(sorted(package["groups"]))},
                    {
                        "name": "agent-workflow:source-requirements",
                        "value": " | ".join(sorted(package["source_requirements"])),
                    },
                ],
            }
        )
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'agent-workflow:{tree_sha256}')}",
        "version": 1,
        "metadata": {
            "timestamp": _utc_now(),
            "tools": {"components": [{"type": "application", "name": "agent-workflow-release-evidence", "version": version}]},
            "component": {
                "type": "application",
                "bom-ref": project_ref,
                "name": project,
                "version": version,
                "purl": project_ref,
                "hashes": [{"alg": "SHA-256", "content": tree_sha256}],
            },
        },
        "components": components,
        "dependencies": [{"ref": project_ref, "dependsOn": dependency_refs}],
    }


def collect_release_evidence(
    *,
    root: Path,
    output_dir: Path,
    policy_path: Path,
    lock_path: Path,
    test_results: Path | None = None,
    artifacts: Iterable[Path] = (),
    technical_exit_code: int = 0,
) -> dict[str, Any]:
    root = root.resolve()
    output_dir = output_dir.resolve()
    policy_path = policy_path.resolve()
    lock_path = lock_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    policy = _load_json(policy_path)
    lock = _load_json(lock_path)
    _validate(root, policy, "release-policy.schema.json")
    _validate(root, lock, "dependency-lock.schema.json")

    expected_version = (root / "VERSION").read_text(encoding="utf-8").strip()
    for label, value in (("release policy", policy), ("dependency lock", lock)):
        if value["project"] != "agent-workflow" or value["version"] != expected_version:
            raise ValueError(f"{label} project/version does not match VERSION")

    checks = _policy_checks(root, policy)
    lock_errors = validate_dependency_lock(root, lock)
    checks.append(
        {
            "id": "dependency-lock",
            "status": "fail" if lock_errors else "pass",
            "detail": "; ".join(lock_errors) if lock_errors else "Every direct pyproject dependency has one exact synchronized lock entry.",
            "backlog_id": "REL-005",
        }
    )

    checks.append(_junit_check(test_results))
    checks.append(
        {
            "id": "technical-release-check",
            "status": "pass" if technical_exit_code == 0 else "fail",
            "detail": (
                "The technical release-check command completed successfully."
                if technical_exit_code == 0
                else f"The technical release-check command exited with code {technical_exit_code}."
            ),
            "backlog_id": "REL-005",
        }
    )

    tree_digest = source_tree_sha256(root, output_dir)
    sbom = _cyclonedx_sbom(policy["project"], expected_version, lock, tree_digest)
    sbom_path = output_dir / "sbom.cdx.json"
    atomic_write_canonical_json(sbom_path, sbom, mode=0o600, ensure_ascii=False)

    policy_evidence = _file_evidence(policy_path, root, output_dir)
    lock_evidence = _file_evidence(lock_path, root, output_dir)
    sbom_evidence = _file_evidence(sbom_path, root, output_dir)
    test_evidence = (
        _file_evidence(test_results.resolve(), root, output_dir)
        if test_results is not None and test_results.exists()
        else None
    )
    artifact_evidence = [_file_evidence(path.resolve(), root, output_dir) for path in artifacts]
    git_revision, git_dirty = _git_source(root)
    materials = [policy_evidence, lock_evidence, sbom_evidence]
    if test_evidence is not None:
        materials.append(test_evidence)
    provenance = {
        "schema": PROVENANCE_SCHEMA,
        "project": policy["project"],
        "version": expected_version,
        "generated_at": _utc_now(),
        "source": {
            "tree_sha256": tree_digest,
            "git_revision": git_revision,
            "git_dirty": git_dirty,
        },
        "builder": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "materials": [item.to_dict() for item in materials],
        "artifacts": [item.to_dict() for item in artifact_evidence],
    }
    _validate(root, provenance, "build-provenance.schema.json")
    provenance_path = output_dir / "build-provenance.json"
    atomic_write_canonical_json(provenance_path, provenance, mode=0o600, ensure_ascii=False)
    provenance_evidence = _file_evidence(provenance_path, root, output_dir)

    if technical_exit_code != 0 or any(check["status"] == "fail" for check in checks):
        status = "technical_failure"
    elif any(check["status"] in {"blocked", "not_run"} for check in checks):
        status = "blocked"
    else:
        status = "ready"

    summary = {
        "schema": SCHEMA,
        "project": policy["project"],
        "version": expected_version,
        "status": status,
        "generated_at": _utc_now(),
        "technical_exit_code": technical_exit_code,
        "checks": checks,
        "evidence": {
            "policy": policy_evidence.to_dict(),
            "dependency_lock": lock_evidence.to_dict(),
            "sbom": sbom_evidence.to_dict(),
            "provenance": provenance_evidence.to_dict(),
            "test_results": test_evidence.to_dict() if test_evidence is not None else None,
        },
    }
    _validate(root, summary, "release-evidence.schema.json")
    atomic_write_canonical_json(output_dir / "release-evidence.json", summary, mode=0o600, ensure_ascii=False)
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate durable release blocker and provenance evidence.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--dependency-lock", type=Path)
    parser.add_argument("--test-results", type=Path)
    parser.add_argument("--artifact", type=Path, action="append", default=[])
    parser.add_argument("--technical-exit-code", type=int, default=0)
    parser.add_argument("--enforce-blockers", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    try:
        summary = collect_release_evidence(
            root=root,
            output_dir=args.output_dir,
            policy_path=(args.policy or root / "release" / "release-policy.json"),
            lock_path=(args.dependency_lock or root / "release" / "dependency-lock.json"),
            test_results=args.test_results,
            artifacts=args.artifact,
            technical_exit_code=args.technical_exit_code,
        )
    except (OSError, ValueError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        print(f"release evidence failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": summary["status"], "output": str(args.output_dir)}, sort_keys=True))
    if summary["status"] == "technical_failure":
        return 2
    if args.enforce_blockers and summary["status"] != "ready":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
