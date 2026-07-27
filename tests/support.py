from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_workflow.receipts import initial_completion, initial_provenance
from agent_workflow.util import atomic_write_json, sha256_file


def write_minimal_run(root: Path, *, session_id: str = "test-run", terminal: str = "completed") -> None:
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
    atomic_write_json(
        root / "command.json",
        {"schema": "agent-workflow/command/v1", "argv": ["cat"], "shell": "cat", "executor": None, "classification": "unclassified", "stream_format": "text", "environment_allowlist": []},
    )
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
        initial_completion(session_id=session_id, ticket_id=None, pack_id=None, base_revision=None),
    )
    atomic_write_json(
        root / "collections" / "completion.json",
        {
            "schema": "agent-workflow/completion-collection/v1",
            "session_id": session_id,
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
            session_id=session_id,
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
    status: dict[str, Any] = {
        "schema": "agent-workflow/session-status/v2",
        "session_id": session_id,
        "status": "launched",
        "disposition": None,
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
        "retry_of_run_id": None,
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
