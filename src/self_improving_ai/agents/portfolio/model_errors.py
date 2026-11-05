"""Actionable model errors without returning provider text, URLs or credentials."""
from __future__ import annotations

import httpx


def model_failure(code: str, message: str, *, retryable: bool = False,
                  http_status: int | None = None) -> dict:
    error = {"code": code, "message": message, "retryable": retryable}
    if http_status is not None:
        error["provider_http_status"] = http_status
    return {"status": "error", "source": "gemini", "error": error}


def classify_model_error(exc: Exception) -> dict:
    code = getattr(exc, "code", None)
    # Inspect provider text for classification only; never return the text itself.
    message = str(getattr(exc, "message", "")).lower()
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return model_failure("MODEL_TIMEOUT", "The model request timed out. Try again shortly.", retryable=True)
    if code == 401 or any(text in message for text in ("api key not valid", "api_key_invalid", "invalid api key")):
        return model_failure("MODEL_AUTHENTICATION_FAILED", "Gemini rejected the API key. Update it in Connections.", http_status=code if isinstance(code, int) else None)
    if code == 403:
        return model_failure("MODEL_ACCESS_DENIED", "The Gemini project cannot access this resource. Check its permissions in Google AI Studio.", http_status=403)
    if code == 404:
        return model_failure("MODEL_NOT_FOUND", "The selected Gemini model is unavailable to this account. Choose an available model in Connections.", http_status=404)
    if code == 429:
        return model_failure("MODEL_RATE_LIMITED", "Gemini rate or quota limits were reached. Check project limits in Google AI Studio before retrying.", retryable=True, http_status=429)
    if code == 503:
        return model_failure("MODEL_BUSY", "The selected Gemini model is temporarily busy (503). Try again shortly or choose another model in Connections.", retryable=True, http_status=503)
    if code in {500, 502, 504}:
        return model_failure("MODEL_PROVIDER_UNAVAILABLE", "The Gemini service is temporarily unavailable. Try again shortly.", retryable=True, http_status=code)
    if code == 400:
        return model_failure("MODEL_INVALID_REQUEST", "Gemini rejected the request format. Check model support and the tool configuration.", http_status=400)
    if isinstance(exc, httpx.TransportError):
        return model_failure("MODEL_NETWORK_ERROR", "Could not reach Gemini. Check the connection and try again.", retryable=True)
    return model_failure("MODEL_EXECUTION_FAILED", "Portfolio Agent execution failed. Check the application configuration.")
