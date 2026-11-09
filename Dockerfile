FROM node:20-slim AS frontend
WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

COPY --from=frontend /app/dashboard/dist dashboard/dist

ENV SIA_OTEL_EXPORTER=gcp
ENV SIA_WORKSPACE_STORE=firestore

CMD uvicorn self_improving_ai.dashboard.app:app --host 0.0.0.0 --port ${PORT:-8080}
