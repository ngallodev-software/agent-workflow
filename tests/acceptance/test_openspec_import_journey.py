from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.native_jobs import (
    NATIVE_JOB_SCHEMA,
    NATIVE_JOB_V2_SCHEMA,
    validate_native_job,
    validate_source_specification_worktree,
)
from tests.conftest import InstalledProduct, git_repo


CHANGE = "add-rate-limit"
TASK_ID = "openspec-add-rate-limit-1-1"


def _commit_all(repo: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", message], check=True)
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _write_openspec_repository(repo: Path) -> str:
    git_repo(repo)
    (repo / "src").mkdir()
    (repo / "src" / "limiter.py").write_text("LIMIT = 10\n", encoding="utf-8")

    (repo / "openspec" / "specs" / "api").mkdir(parents=True)
    (repo / "openspec" / "specs" / "api" / "spec.md").write_text(
        textwrap.dedent(
            """\
            # API

            ## Purpose

            Defines observable API behavior for the fixture.

            ### Requirement: Existing request behavior
            The system SHALL preserve ordinary successful requests.

            #### Scenario: ordinary request
            - **WHEN** a request is below the rate limit
            - **THEN** it succeeds
            """
        ),
        encoding="utf-8",
    )
    (repo / "openspec" / "config.yaml").write_text(
        "schema: spec-driven\n",
        encoding="utf-8",
    )

    change = repo / "openspec" / "changes" / CHANGE
    (change / "specs" / "api").mkdir(parents=True)
    (change / "proposal.md").write_text(
        "# Proposal\n\nAdd deterministic request limiting.\n",
        encoding="utf-8",
    )
    (change / "design.md").write_text(
        "# Design\n\nImplement the limiter in src/ and keep planning artifacts read-only.\n",
        encoding="utf-8",
    )
    (change / "specs" / "api" / "spec.md").write_text(
        textwrap.dedent(
            """\
            # Spec Delta

            ## MODIFIED Requirements

            ### Requirement: Existing request behavior
            The system SHALL preserve ordinary successful requests and reject bursts.

            #### Scenario: burst request
            - **WHEN** the request exceeds the configured rate limit
            - **THEN** the system returns a rate-limit response
            """
        ),
        encoding="utf-8",
    )
    (change / "tasks.md").write_text(
        "# Tasks\n\n"
        "- [ ] 1.1 Implement the limiter in src; verification note: "
        "run untrusted-check --from-openspec-task\n",
        encoding="utf-8",
    )
    return _commit_all(repo, "add openspec fixture")


def _write_package_schema(root: Path) -> Path:
    schema_root = root / "schemas" / "spec-driven"
    templates = schema_root / "templates"
    templates.mkdir(parents=True)
    (schema_root / "schema.yaml").write_text(
        textwrap.dedent(
            """\
            name: spec-driven
            version: 1
            description: fixture package schema
            artifacts:
              - id: proposal
                generates: proposal.md
                template: proposal.md
                requires: []
              - id: specs
                generates: "specs/**/*.md"
                template: spec.md
                requires: [proposal]
              - id: design
                generates: design.md
                template: design.md
                requires: [proposal]
              - id: tasks
                generates: tasks.md
                template: tasks.md
                requires: [specs, design]
            apply:
              requires: [tasks]
              tracks: tasks.md
            """
        ),
        encoding="utf-8",
    )
    for name in ("proposal", "spec", "design", "tasks"):
        (templates / f"{name}.md").write_text(
            f"# {name} template\n",
            encoding="utf-8",
        )
    return schema_root


def _write_fake_openspec(
    executable: Path,
    schema_root: Path,
    *,
    version: str = "1.13.2",
    schema_source: str = "package",
) -> None:
    script = f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

VERSION = {version!r}
SOURCE = {schema_source!r}
SCHEMA_ROOT = Path({str(schema_root)!r})

args = sys.argv[1:]
cwd = Path.cwd()
change = {CHANGE!r}
change_root = cwd / "openspec" / "changes" / change
tasks_path = change_root / "tasks.md"

if args == ["--version"]:
    print(VERSION)
    raise SystemExit(0)
elif args == ["schemas", "--json"]:
    value = [{{
        "name": "spec-driven",
        "description": "Default OpenSpec workflow",
        "artifacts": ["proposal", "specs", "design", "tasks"],
        "source": SOURCE,
    }}]
elif args == ["templates", "--schema", "spec-driven", "--json"]:
    value = {{
        "proposal": {{"path": str(SCHEMA_ROOT / "templates" / "proposal.md"), "source": SOURCE}},
        "specs": {{"path": str(SCHEMA_ROOT / "templates" / "spec.md"), "source": SOURCE}},
        "design": {{"path": str(SCHEMA_ROOT / "templates" / "design.md"), "source": SOURCE}},
        "tasks": {{"path": str(SCHEMA_ROOT / "templates" / "tasks.md"), "source": SOURCE}},
    }}
elif args == ["status", "--change", change, "--json"]:
    value = {{
        "changeName": change,
        "schemaName": "spec-driven",
        "isComplete": True,
        "nextSteps": ["Run openspec instructions apply"],
        "artifacts": [
            {{"id": "proposal", "outputPath": "proposal.md", "status": "done", "requires": []}},
            {{"id": "specs", "outputPath": "specs/**/*.md", "status": "done", "requires": ["proposal"]}},
            {{"id": "design", "outputPath": "design.md", "status": "done", "requires": ["proposal"]}},
            {{"id": "tasks", "outputPath": "tasks.md", "status": "done", "requires": ["specs", "design"]}},
        ],
    }}
elif args == ["validate", change, "--strict", "--json", "--no-interactive"]:
    value = {{
        "items": [{{"id": change, "type": "change", "valid": True, "issues": [], "durationMs": 1}}],
        "summary": {{"totals": {{"items": 1, "passed": 1, "failed": 0}}}},
        "version": "1.0",
        "root": {{"path": str(cwd), "source": "nearest"}},
    }}
elif args == ["instructions", "apply", "--change", change, "--json"]:
    value = {{
        "changeName": change,
        "schemaName": "spec-driven",
        "contextFiles": {{
            "proposal": [str(change_root / "proposal.md")],
            "specs": [str(change_root / "specs" / "api" / "spec.md")],
            "design": [str(change_root / "design.md")],
            "tasks": [str(tasks_path)],
        }},
        "progress": {{"total": 1, "complete": 0, "remaining": 1}},
        "tasks": [{{
            "id": "1",
            "description": "1.1 Implement the limiter in src; verification note: run untrusted-check --from-openspec-task",
            "done": False,
        }}],
        "taskTrackingConfigured": True,
        "state": "ready",
        "instruction": "Read context files and implement pending tasks.",
    }}
elif args == ["show", change, "--json", "--no-interactive"]:
    value = {{
        "changeName": change,
        "deltas": [{{"capability": "api", "operation": "MODIFIED"}}],
    }}
else:
    print(json.dumps({{"error": "unsupported fixture invocation", "args": args}}))
    raise SystemExit(2)

print(json.dumps(value, sort_keys=True))
"""
    executable.write_text(script, encoding="utf-8")
    executable.chmod(0o755)


def _write_job_policy(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "scope": {
                    "writable_paths": [],
                    "writable_trees": ["src"],
                    "disposable_trees": [],
                },
                "acceptance_commands": [
                    {
                        "id": "compile-src",
                        "argv": ["python3", "-m", "compileall", "-q", "src"],
                        "cwd": ".",
                        "timeout_seconds": 60,
                        "result_format": "exit-code",
                        "junit_path": None,
                    }
                ],
                "criteria": [
                    {
                        "id": "source-compiles",
                        "description": "Changed Python source compiles.",
                        "acceptance_command_ids": ["compile-src"],
                    }
                ],
                "review_requirement": {
                    "required": False,
                    "independent": False,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _import_fixture(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    tmp_path: Path,
    *,
    version: str = "1.13.2",
    schema_source: str = "package",
) -> tuple[Path, Path, str]:
    repo = tmp_path / "source"
    revision = _write_openspec_repository(repo)
    schema_root = _write_package_schema(tmp_path / "openspec-package")
    fake = Path(product_env["PATH"].split(os.pathsep)[0]) / "openspec"
    _write_fake_openspec(
        fake,
        schema_root,
        version=version,
        schema_source=schema_source,
    )
    policy = tmp_path / "job-policy.json"
    _write_job_policy(policy)
    pack = tmp_path / "pack"
    return repo, pack, revision


def test_openspec_import_freezes_planning_and_keeps_acceptance_host_owned(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, pack, revision = _import_fixture(installed_product, product_env, tmp_path)
    policy = tmp_path / "job-policy.json"

    imported = installed_product.json(
        "pack",
        "import-openspec",
        repo,
        CHANGE,
        pack,
        "--job-policy",
        policy,
        env=product_env,
    )
    assert imported["provider"] == "openspec@1.13.2"
    assert imported["source_revision"] == revision
    assert imported["legacy_specgen_required"] is False
    assert imported["tasks"] == [TASK_ID]

    receipt = json.loads((pack / "source-specification.json").read_text(encoding="utf-8"))
    assert receipt["schema"] == "agent-workflow/source-specification-import/v1"
    assert receipt["provider"]["version"] == "1.13.2"
    assert receipt["workflow_schema"]["source"] == "package"
    assert receipt["workflow_schema"]["name"] == "spec-driven"
    assert receipt["workflow_schema"]["version"] == 1
    assert receipt["repository"]["revision"] == revision
    assert receipt["repository"]["dirty"] is False
    artifact_paths = {item["path"] for item in receipt["artifacts"]}
    assert f"openspec/changes/{CHANGE}/tasks.md" in artifact_paths
    assert "openspec/specs/api/spec.md" in artifact_paths
    assert receipt["task_map"][0]["agent_workflow_task_id"] == TASK_ID

    validation = installed_product.json(
        "pack", "validate", pack, "--verify-checksums", env=product_env
    )
    assert validation["ok"] is True

    job_path = pack / "jobs" / f"{TASK_ID}.json"
    job_value = json.loads(job_path.read_text(encoding="utf-8"))
    assert job_value["schema"] == NATIVE_JOB_V2_SCHEMA
    assert "bundle_provenance" not in job_value
    assert job_value["scope"]["writable_paths"] == []
    assert job_value["scope"]["writable_trees"] == ["src"]
    assert "openspec" not in json.dumps(job_value["scope"])
    assert [item["id"] for item in job_value["acceptance_commands"]] == ["compile-src"]
    serialized_commands = json.dumps(job_value["acceptance_commands"])
    assert "untrusted-check" not in serialized_commands

    prompt = (pack / "phase-0" / "tickets" / f"{TASK_ID}.md").read_text(encoding="utf-8")
    assert "untrusted-check --from-openspec-task" in prompt
    assert "do not infer" in prompt.lower()
    assert "do not edit" in prompt.lower() and "openspec/" in prompt.lower()

    import agent_workflow.native_jobs as native_jobs

    monkeypatch.setattr(
        native_jobs,
        "negotiate_bundle",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("native-job/v2 must not negotiate the SpecGen bundle")
        ),
    )
    job = validate_native_job(job_path, pack_root=pack)
    assert job.schema == NATIVE_JOB_V2_SCHEMA
    assert job.bundle_provenance is None
    assert job.source_specification is not None
    validate_source_specification_worktree(job, repo)

    prompt_path = pack / "phase-0" / "tickets" / f"{TASK_ID}.md"
    fake_agent = Path(product_env["PATH"].split(os.pathsep)[0]) / "fake-agent"
    prepared = installed_product.json(
        "agent-run",
        "prepare",
        "openspec-v2-prepare",
        repo,
        prompt_path,
        "--pack",
        pack,
        "--job",
        f"jobs/{TASK_ID}.json",
        "--worker-mode",
        "external",
        "--interactive",
        "--",
        fake_agent,
        env=product_env,
    )
    assert prepared["status"] == "prepared"
    run_dir = (
        Path(product_env["XDG_STATE_HOME"])
        / "agent-workflow"
        / "runs"
        / "openspec-v2-prepare"
    )
    binding = json.loads((run_dir / "job-binding.json").read_text(encoding="utf-8"))
    assert binding["schema"] == "agent-workflow/job-binding/v2"
    assert "bundle_provenance" not in binding
    assert binding["source_specification"]["schema"] == (
        "agent-workflow/source-specification-import/v1"
    )
    assert (run_dir / "jobs" / "source-specification.json").is_file()

    report = pack / "source-reports" / "show.json"
    report.write_text('{"tampered": true}\n', encoding="utf-8")
    with pytest.raises(WorkflowError, match="report digest mismatch"):
        validate_native_job(job_path, pack_root=pack)


def test_openspec_source_drift_is_rejected_after_import(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    tmp_path: Path,
) -> None:
    repo, pack, _ = _import_fixture(installed_product, product_env, tmp_path)
    installed_product.json(
        "pack",
        "import-openspec",
        repo,
        CHANGE,
        pack,
        "--job-policy",
        tmp_path / "job-policy.json",
        env=product_env,
    )
    job = validate_native_job(pack / "jobs" / f"{TASK_ID}.json", pack_root=pack)
    tasks = repo / "openspec" / "changes" / CHANGE / "tasks.md"
    tasks.write_text(tasks.read_text(encoding="utf-8") + "\n<!-- drift -->\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="must be clean"):
        validate_source_specification_worktree(job, repo)


@pytest.mark.parametrize(
    ("version", "schema_source", "expected"),
    [
        ("1.13.1", "package", "requires exact version 1.13.2"),
        ("1.13.2", "project", "requires package-owned spec-driven"),
    ],
)
def test_openspec_import_fails_closed_outside_qualified_surface(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    tmp_path: Path,
    version: str,
    schema_source: str,
    expected: str,
) -> None:
    repo, pack, _ = _import_fixture(
        installed_product,
        product_env,
        tmp_path,
        version=version,
        schema_source=schema_source,
    )
    result = installed_product.run(
        "pack",
        "import-openspec",
        repo,
        CHANGE,
        pack,
        "--job-policy",
        tmp_path / "job-policy.json",
        env=product_env,
    )
    assert result.returncode == 2
    assert expected in result.stderr
    assert not pack.exists()



def test_openspec_import_keeps_hidden_oracle_in_host_evaluation_policy(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    tmp_path: Path,
) -> None:
    repo, pack, _ = _import_fixture(installed_product, product_env, tmp_path)
    installed_product.json(
        "pack",
        "import-openspec",
        repo,
        CHANGE,
        pack,
        "--job-policy",
        tmp_path / "job-policy.json",
        env=product_env,
    )

    oracle_id = "hidden-fixture-oracle-v1"
    oracle_sha = "7" * 64
    evaluation_dir = pack / "evals"
    evaluation_dir.mkdir()
    evaluation = evaluation_dir / "hidden-evaluation.json"
    evaluation.write_text(
        json.dumps(
            {
                "schema": "agent-workflow/evaluation-plan/v1",
                "dataset_split": "holdout",
                "task_ids": [TASK_ID],
                "repetitions": 1,
                "timeout_seconds": 30,
                "scorers": ["acceptance_commands"],
                "sandbox": "docker",
                "oracle_refs": {
                    TASK_ID: {
                        "id": oracle_id,
                        "sha256": oracle_sha,
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    installed_product.json("pack", "checksum", pack, env=product_env)

    source_receipt_text = (pack / "source-specification.json").read_text(encoding="utf-8")
    prompt = pack / "phase-0" / "tickets" / f"{TASK_ID}.md"
    prompt_text = prompt.read_text(encoding="utf-8")
    assert oracle_id not in source_receipt_text
    assert oracle_sha not in source_receipt_text
    assert oracle_id not in prompt_text
    assert oracle_sha not in prompt_text

    fake_agent = Path(product_env["PATH"].split(os.pathsep)[0]) / "fake-agent"
    prepared = installed_product.json(
        "agent-run",
        "prepare",
        "openspec-v2-hidden-oracle",
        repo,
        prompt,
        "--pack",
        pack,
        "--job",
        f"jobs/{TASK_ID}.json",
        "--evaluation",
        evaluation,
        "--worker-mode",
        "external",
        "--interactive",
        "--",
        fake_agent,
        env=product_env,
    )
    assert prepared["status"] == "prepared"

    run_dir = (
        Path(product_env["XDG_STATE_HOME"])
        / "agent-workflow"
        / "runs"
        / "openspec-v2-hidden-oracle"
    )
    runtime = json.loads((run_dir / "evaluation-runtime.json").read_text(encoding="utf-8"))
    assert runtime["oracle_refs"] == {
        TASK_ID: {
            "id": oracle_id,
            "sha256": oracle_sha,
        }
    }
    binding = json.loads((run_dir / "job-binding.json").read_text(encoding="utf-8"))
    assert binding["schema"] == "agent-workflow/job-binding/v2"
    assert "oracle_refs" not in binding
    assert oracle_id not in json.dumps(binding)



def test_native_job_v1_retains_legacy_bundle_negotiation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = tmp_path / "legacy-pack"
    pack.mkdir()
    (pack / "prompt.md").write_text("legacy\n", encoding="utf-8")
    job_path = pack / "job.json"
    provenance = {
        "bundle_version": "0.2.1",
        "schema_id": "agent-workflow/prompt-pack/v1",
        "schema_digest": "0" * 64,
    }
    job_path.write_text(
        json.dumps(
            {
                "schema": NATIVE_JOB_SCHEMA,
                "job_id": "legacy-job",
                "ticket_id": "legacy-ticket",
                "bundle_provenance": provenance,
                "prompt_path": "prompt.md",
                "worktree_target": "src",
                "path_policy": {
                    "allowed_paths": ["src"],
                    "forbidden_paths": [],
                },
                "acceptance_commands": [],
                "review_requirement": {
                    "required": False,
                    "independent": False,
                },
            }
        ),
        encoding="utf-8",
    )

    calls: list[dict[str, object]] = []

    def negotiate(value: object) -> dict[str, object]:
        assert value == provenance
        calls.append(dict(provenance))
        return {"legacy": True}

    import agent_workflow.native_jobs as native_jobs

    monkeypatch.setattr(native_jobs, "negotiate_bundle", negotiate)
    job = validate_native_job(job_path, pack_root=pack)
    assert calls == [provenance]
    assert job.schema == NATIVE_JOB_SCHEMA
    assert job.bundle_provenance == {"legacy": True}
    assert job.source_specification is None
