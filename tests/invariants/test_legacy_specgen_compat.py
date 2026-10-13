from __future__ import annotations

import builtins

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.shared_contracts import negotiate_bundle


def test_native_job_v1_missing_legacy_bundle_fails_with_actionable_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def blocked_import(name: str, *args, **kwargs):
        if name == "specgen_contracts" or name.startswith("specgen_contracts."):
            raise ImportError("legacy SpecGen compatibility bundle intentionally absent")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    with pytest.raises(WorkflowError, match="legacy-specgen"):
        negotiate_bundle(
            {
                "bundle_version": "0.2.0",
                "schema_id": "agent-workflow/prompt-pack/v2",
                "schema_digest": "0" * 64,
            }
        )
