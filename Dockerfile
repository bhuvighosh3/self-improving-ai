FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

ENV SIA_OTEL_EXPORTER=gcp
ENV SIA_WORKSPACE_STORE=firestore

CMD uvicorn self_improving_ai.dashboard.app:app --host 0.0.0.0 --port ${PORT:-8080}
