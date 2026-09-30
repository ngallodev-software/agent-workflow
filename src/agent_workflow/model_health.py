"""Advisory configured-model lifecycle health.

This module is deliberately outside routing authority. It reports bounded,
source-identified cached metadata and degrades stale, missing, or invalid
metadata to unknown rather than changing executor/model selection.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .contracts import validate_instance
from .path import read_regular_file

METADATA_SCHEMA = "agent-workflow/model-lifecycle-metadata/v1"
REPORT_SCHEMA = "agent-workflow/model-health-report/v1"
METADATA_NAME = "model-lifecycle-metadata.json"


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _configured_models(settings: Settings) -> list[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for executor, policy in settings.executor_policies.items():
        for model in policy.models:
            if model:
                result.add((executor, model))
        if policy.default_model:
            result.add((executor, policy.default_model))
    return sorted(result)


def _unknown_rows(settings: Settings, *, reason: str) -> list[dict[str, Any]]:
    return [
        {
            "executor": executor,
            "model": model,
            "availability": "unknown",
            "lifecycle": "unknown",
            "verification": "unknown",
            "reason": reason,
        }
        for executor, model in _configured_models(settings)
    ]


def build_model_health_report(
    settings: Settings,
    *,
    metadata_path: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a read-only model lifecycle report without influencing routing."""
    path = (metadata_path or (settings.state_root / METADATA_NAME)).resolve()
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    metadata: dict[str, Any] = {
        "path": str(path),
        "status": "missing",
        "source": None,
        "retrieved_at": None,
        "valid_until": None,
        "sha256": None,
        "error": None,
    }
    rows = _unknown_rows(settings, reason="metadata_missing")

    if path.is_file():
        try:
            read = read_regular_file(path, max_bytes=1024 * 1024)
            value = json.loads(read.data.decode("utf-8"))
            validate_instance(value, METADATA_SCHEMA, artifact=str(path))
            retrieved_at = _timestamp(value.get("retrieved_at"))
            valid_until = _timestamp(value.get("valid_until"))
            if retrieved_at is None or valid_until is None or valid_until < retrieved_at:
                raise ValueError("metadata timestamps must be timezone-aware and ordered")
            metadata.update(
                status="fresh",
                source=value["source"],
                retrieved_at=value["retrieved_at"],
                valid_until=value["valid_until"],
                sha256=hashlib.sha256(read.data).hexdigest(),
            )
            if observed_at > valid_until:
                metadata["status"] = "stale"
                rows = _unknown_rows(settings, reason="metadata_stale")
            elif retrieved_at > observed_at:
                metadata["status"] = "invalid"
                metadata["error"] = "metadata retrieval time is in the future"
                rows = _unknown_rows(settings, reason="metadata_invalid")
            else:
                indexed = {
                    (str(item["executor"]), str(item["model"])): item
                    for item in value["models"]
                }
                rows = []
                for executor, model in _configured_models(settings):
                    item = indexed.get((executor, model))
                    if item is None:
                        rows.append(
                            {
                                "executor": executor,
                                "model": model,
                                "availability": "unknown",
                                "lifecycle": "unknown",
                                "verification": "unverified",
                                "reason": "configured_model_absent_from_fresh_metadata",
                            }
                        )
                        continue
                    availability = str(item["availability"])
                    lifecycle = str(item["lifecycle"])
                    verification = (
                        "unavailable"
                        if availability == "unavailable"
                        else lifecycle
                        if lifecycle in {"deprecated", "retired"}
                        else "verified"
                        if availability == "available" and lifecycle == "active"
                        else "unknown"
                    )
                    rows.append(
                        {
                            "executor": executor,
                            "model": model,
                            "availability": availability,
                            "lifecycle": lifecycle,
                            "verification": verification,
                            "reason": None,
                        }
                    )
        except Exception as exc:
            metadata.update(
                status="invalid",
                error=f"{type(exc).__name__}: {exc}",
            )
            rows = _unknown_rows(settings, reason="metadata_invalid")

    report = {
        "schema": REPORT_SCHEMA,
        "observed_at": observed_at.isoformat(),
        "advisory": True,
        "routing_authority": False,
        "metadata": metadata,
        "models": rows,
    }
    validate_instance(report, REPORT_SCHEMA, artifact="model health report")
    return report
