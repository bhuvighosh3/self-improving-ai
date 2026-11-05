"""Offline transport for wiring checks, with no natural-language interpretation."""
import json

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field


class ReplayModel(BaseLlm):
    model: str = "offline-declared-tool-sequence"
    steps: list[dict] = Field(default_factory=list)
    answer_shape: str = "last_result"
    inject_wrong_currency: bool = False

    async def generate_content_async(self, llm_request, stream=False):
        results=[part.function_response.response for content in llm_request.contents
                 for part in content.parts or [] if part.function_response]
        if len(results)<len(self.steps):
            step=self.steps[len(results)]
            part=types.Part(function_call=types.FunctionCall(name=step["tool"],args=step["arguments"]))
        else:
            answer={"results":results} if self.answer_shape=="results_array" else dict(results[-1])
            if self.inject_wrong_currency:
                answer["currency"]="EUR"
            part=types.Part(text=json.dumps(answer))
        yield LlmResponse(content=types.Content(role="model",parts=[part]))

