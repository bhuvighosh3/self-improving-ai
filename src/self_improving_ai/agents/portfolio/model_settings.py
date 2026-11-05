"""Portfolio-specific Developer API configuration without changing shared settings."""
import os
from functools import cached_property

from google.adk.models.google_llm import Gemini
from google.genai import Client, types
from pydantic import Field, SecretStr


def portfolio_api_key() -> str:
    # An explicit empty local override disables A even if the team has a key.
    if "SIA_PORTFOLIO_API_KEY" in os.environ:
        return os.environ["SIA_PORTFOLIO_API_KEY"].strip()
    return (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()


class PortfolioGemini(Gemini):
    api_key: SecretStr = Field(exclude=True, repr=False)

    @cached_property
    def api_client(self) -> Client:
        # ADK documents overriding this property for explicit Client settings.
        # No mutation of GOOGLE_API_KEY or the team's Vertex AI mode is needed.
        return Client(vertexai=False, api_key=self.api_key.get_secret_value(),
                      http_options=types.HttpOptions(timeout=60000, retry_options=self.retry_options))
