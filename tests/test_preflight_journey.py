from __future__ import annotations

import json
from pathlib import Path

from agent_workflow.errors import WorkflowError
from agent_workflow.preflight import resolve_prerequisites


def _evidence(run: Path, action: str = "accepted") -> None:
    run.mkdir(parents=True)
    (run / "final-receipt.json").write_text("{}", encoding="utf-8")


def test_preflight_preserves_accepted_rejected_missing_and_stale(monkeypatch, tmp_path):
    runs = tmp_path / "runs"
    accepted, rejected, stale = (runs / name for name in ("accepted", "rejected", "stale"))
    _evidence(accepted)
    _evidence(rejected)
    _evidence(stale)

    def run_dir(_settings, session_id):
        return runs / session_id

    monkeypatch.setattr("agent_workflow.preflight.run_dir", run_dir)
    monkeypatch.setattr(
        "agent_workflow.preflight.verify_seal_details",
        lambda run: ({"session_id": run.name}, "f" * 64),
    )

    def receipts(run, *, expected_final_receipt_sha256):
        if run.name == "stale":
            raise WorkflowError("lifecycle receipt final-receipt digest mismatch")
        action = "rejected" if run.name == "rejected" else "accepted"
        return [{"sequence": 1, "sha256": "a" * 64, "receipt": {"action": action, "reason": "no"}}]

    monkeypatch.setattr("agent_workflow.preflight.lifecycle_receipts", receipts)
    result = resolve_prerequisites(object(), ["accepted", "rejected", "missing", "stale"])
    assert result["status"] == "stale"
    assert {item["status"] for item in result["prerequisites"]} == {"accepted", "rejected", "missing", "stale"}


def test_preflight_ignores_mutable_status_projection(monkeypatch, tmp_path):
    run = tmp_path / "accepted"
    _evidence(run)
    (run / "status.json").write_text(json.dumps({"status": "running", "disposition": "rejected"}), encoding="utf-8")
    monkeypatch.setattr("agent_workflow.preflight.run_dir", lambda _settings, _session_id: run)
    monkeypatch.setattr("agent_workflow.preflight.verify_seal_details", lambda _run: ({}, "a" * 64))
    monkeypatch.setattr(
        "agent_workflow.preflight.lifecycle_receipts",
        lambda _run, *, expected_final_receipt_sha256: [{"sequence": 1, "sha256": "b" * 64, "receipt": {"action": "accepted"}}],
    )
    assert resolve_prerequisites(object(), ["accepted"])["status"] == "accepted"
