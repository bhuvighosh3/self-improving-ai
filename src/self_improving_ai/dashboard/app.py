"""FastAPI backend for the self-improving AI dashboard."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from self_improving_ai.config import settings

app = FastAPI(title="Self-Improving AI Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@app.get("/api/health")
async def health():
    return {"status": "ok", "model": settings.agent_model}


@app.get("/api/clients")
async def list_clients():
    path = _DATA_DIR / "clients" / "households.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


@app.get("/api/clients/{client_id}")
async def get_client(client_id: str):
    path = _DATA_DIR / "clients" / "households.json"
    if path.exists():
        households = json.loads(path.read_text())
        for h in households:
            if h.get("client_id") == client_id:
                return h
    return {"error": "Client not found"}


@app.get("/api/requests")
async def list_requests():
    path = _DATA_DIR / "requests" / "advisor_requests.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


@app.get("/api/tools")
async def list_tools():
    path = _DATA_DIR / "tool_catalog.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.fastapi_port)
