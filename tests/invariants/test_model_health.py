from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from agent_workflow.config import defaults
from agent_workflow.model_health import build_model_health_report


def _settings(tmp_path: Path):
    base = defaults(tmp_path / "config.toml")
    return replace(base, state_root=tmp_path / "state")


def test_missing_model_metadata_is_advisory_unknown(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    report = build_model_health_report(
        settings, now=datetime(2026, 9, 30, tzinfo=timezone.utc)
    )

    assert report["advisory"] is True
    assert report["routing_authority"] is False
    assert report["metadata"]["status"] == "missing"
    assert report["models"]
    assert {item["verification"] for item in report["models"]} == {"unknown"}


def test_stale_model_metadata_never_preserves_cached_availability(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    path = settings.state_root / "model-lifecycle-metadata.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema": "agent-workflow/model-lifecycle-metadata/v1",
                "source": "test-catalog",
                "retrieved_at": "2026-01-01T00:00:00+00:00",
                "valid_until": "2026-01-02T00:00:00+00:00",
                "models": [
                    {
                        "executor": "codex",
                        "model": "gpt-6-luna",
                        "availability": "available",
                        "lifecycle": "active",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_model_health_report(
        settings, now=datetime(2026, 9, 30, tzinfo=timezone.utc)
    )

    assert report["metadata"]["status"] == "stale"
    assert report["metadata"]["source"] == "test-catalog"
    assert report["metadata"]["sha256"]
    luna = next(
        item
        for item in report["models"]
        if item["executor"] == "codex" and item["model"] == "gpt-6-luna"
    )
    assert luna["availability"] == "unknown"
    assert luna["lifecycle"] == "unknown"
    assert luna["verification"] == "unknown"


def test_fresh_model_metadata_reports_unavailable_deprecated_and_unverified(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    path = settings.state_root / "model-lifecycle-metadata.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema": "agent-workflow/model-lifecycle-metadata/v1",
                "source": "test-catalog",
                "retrieved_at": "2026-09-29T00:00:00+00:00",
                "valid_until": "2026-10-02T00:00:00+00:00",
                "models": [
                    {
                        "executor": "codex",
                        "model": "gpt-6-luna",
                        "availability": "unavailable",
                        "lifecycle": "active",
                    },
                    {
                        "executor": "claude",
                        "model": "sonnet",
                        "availability": "available",
                        "lifecycle": "deprecated",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_model_health_report(
        settings, now=datetime(2026, 9, 30, tzinfo=timezone.utc)
    )
    by_key = {
        (item["executor"], item["model"]): item for item in report["models"]
    }

    assert report["metadata"]["status"] == "fresh"
    assert by_key[("codex", "gpt-6-luna")]["verification"] == "unavailable"
    assert by_key[("claude", "sonnet")]["verification"] == "deprecated"
    assert by_key[("claude", "haiku")]["verification"] == "unverified"
