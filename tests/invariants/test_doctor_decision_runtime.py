from dataclasses import replace

from agent_workflow.config import defaults
from agent_workflow.doctor import _decision_runtime_diagnostics


def test_doctor_deterministic_mode_requires_no_semantic_runtime() -> None:
    result = _decision_runtime_diagnostics(defaults())

    assert result["ok"] is True
    assert result["typesafe_required"] is False
    assert result["comparative_eval_required"] is False


def test_doctor_typesafe_mode_requires_sdk_and_api_key(monkeypatch) -> None:
    monkeypatch.setattr(
        "agent_workflow.semantic.typesafe.capability",
        lambda settings: {
            "provider": "typesafe",
            "typesafe_sdk_installed": True,
            "api_key_configured": False,
            "model": None,
        },
    )
    result = _decision_runtime_diagnostics(
        replace(defaults(), decision_mode="typesafe")
    )

    assert result["ok"] is False
    assert result["typesafe_required"] is True
    assert result["typesafe"]["api_key_configured"] is False
    assert "TYPESAFE_API_KEY" not in str(result)


def test_doctor_comparative_mode_requires_compatible_shared_library(monkeypatch) -> None:
    monkeypatch.setattr(
        "agent_workflow.semantic.typesafe.capability",
        lambda settings: {
            "provider": "typesafe",
            "typesafe_sdk_installed": True,
            "api_key_configured": True,
            "model": None,
        },
    )
    monkeypatch.setattr(
        "agent_workflow.comparative_eval.shared_library_status",
        lambda: {
            "installed": True,
            "compatible": False,
            "version": "0.0.0",
            "distribution": "agent-workflow-comparative-eval",
        },
    )
    result = _decision_runtime_diagnostics(
        replace(defaults(), decision_mode="comparative")
    )

    assert result["ok"] is False
    assert result["comparative_eval_required"] is True
    assert result["comparative_eval"]["compatible"] is False
