from pathlib import Path

from agent_workflow.config import load_settings


def test_decision_policy_and_profile_parse(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[decision_policy]\nmode="semantic"\nprofile="approved"\n'
        '[decision_profiles.approved."routing.task_class"]\n'
        'disposition="automated"\nminimum_confidence=0.9\n',
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.decision_mode == "semantic"
    assert settings.decision_profile == "approved"
    assert settings.decision_profiles["approved"]["routing.task_class"].minimum_confidence == 0.9


def test_builtin_typesafe_config_parse(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[semantic]\nprovider="typesafe"\n[semantic.typesafe]\nmodel="jev-latest"\napi_call_log="~/typesafe.jsonl"\n'
        '[decision_policy]\nmode="comparative"\n', encoding="utf-8"
    )
    settings = load_settings(config)
    assert settings.decision_mode == "comparative"
    assert settings.typesafe_model == "jev-latest"
    assert settings.typesafe_api_call_log.name == "typesafe.jsonl"
