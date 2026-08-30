"""Narrow adapter for the released SpecGen/Agent-Workflow contract bundle."""

from __future__ import annotations

from typing import Any

from .errors import WorkflowError

NATIVE_BUNDLE_SCHEMA = "agent-workflow/prompt-pack/v1"


def negotiate_bundle(provenance: Any) -> dict[str, Any]:
    """Verify producer provenance using only the bundle's documented API.

    Native-job execution remains an Agent-Workflow concern.  This adapter
    only establishes that the producer compiled against the exact immutable
    bundle release and shared schema bytes installed in this process.
    """
    if not isinstance(provenance, dict):
        raise WorkflowError("native job is missing bundle_provenance")
    try:
        from specgen_contracts import negotiate
    except ImportError as exc:
        raise WorkflowError(
            "native job requires the specgen-agent-workflow-contracts bundle"
        ) from exc

    version = provenance.get("bundle_version")
    schema_id = provenance.get("schema_id", NATIVE_BUNDLE_SCHEMA)
    schema_digest = provenance.get("schema_digest")
    if not isinstance(version, str) or not isinstance(schema_id, str) or not isinstance(schema_digest, str):
        raise WorkflowError(
            "native job bundle_provenance requires bundle_version, schema_id, and schema_digest"
        )
    try:
        return negotiate(
            bundle_version=version,
            schema_id=schema_id,
            schema_digest_value=schema_digest,
            features=frozenset(provenance.get("features", [])),
        )
    except (TypeError, ValueError) as exc:
        raise WorkflowError(f"incompatible native job bundle provenance: {exc}") from exc
