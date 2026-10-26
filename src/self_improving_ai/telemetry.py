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

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    if settings.otel_exporter == "otlp":
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
    return trace.get_tracer(settings.otel_service_name)
