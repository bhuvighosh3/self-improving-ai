"""Local-only connection management with non-echoing validation and immediate updates."""
from __future__ import annotations

import asyncio
import os
from ipaddress import ip_address
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, SecretStr
from starlette.concurrency import run_in_threadpool

from self_improving_ai.agents.portfolio.model_catalog import FREE_TIER_MODEL_IDS, GEMINI_MODELS
from self_improving_ai.agents.portfolio.model_connection import test_model_connection
from self_improving_ai.agents.portfolio.model_errors import model_failure
from self_improving_ai.agents.portfolio.model_settings import portfolio_api_key
from self_improving_ai.config import settings
from self_improving_ai.connection_store import update_connections
from self_improving_ai.tools.portfolio.market_data_api import probe_market_quote

TEST_TIMEOUT_SECONDS = 12


class PrivateValidationRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def non_echoing_handler(request: Request):
            try:
                return await handler(request)
            except RequestValidationError:
                # Default validation responses can include the complete submitted key.
                return JSONResponse(status_code=422, content={"detail": "Check the connection fields and try again."})
        return non_echoing_handler


def local_request(request: Request):
    try:
        loopback = bool(request.client and ip_address(request.client.host).is_loopback)
    except ValueError:
        loopback = False
    host = urlsplit("http://" + request.headers.get("host", "")).hostname
    if not loopback or host not in {"127.0.0.1", "localhost", "::1"}:
        raise HTTPException(status_code=403, detail="Connection settings are available locally only.")
    origin = request.headers.get("origin")
    allowed = {f"http://{hostname}:{port}" for hostname in ("127.0.0.1", "localhost")
               for port in (5173, 5174, 8000, 8002)}
    if origin and origin not in allowed:
        raise HTTPException(status_code=403, detail="Open connection settings from this local application.")


router = APIRouter(prefix="/api/portfolio/connections", tags=["connections"],
                   route_class=PrivateValidationRoute, dependencies=[Depends(local_request)])


class MarketConnection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    provider: Literal["twelve_data"] = "twelve_data"
    api_key: SecretStr | None = None


class AgentConnection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    api_key: SecretStr | None = None
    model: str | None = None


def checked_key(value: SecretStr | None) -> str | None:
    if value is None:
        return None
    key = value.get_secret_value().strip()
    if not key:
        return None  # A blank field preserves the saved key; DELETE is explicit.
    if len(key) > 4096 or any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise HTTPException(status_code=422, detail="API keys must contain visible characters without spaces.")
    return key


def status() -> dict:
    return {"market": {"provider": "twelve_data", "provider_name": "Twelve Data",
                       "configured": bool(os.environ.get("TWELVE_DATA_API_KEY", "").strip())},
            "agent": {"provider": "gemini", "configured": bool(portfolio_api_key()),
                "model": settings.portfolio_model, "model_options": GEMINI_MODELS,
                "model_options_verified_on": "2026-11-02"},
            "storage": "this_computer", "credentials_returned": False}


def persist(values: dict[str, str]):
    try:
        update_connections(values)
    except (OSError, ValueError):
        raise HTTPException(status_code=500, detail="Could not save the connection on this computer.") from None


@router.get("")
def get_status():
    return status()


@router.put("/market")
def save_market(request: MarketConnection):
    values = {"SIA_MARKET_DATA_PROVIDER": request.provider}
    key = checked_key(request.api_key)
    if key is not None:
        values["TWELVE_DATA_API_KEY"] = key
    if key is None and not status()["market"]["configured"]:
        raise HTTPException(status_code=422, detail="Enter a market-data API key first.")
    persist(values)
    return status()


@router.delete("/market")
def remove_market():
    persist({"TWELVE_DATA_API_KEY": ""})
    return status()


@router.post("/market/test")
async def test_market(request: MarketConnection | None = None):
    # Explicit user action only: no provider request is made merely by saving.
    key = checked_key(request.api_key) if request else None
    key = key or os.environ.get("TWELVE_DATA_API_KEY", "").strip()
    if not key:
        return {"status": "error", "source": "twelve_data", "error": {
            "code": "MISSING_API_KEY", "message": "Enter a market-data API key before testing.", "retryable": False}}
    try:
        return await asyncio.wait_for(run_in_threadpool(probe_market_quote, key),
                                      timeout=TEST_TIMEOUT_SECONDS)
    except TimeoutError:
        return {"status": "error", "source": "twelve_data", "error": {
            "code": "TIMEOUT", "message": "The market-data test timed out. Try again.", "retryable": True}}


@router.put("/agent")
def save_agent(request: AgentConnection):
    values = {}
    key = checked_key(request.api_key)
    if key is not None:
        values["SIA_PORTFOLIO_API_KEY"] = key
    if request.model is not None:
        model = request.model.strip()
        if model not in FREE_TIER_MODEL_IDS:
            raise HTTPException(status_code=422, detail="Choose one of the listed models with a free tier.")
        values["SIA_PORTFOLIO_MODEL"] = model
    if key is None and not status()["agent"]["configured"]:
        raise HTTPException(status_code=422, detail="Enter a Gemini API key first.")
    persist(values)
    if "SIA_PORTFOLIO_MODEL" in values:
        settings.portfolio_model = values["SIA_PORTFOLIO_MODEL"]
    return status()


@router.delete("/agent")
def remove_agent():
    persist({"SIA_PORTFOLIO_API_KEY": ""})
    return status()


@router.post("/agent/test")
async def test_agent_connection(request: AgentConnection | None = None):
    selected_model = (request.model.strip() if request and request.model is not None
                      else settings.portfolio_model)
    if selected_model not in FREE_TIER_MODEL_IDS:
        raise HTTPException(status_code=422, detail="Choose one of the listed models with a free tier.")
    key = checked_key(request.api_key) if request else None
    key = key or portfolio_api_key()
    if not key:
        return model_failure("MISSING_MODEL_CONFIGURATION", "Enter a Gemini API key before testing.")
    try:
        return await asyncio.wait_for(run_in_threadpool(test_model_connection,
            api_key=key, model=selected_model), timeout=TEST_TIMEOUT_SECONDS)
    except TimeoutError:
        return {**model_failure("MODEL_TIMEOUT", "The Gemini connection test timed out. Try again.",
                               retryable=True), "model": selected_model}
