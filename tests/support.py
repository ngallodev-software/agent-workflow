from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agent_workflow.command_catalog import write_launch_command_artifacts
from agent_workflow.contracts import schema_descriptor
from agent_workflow.receipts import initial_completion, initial_provenance
from agent_workflow.util import atomic_write_json, sha256_file


def write_minimal_run(root: Path, *, agent_run_id: str = "test-run", terminal: str = "completed") -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, content in {
        "prompt.md": "task\n",
        "launch-prompt.md": "task\n",
        "completion.md": "completion\n",
        "executor-events.jsonl": "",
        "executor-stderr.log": "",
        "output.log": "done\n",
        "patch.diff": "",
    }.items():
        (root / name).write_text(content, encoding="utf-8")
    command = {
        "schema": "agent-workflow/command/v1",
        "argv": ["cat"],
        "shell": "cat",
        "executor": None,
        "classification": "unclassified",
        "stream_format": "text",
        "environment_allowlist": [],
        "mode": "headless",
        "interactive_stdio": False,
    }
    atomic_write_json(root / "command.json", command)
    atomic_write_json(
        root / "source-baseline.json",
        {
            "schema": "agent-workflow/source-baseline/v1",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "components": {"primary": {"path": str(root), "head": "", "branch": "", "dirty": False}},
        },
    )
    atomic_write_json(
        root / "completion.json",
        initial_completion(agent_run_id=agent_run_id, ticket_id=None, pack_id=None, base_revision=None),
    )
    atomic_write_json(
        root / "collections" / "completion.json",
        {
            "schema": "agent-workflow/completion-collection/v1",
            "agent_run_id": agent_run_id,
            "adapter": "native",
            "adapter_version": "1",
            "source_path": None,
            "source_sha256": None,
            "canonical_mapping": "identity",
            "canonical_sha256": sha256_file(root / "completion.json"),
            "validation_status": "valid",
            "validation_errors": [],
            "collected_at": "2026-01-01T00:00:00+00:00",
            "stored_path": "completion.json",
        },
    )
    atomic_write_json(
        root / "run-provenance.json",
        initial_provenance(
            agent_run_id=agent_run_id,
            executor=None,
            argv=["cat"],
            stream_format="text",
            executor_version=None,
            prompt_sha256="0" * 64,
            launch_prompt_sha256="1" * 64,
            config_sha256=None,
            pack_manifest_sha256=None,
            source_revision=None,
            worktree=root,
            environment={},
        ),
    )
    command_artifacts = write_launch_command_artifacts(
        root, role="implementation"
    )
    prompt_sha256 = sha256_file(root / "prompt.md")
    launch_prompt_sha256 = sha256_file(root / "launch-prompt.md")
    source_baseline_sha256 = sha256_file(root / "source-baseline.json")
    contract = {
        "schema": "agent-workflow/agent-run-contract/v1",
        "version": 1,
        "agent_run": {
            "id": agent_run_id,
            "agent_name": None,
            "agent_class": "implementation",
            "tier": "medium",
            "retry_of_agent_run_id": None,
            "created_at": "2026-01-01T00:00:00+00:00",
        },
        "ticket": None,
        "ticket_identity": {"mode": "omitted", "value": None},
        "pack": {"id": None, "root": None, "manifest_sha256": None},
        "worktree": {
            "path": str(root),
            "source_revision": None,
            "branch": None,
            "dirty_at_launch": None,
        },
        "prompt": {
            "source": str(root / "prompt.md"),
            "stored": "prompt.md",
            "sha256": prompt_sha256,
            "launch_stored": "launch-prompt.md",
            "launch_sha256": launch_prompt_sha256,
        },
        "worker_plan": {
            "argv": ["cat"],
            "command_sha256": hashlib.sha256(
                json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "stream_format": "text",
            "environment_allowlist": [],
            "mode": "headless",
            "interactive_stdio": False,
            "executor": None,
            "model": None,
        },
        "paths": {
            "run_dir": ".",
            "workdir": str(root),
            "handoff_dir": str(root),
            "completion": "completion.json",
            "result": "result.json",
            "result_contract": None,
            "runtime": "evaluation-runtime.json",
            "source_baseline": "source-baseline.json",
        },
        "schemas": {
            "launch": schema_descriptor("agent-workflow/agent-run-contract/v1"),
            "command_catalog": schema_descriptor("agent-workflow/command-catalog/v1"),
            "completion": schema_descriptor("agent-workflow/completion/v1"),
            "provenance": schema_descriptor("agent-workflow/run-provenance/v1"),
            "status": schema_descriptor("agent-workflow/agent-run-status/v1"),
            "source_baseline": schema_descriptor("agent-workflow/source-baseline/v1"),
            "completion_collection": schema_descriptor("agent-workflow/completion-collection/v1"),
            "task_result": None,
        },
        "runtime_policy": {},
        "evaluation_policy": {},
        "source_baseline": {
            "path": "source-baseline.json",
            "sha256": source_baseline_sha256,
        },
        "expected_outputs": {
            "output_log": "output.log",
            "executor_events": "executor-events.jsonl",
            "executor_stderr": "executor-stderr.log",
            "final_status": "final-status.json",
            "final_receipt": "final-receipt.json",
        },
        "command_catalog": command_artifacts,
    }
    atomic_write_json(root / "agent-run-contract.json", contract)

    status: dict[str, Any] = {
        "schema": "agent-workflow/agent-run-status/v1",
        "agent_run_id": agent_run_id,
        "status": "prepared",
        "disposition": None,
        "worker_mode": "headless",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "workdir": str(root),
        "prompt_path": str(root / "prompt.md"),
        "log_path": str(root / "output.log"),
        "completion_collection_path": str(root / "collections" / "completion.json"),
        "completion_validation_status": "valid",
        "tier": "medium",
        "executor": None,
        "evaluation_path": None,
    }
    atomic_write_json(root / "status.json", status)
    atomic_write_json(root / "final-status.json", {**status, "status": terminal})


def trial(trial_id: str, verdict: str, *, task_id: str = "task-1", repetition: int = 0) -> dict[str, Any]:
    nullable = {
        "duration_seconds": 1.0,
        "input_tokens": None,
        "cached_input_tokens": None,
        "cache_write_input_tokens": None,
        "output_tokens": None,
        "reasoning_output_tokens": None,
        "provider_total_tokens": None,
        "tokens": None,
        "provider_billed_cost": None,
        "local_estimated_cost": None,
        "currency": None,
        "price_catalog_id": None,
        "retry_of_agent_run_id": None,
        "retry_count": 0,
        "steer_count": 0,
        "steer_acknowledged_count": 0,
    }
    return {
        "schema": "agent-workflow/trial-evidence/v2",
        "trial_id": trial_id,
        "run_path": f"/runs/{trial_id}",
        "final_receipt_sha256": "1" * 64,
        "provider_evidence_sha256": "2" * 64,
        "raw_events_sha256": "3" * 64,
        "verdict": verdict,
        "provider": "codex",
        "source_revision": "source-v1",
        "pack_manifest_sha256": None,
        "model": "fixture-model",
        "executor": "codex",
        "executor_version": "fixture-v1",
        "fixture_revision": "fixture-v1",
        "fixture_sha256": None,
        "task_id": task_id,
        "base_revision": "base-v1",
        "prompt_sha256": "4" * 64,
        "oracle_sha256": "5" * 64,
        "reference_sha256": None,
        "acceptance_commands_sha256": "6" * 64,
        "scope_policy_sha256": "7" * 64,
        "scorer_versions_sha256": "8" * 64,
        "sandbox": "docker",
        "budget_sha256": "9" * 64,
        "repetition": repetition,
        "errors": [],
        "source_artifacts": {},
        **nullable,
    }
