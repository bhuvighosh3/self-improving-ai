from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


_PROJECT_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = {"env_prefix": "SIA_"}

    # GCP / Gemini
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    agent_model: str = "gemini-2.5-flash"
    judge_model: str = "gemini-2.5-pro"

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
