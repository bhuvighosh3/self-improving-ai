"""Bound individual Gemini requests without restarting completed ADK tool work."""

from google.adk.models.google_llm import Gemini
from google.genai import types
import httpx


def wire_schema(value):
    """Keep the legacy Gemini wire schema compatible; validation stays strict locally."""
    if isinstance(value, dict):
        allowed = {"type", "properties", "items", "required", "enum", "format", "anyOf", "$defs", "$ref"}
        result = {}
        for key, item in value.items():
            if key not in allowed:
                continue
            result[key] = ({name: wire_schema(child) for name, child in item.items()}
                           if key in {"properties", "$defs"} else wire_schema(item))
        if "const" in value:
            result["enum"] = [value["const"]]
        return result
    if isinstance(value, list):
        return [wire_schema(item) for item in value]
    return value


class BriefingGemini(Gemini):
    request_timeout_ms: int = 30000

    async def generate_content_async(self, llm_request, stream=False):
        schema = llm_request.config.response_schema
        if isinstance(schema, type) and hasattr(schema, "model_json_schema"):
            # This account's GenerateContent endpoint rejects nested
            # additionalProperties. Pydantic still rejects extra fields locally.
            llm_request.config.response_schema = wire_schema(schema.model_json_schema())
            llm_request.config.response_mime_type = "application/json"
        options = llm_request.config.http_options or types.HttpOptions()
        llm_request.config.http_options = options.model_copy(update={
            "timeout": self.request_timeout_ms, "retry_options": self.retry_options})
        try:
            async for response in super().generate_content_async(llm_request, stream=stream):
                yield response
        except httpx.TimeoutException as exc:
            raise TimeoutError("Gemini request exceeded its configured timeout") from exc


def create_model(name: str) -> BriefingGemini:
    """Retry only transient service errors, not credentials, quota or invalid input."""
    return BriefingGemini(model=name, retry_options=types.HttpRetryOptions(
        attempts=3, initial_delay=1, max_delay=4, jitter=0.25,
        http_status_codes=[502, 503, 504]))
