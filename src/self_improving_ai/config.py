from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

from self_improving_ai.agents.portfolio.model_catalog import DEFAULT_MODEL

_PROJECT_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = {"env_prefix": "SIA_"}

    # GCP / Gemini
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    agent_model: str = "gemini-3.8-flash"
    agent_model_fallback: str = "gemini-3.5-flash-lite"
    judge_model: str = "gemini-3.8-flash"
    briefing_discovery: Literal["agent", "backend"] = "agent"
    workspace_store: Literal["local", "firestore"] = "local"
    briefing_news_source: Literal["auto", "fixture", "live"] = "auto"

    # Independent A selection; connection settings do not change B/C defaults.
    portfolio_model: str = DEFAULT_MODEL

    # Paths
    data_dir: Path = _PROJECT_ROOT / "data"
    db_path: Path = _PROJECT_ROOT / "store.db"

    # Evaluation
    passing_threshold: float = 0.8
    num_eval_seeds: int = 5
    candidate_p_value: float = 0.05

    # OpenTelemetry
    otel_service_name: str = "self-improving-ai"
    otel_exporter: str = "console"  # "console" | "otlp"
    otel_endpoint: str = "http://localhost:4317"

    # Dashboard
    fastapi_port: int = 8000


settings = Settings()
