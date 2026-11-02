"""Explicit, bounded live generation check used by the connection dialog."""
from self_improving_ai.agents.portfolio.model_errors import classify_model_error, model_failure
from self_improving_ai.agents.portfolio.model_settings import portfolio_api_key
from self_improving_ai.config import settings


def test_model_connection(*, api_key: str | None = None, model: str | None = None) -> dict:
    """Probe draft values without mutating the saved key/model or process environment."""
    key = (api_key if api_key is not None else portfolio_api_key()).strip()
    selected_model = model if model is not None else settings.portfolio_model
    if not key:
        return model_failure("MISSING_MODEL_CONFIGURATION", "Enter a Gemini API key or use a saved key before testing.")
    client = None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(vertexai=False, api_key=key,
                              http_options=types.HttpOptions(timeout=10000,
                                  retry_options=types.HttpRetryOptions(attempts=1)))
        response = client.models.generate_content(model=selected_model, contents="Reply with OK only.",
                                        config=types.GenerateContentConfig(max_output_tokens=128))
        if not any(part.text and part.text.strip() and not part.thought
                   for candidate in (getattr(response, "candidates", None) or []) if candidate.content
                   for part in (candidate.content.parts or [])):
            return {**model_failure("EMPTY_MODEL_RESPONSE",
                "Gemini returned no usable text. Try again or choose another model.", retryable=True),
                "model": selected_model}
        return {"status": "success", "source": "gemini", "model": selected_model,
                "message": "Gemini accepted a generation request. Connection verified."}
    except Exception as exc:
        return {**classify_model_error(exc), "model": selected_model}
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass  # Cleanup must not replace the bounded, sanitized probe result.
