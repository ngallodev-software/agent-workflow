from __future__ import annotations

from typing import Any, Mapping

from ..errors import WorkflowError


def configure(endpoint: str, service_name: str = "agent-workflow") -> Any:
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ModuleNotFoundError as exc:
        raise WorkflowError(
            "OpenTelemetry export requires: pip install 'agent-workflow[otel]'"
        ) from exc
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name})
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    )
    return provider


def export_event(provider: Any, event: Mapping[str, Any]) -> None:
    tracer = provider.get_tracer("agent-workflow")
    name = f"agent_workflow.{event.get('dimension', 'lifecycle')}"
    with tracer.start_as_current_span(name) as span:
        for key in ("sequence", "actor", "reason", "prior", "new"):
            value = event.get(key)
            if value is not None:
                span.set_attribute(f"agent_workflow.{key}", value)
