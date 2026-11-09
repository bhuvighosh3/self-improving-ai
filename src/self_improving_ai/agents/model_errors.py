"""Recognize provider limits before structured-output parsing hides their cause."""

import logging

from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.genai import types
from google.genai.errors import APIError

log = logging.getLogger(__name__)


class ModelOutputLimitError(RuntimeError):
    def __init__(self, *, model=None, output_limit=None, usage=None):
        self.model = model
        self.output_limit = output_limit
        self.usage = usage or {}
        super().__init__("Gemini stopped with MAX_TOKENS; the incomplete output was rejected")


def reject_truncated_response(response, *, model=None, output_limit=None):
    """Run at the model boundary, before ADK validates any output_schema."""
    if response.finish_reason == types.FinishReason.MAX_TOKENS:
        usage = response.usage_metadata.model_dump(exclude_none=True) if response.usage_metadata else {}
        log.warning("Model output truncated: model=%s finish_reason=MAX_TOKENS output_limit=%s usage=%s",
                    model, output_limit, usage)
        raise ModelOutputLimitError(model=model, output_limit=output_limit, usage=usage)


def error_chain(exc):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = exc.__cause__


def model_error_code(exc):
    """Keep output, input context, call budget and quota failures distinct."""
    chain = list(error_chain(exc))
    if any(isinstance(error, ModelOutputLimitError) for error in chain):
        return "output_token_limit"
    text = " ".join(str(error).lower() for error in chain)
    if any(phrase in text for phrase in (
        "input token count", "input token limit", "maximum context length", "context window exceeded",
    )):
        return "input_context_limit"
    if any(isinstance(error, LlmCallsLimitExceededError) for error in chain) or any(
        phrase in text for phrase in ("max_llm_calls", "max number of llm calls")
    ):
        return "llm_call_limit"
    codes = {error.code for error in chain if isinstance(error, APIError)}
    if 429 in codes or "resource_exhausted" in text:
        return "rate_limit"
    if any(isinstance(error, TimeoutError) for error in chain):
        return "timeout"
    if codes.intersection({503, 504}) or any(
        word in text for word in ("unavailable", "deadline_exceeded")
    ):
        return "service_busy"
    return "service_error"


def model_error_message(code):
    return {
        "output_token_limit": "Gemini reached its output token limit. The incomplete response was rejected. Please retry with a narrower request.",
        "input_context_limit": "The request exceeded Gemini's input context limit. Try fewer clients or a shorter request.",
        "llm_call_limit": "That request needed more steps than I could complete in one pass. Try asking about fewer clients at once, or be more specific about what you need.",
        "rate_limit": "Rate limit reached — please wait a moment and try again.",
        "timeout": "The AI service timed out. Please try again in a minute.",
        "service_busy": "The AI service is temporarily busy or timed out. Please try again in a minute.",
    }.get(code, "Something went wrong. Please try again.")
