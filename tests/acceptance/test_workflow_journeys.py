from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.conftest import InstalledProduct, fake_agent_path, git_repo, wait_for_status, write_config


def _node(node_id: str, agent_run_id: str, prompt: Path, dependencies: list[str]) -> dict:
    return {
        "node_id": node_id,
        "kind": "task",
        "ticket_id": node_id.upper(),
        "agent_run_id": agent_run_id,
        "tier": "low",
        "pack_id": "acceptance-pack",
        "prompt_path": str(prompt),
        "role": "review",
        "routing": {"task_type": "review", "risk": "low"},
        "input_bindings": {},
        "dependencies": dependencies,
    }


def _snapshot(workflow_id: str, nodes: list[dict]) -> dict:
    return {
        "schema": "agent-workflow/workflow-snapshot/v1",
        "workflow_id": workflow_id,
        "pack_id": "acceptance-pack",
        "pack_manifest_sha256": "0" * 64,
        "nodes": nodes,
    }


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def test_pipeline_runs_through_installed_cli_binds_results_and_seals_terminal_workflow(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "workflow-run"
    git_repo(run_dir)
    pack = run_dir / "pack"
    tickets = pack / "phase-0" / "tickets"
    contracts = pack / "contracts"
    tickets.mkdir(parents=True)
    contracts.mkdir(parents=True)
    first_prompt = tickets / "first.md"
    second_prompt = tickets / "second.md"
    first_prompt.write_text("Produce the first structured result.\n", encoding="utf-8")
    second_prompt.write_text("Consume the sealed predecessor input.\n", encoding="utf-8")
    (pack / "pack.yaml").write_text(
        """schema: agent-workflow/prompt-pack/v1
pack_id: acceptance-pack
workflow:
  name: agent-workflow
  minimum_version: 0.8.0
phases:
  - id: "0"
    name: acceptance
    directory: phase-0
    tasks:
      - id: FIRST
        tier: C
        agent_run_id: pipeline-first
        prompt: phase-0/tickets/first.md
        result_contract:
          schema: contracts/result.schema.json
          required: true
      - id: SECOND
        tier: C
        agent_run_id: pipeline-second
        prompt: phase-0/tickets/second.md
        dependencies: [FIRST]
""",
        encoding="utf-8",
    )
    (contracts / "result.schema.json").write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "required": ["artifact"],
                "properties": {
                    "artifact": {
                        "type": "object",
                        "required": ["id"],
                        "properties": {"id": {"type": "string"}},
                        "additionalProperties": False,
                    }
                },
                "additionalProperties": False,
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(run_dir), "add", "."], check=True)
    subprocess.run(["git", "-C", str(run_dir), "commit", "-qm", "workflow pack"], check=True)
    config = write_config(product_env, fake_agent=fake_agent_path)
    second = _node("second", "pipeline-second", second_prompt, ["first"])
    second["input_bindings"] = {
        "upstream_id": {
            "source_node_id": "first",
            "pointer": "/artifact/id",
            "required": True,
            "max_bytes": 1024,
        }
    }
    snapshot = _write(
        tmp_path / "workflow.json",
        _snapshot(
            "pipeline-e2e",
            [_node("first", "pipeline-first", first_prompt, []), second],
        ),
    )
    env = dict(product_env)
    env["FAKE_AGENT_RESULT_JSON"] = json.dumps({"artifact": {"id": "stage-one"}})

    started = installed_product.json("workflow", "start", run_dir, snapshot, "--config", config, env=env)
    assert started["scheduled"] == ["first"]
    wait_for_status(env, "pipeline-first")

    resumed = installed_product.json("workflow", "resume", run_dir, snapshot, "--config", config, env=env)
    assert resumed["scheduled"] == ["second"]
    wait_for_status(env, "pipeline-second")

    installed_product.json("workflow", "resume", run_dir, snapshot, "--config", config, env=env)
    child_inputs = json.loads(
        (Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / "pipeline-second" / "workflow-inputs.json").read_text()
    )
    binding = child_inputs["bindings"][0]
    assert binding["name"] == "upstream_id"
    assert binding["value"] == "stage-one"

    sealed = installed_product.json("workflow", "seal", run_dir, snapshot, "--config", config, env=env)
    verified = installed_product.json("workflow", "verify", run_dir, snapshot, "--config", config, env=env)
    assert sealed["result"]["verified"] is True
    assert sealed["result"]["workflow_state"] == "completed"
    assert verified["result"]["receipt_sha256"] == sealed["result"]["receipt_sha256"]
    assert (run_dir / "workflow-receipt.json").stat().st_mode & 0o222 == 0


def test_approval_gate_requires_canonical_child_acceptance(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "approval-workflow"
    revision = git_repo(run_dir)
    prompt = run_dir / "implementation.md"
    prompt.write_text("Implement the approved change.\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(run_dir), "add", "."], check=True)
    subprocess.run(["git", "-C", str(run_dir), "commit", "-qm", "workflow prompt"], check=True)
    revision = subprocess.run(
        ["git", "-C", str(run_dir), "rev-parse", "HEAD"], text=True, capture_output=True, check=True
    ).stdout.strip()
    config = write_config(product_env, fake_agent=fake_agent_path)
    task = _node("implementation", "approval-child", prompt, [])
    approval = {
        "node_id": "approval",
        "kind": "approval",
        "approval_for": "implementation",
        "dependencies": ["implementation"],
    }
    snapshot = _write(tmp_path / "approval.json", _snapshot("approval-e2e", [task, approval]))

    installed_product.json("workflow", "start", run_dir, snapshot, "--config", config, env=product_env)
    wait_for_status(product_env, "approval-child")
    before = installed_product.json("workflow", "resume", run_dir, snapshot, "--config", config, env=product_env)
    assert before["scheduled"] == []
    installed_product.json(
        "agent-run", "review", "approval-child", "--actor", "independent-reviewer", "--reason", "verified", env=product_env
    )
    installed_product.json(
        "agent-run", "accept", "approval-child", "--actor", "independent-reviewer", "--reason", "accepted", "--revision", revision,
        env=product_env,
    )
    installed_product.json("workflow", "resume", run_dir, snapshot, "--config", config, env=product_env)
    terminal = installed_product.json("workflow", "status", run_dir, snapshot, "--config", config, env=product_env)
    assert terminal["result"]["workflow_state"] == "completed"


def test_resume_is_idempotent_and_does_not_duplicate_child_launches(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "resume-workflow"
    git_repo(run_dir)
    prompt = run_dir / "task.md"
    prompt.write_text("Run exactly once.\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(run_dir), "add", "."], check=True)
    subprocess.run(["git", "-C", str(run_dir), "commit", "-qm", "prompt"], check=True)
    config = write_config(product_env, fake_agent=fake_agent_path)
    snapshot = _write(
        tmp_path / "resume.json",
        _snapshot("resume-e2e", [_node("only", "resume-child", prompt, [])]),
    )

    installed_product.json("workflow", "start", run_dir, snapshot, "--config", config, env=product_env)
    wait_for_status(product_env, "resume-child")
    first = installed_product.json("workflow", "resume", run_dir, snapshot, "--config", config, env=product_env)
    events_path = run_dir / "workflow-events.jsonl"
    event_count = len(events_path.read_text(encoding="utf-8").splitlines())
    second = installed_product.json("workflow", "resume", run_dir, snapshot, "--config", config, env=product_env)
    after = installed_product.json("workflow", "status", run_dir, snapshot, "--config", config, env=product_env)
    assert first["scheduled"] == []
    assert second["scheduled"] == []
    assert len(events_path.read_text(encoding="utf-8").splitlines()) == event_count
    only = next(item for item in after["result"]["nodes"] if item["node_id"] == "only")
    assert only["attempt"] == 1


def test_authorized_template_expands_to_valid_executable_snapshot(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    tmp_path: Path,
) -> None:
    template = "pipeline"
    parameters = {
        "steps": [
            {"node_id": "a", "agent_run_id": "a", "prompt_path": "/tmp/a"},
            {"node_id": "b", "agent_run_id": "b", "prompt_path": "/tmp/b"},
        ]
    }
    expected_nodes = 2
    spec = _write(
        tmp_path / f"{template}-spec.json",
        {
            "workflow_id": f"{template}-workflow",
            "pack_id": "acceptance-pack",
            "pack_manifest_sha256": "0" * 64,
            "parameters": parameters,
        },
    )
    output = tmp_path / f"{template}.json"
    installed_product.run("workflow", "template", template, spec, "--output", output, env=product_env, check=True)
    validated = installed_product.json("workflow", "validate", output, env=product_env)
    assert validated["result"]["node_count"] == expected_nodes
