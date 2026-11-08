"""OpenTelemetry tracing setup for the self-improving AI system."""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.sdk.resources import Resource

from self_improving_ai.config import settings

_initialized = False


def init_telemetry() -> trace.Tracer:
    """Initialize OpenTelemetry tracing. Safe to call multiple times."""
    global _initialized
    if _initialized:
        return trace.get_tracer(settings.otel_service_name)

    resource = Resource.create({
        "service.name": settings.otel_service_name,
        "service.version": "1.0.0",
        "cloud.provider": "gcp",
        "cloud.project": settings.google_cloud_project,
    })
    provider = TracerProvider(resource=resource)

    if settings.otel_exporter == "gcp":
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

        exporter = CloudTraceSpanExporter(project_id=settings.google_cloud_project)
    elif settings.otel_exporter == "otlp":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _initialized = True

    return trace.get_tracer(settings.otel_service_name)


def get_tracer() -> trace.Tracer:
    if not _initialized:
        init_telemetry()
    return trace.get_tracer(settings.otel_service_name)
