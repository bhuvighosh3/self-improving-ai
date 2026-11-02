"""Connection persistence and credential boundaries, with every provider request intercepted."""
import io
import json

import pytest
from fastapi.testclient import TestClient
from google.genai import types

from self_improving_ai import connection_store
from self_improving_ai.config import settings
from self_improving_ai.dashboard.app import app
from self_improving_ai.tools.portfolio import market_data_api


@pytest.fixture
def connection_client(tmp_path,monkeypatch):
    monkeypatch.setattr(connection_store,"STORE_PATH",tmp_path/"private"/"connections.json")
    for key in connection_store.ALLOWED | {"GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"}:
        monkeypatch.setenv(key,"")
        monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(settings,"portfolio_model","gemini-3.5-flash-lite")
    with TestClient(app,base_url="http://127.0.0.1",client=("127.0.0.1",50000)) as client:
        yield client


def test_saved_market_key_is_private_persistent_and_immediately_used(connection_client,monkeypatch):
    key="offline-fake-market-secret"
    response=connection_client.put("/api/portfolio/connections/market",json={"provider":"twelve_data","api_key":key})
    assert response.status_code==200
    assert response.json()["market"]["configured"]
    assert key not in response.text
    assert key not in connection_client.get("/api/portfolio/connections").text
    assert connection_store.read_connections()["TWELVE_DATA_API_KEY"]==key
    seen=[]
    def transport(request,**kwargs):
        seen.append(request.get_header("Authorization"))
        return io.BytesIO(json.dumps({"symbol":"AAPL","currency":"USD","datetime":"2026-10-30",
                                      "close":"123.45","is_market_open":False}).encode())
    monkeypatch.setattr(market_data_api,"urlopen",transport)
    result=connection_client.post("/api/portfolio/connections/market/test")
    assert result.json()["price"]==123.45
    assert seen==["apikey "+key]
    assert key not in result.text
    normal=connection_client.post("/api/portfolio/execute",json={"task":"quote","symbol":"AAPL"})
    assert normal.json()["result"]["price"]==123.45
    assert key not in normal.text
    monkeypatch.delenv("TWELVE_DATA_API_KEY")
    connection_store.restore_connections()
    assert connection_client.get("/api/portfolio/connections").json()["market"]["configured"]


def test_blank_preserves_and_delete_survives_restart(connection_client,monkeypatch):
    connection_client.put("/api/portfolio/connections/market",json={"api_key":"test-preserved-key"})
    connection_client.put("/api/portfolio/connections/market",json={"api_key":"  "})
    assert connection_store.read_connections()["TWELVE_DATA_API_KEY"]=="test-preserved-key"
    assert not connection_client.delete("/api/portfolio/connections/market").json()["market"]["configured"]
    monkeypatch.setenv("TWELVE_DATA_API_KEY","old-environment-key")
    connection_store.restore_connections()
    assert not connection_client.get("/api/portfolio/connections").json()["market"]["configured"]
    result=connection_client.post("/api/portfolio/connections/market/test")
    assert result.json()["error"]["code"]=="MISSING_API_KEY"


@pytest.mark.parametrize("payload",[
    {"provider":"unsupported","api_key":"never-echo-this-secret"},
    {"api_key":"never-echo-this-secret\nwith-control"},
    {"api_key":{"nested_secret":"never-echo-this-secret"}},
    {"api_key":"never-echo-this-secret","unknown_field":True},
])
def test_validation_does_not_echo_or_persist_credentials(connection_client,payload):
    response=connection_client.put("/api/portfolio/connections/market",json=payload)
    assert response.status_code==422
    assert "never-echo" not in response.text
    assert not connection_store.STORE_PATH.exists()


def test_origin_and_host_checks_block_configuration_changes(connection_client):
    response=connection_client.put("/api/portfolio/connections/market",json={"api_key":"secret"},
                                   headers={"Origin":"https://unrelated.example"})
    assert response.status_code==403
    assert not connection_store.STORE_PATH.exists()
    assert connection_client.get("/api/portfolio/connections",headers={"Host":"unrelated.example"}).status_code==403
    assert connection_client.get("/api/portfolio/connections",headers={"Origin":"http://127.0.0.1:5173"}).status_code==200


def test_nonlocal_client_cannot_change_connections_even_with_loopback_host():
    with TestClient(app,base_url="http://127.0.0.1",client=("198.51.100.8",50000)) as client:
        assert client.put("/api/portfolio/connections/market",json={"api_key":"never-save"}).status_code==403


def test_gemini_model_and_key_apply_without_restart(connection_client,monkeypatch):
    response=connection_client.put("/api/portfolio/connections/agent",json={
        "api_key":"fake-gemini-secret","model":"gemini-3.6-flash"})
    assert response.status_code==200
    agent=response.json()["agent"]
    assert agent["provider"]=="gemini" and agent["configured"]
    assert agent["model"]=="gemini-3.6-flash"
    assert settings.portfolio_model=="gemini-3.6-flash"
    assert "fake-gemini-secret" not in response.text
    import os
    assert "GOOGLE_GENAI_USE_VERTEXAI" not in os.environ
    assert os.environ["SIA_PORTFOLIO_API_KEY"]=="fake-gemini-secret"
    assert not connection_client.delete("/api/portfolio/connections/agent").json()["agent"]["configured"]
    monkeypatch.setenv("GEMINI_API_KEY","legacy-key")
    connection_store.restore_connections()
    assert not connection_client.get("/api/portfolio/connections").json()["agent"]["configured"]


def test_no_network_call_is_made_when_saving(connection_client,monkeypatch):
    def unexpected(*args,**kwargs):
        raise AssertionError("Saving must not contact the provider")
    monkeypatch.setattr(market_data_api,"urlopen",unexpected)
    assert connection_client.put("/api/portfolio/connections/market",json={"api_key":"test-only"}).status_code==200


def test_failed_save_does_not_change_active_key(connection_client,monkeypatch):
    connection_client.put("/api/portfolio/connections/market",json={"api_key":"old-key"})
    def broken(*args,**kwargs):
        raise OSError("private-new-key-or-filesystem-details")
    monkeypatch.setattr(connection_store.Path,"replace",broken)
    response=connection_client.put("/api/portfolio/connections/market",json={"api_key":"new-key"})
    assert response.status_code==500
    assert "private-new-key" not in response.text and "new-key" not in response.text
    import os
    assert os.environ["TWELVE_DATA_API_KEY"]=="old-key"


def test_gemini_connection_test_reports_busy_without_exposing_key(connection_client,monkeypatch):
    from google import genai
    from google.genai import errors
    connection_client.put("/api/portfolio/connections/agent",json={"api_key":"test-gemini-private"})
    class BusyClient:
        def __init__(self,**kwargs):
            assert kwargs["api_key"]=="test-gemini-private"
            self.models=self
        def generate_content(self,**kwargs):
            raise errors.ServerError(503,{"error":{"message":"test-gemini-private","status":"UNAVAILABLE"}})
        def close(self):
            pass
    monkeypatch.setattr(genai,"Client",BusyClient)
    response=connection_client.post("/api/portfolio/connections/agent/test")
    assert response.json()["error"]["code"]=="MODEL_BUSY"
    assert "test-gemini-private" not in response.text


def test_gemini_connection_test_checks_generation(connection_client,monkeypatch):
    from google import genai
    connection_client.put("/api/portfolio/connections/agent",json={"api_key":"test-only"})
    calls=[]
    class GoodClient:
        def __init__(self,**kwargs):
            self.models=self
        def generate_content(self,**kwargs):
            calls.append(kwargs)
            return types.GenerateContentResponse(candidates=[types.Candidate(
                content=types.Content(parts=[types.Part(text="OK")]))])
        def close(self):
            pass
    monkeypatch.setattr(genai,"Client",GoodClient)
    result=connection_client.post("/api/portfolio/connections/agent/test").json()
    assert result["status"]=="success"
    assert calls[0]["model"]=="gemini-3.5-flash-lite"


def test_model_choices_only_offer_reviewed_free_tier_text_models(connection_client):
    options=connection_client.get("/api/portfolio/connections").json()["agent"]["model_options"]
    assert {item["id"] for item in options}=={
        "gemini-3.5-flash-lite","gemini-3.1-flash-lite","gemini-3.6-flash","gemini-3.8-flash"}
    assert all(item["free_tier_available"] for item in options)
    assert [item["id"] for item in options if item["recommended"]]==["gemini-3.5-flash-lite"]


def test_unlisted_model_cannot_replace_the_selected_free_tier_option(connection_client):
    for model in ("gemini-4-argon","gemini-2.5-pro","unknown-model"):
        response=connection_client.put("/api/portfolio/connections/agent",json={
            "model":model,"api_key":"never-persist-this-key"})
        assert response.status_code==422
        assert "never-persist" not in response.text
        assert settings.portfolio_model=="gemini-3.5-flash-lite"
        assert not connection_store.STORE_PATH.exists()



def test_empty_connection_test_returns_without_calling_a_provider(connection_client,monkeypatch):
    from self_improving_ai.dashboard import connections
    def unexpected(*args,**kwargs):
        raise AssertionError("Missing credentials must stop before provider calls")
    monkeypatch.setattr(connections,"test_model_connection",unexpected)
    monkeypatch.setattr(connections,"probe_market_quote",unexpected)
    for tab,code in (("agent","MISSING_MODEL_CONFIGURATION"),("market","MISSING_API_KEY")):
        result=connection_client.post(f"/api/portfolio/connections/{tab}/test",json={}).json()
        assert result["status"]=="error" and result["error"]["code"]==code
    assert not connection_store.STORE_PATH.exists()


def test_gemini_draft_and_saved_keys_follow_model_selection_without_persisting_tests(connection_client,monkeypatch):
    import os

    from google import genai
    seen=[]
    class ProbeClient:
        def __init__(self,**kwargs):
            self.key=kwargs["api_key"]
            assert kwargs["http_options"].retry_options.attempts==1
            assert kwargs["http_options"].timeout==10000
            self.models=self
        def generate_content(self,**kwargs):
            seen.append((self.key,kwargs["model"]))
            return types.GenerateContentResponse(candidates=[types.Candidate(
                content=types.Content(parts=[types.Part(text="OK")]))])
        def close(self):
            pass
    monkeypatch.setattr(genai,"Client",ProbeClient)
    for model in ("gemini-3.5-flash-lite","gemini-3.1-flash-lite"):
        response=connection_client.post("/api/portfolio/connections/agent/test",json={
            "model":model,"api_key":"draft-private-key"})
        assert response.json()["status"]=="success"
        assert response.json()["model"]==model
        assert "draft-private-key" not in response.text
    assert not connection_store.STORE_PATH.exists()
    assert not connection_client.get("/api/portfolio/connections").json()["agent"]["configured"]
    connection_client.put("/api/portfolio/connections/agent",json={
        "api_key":"saved-private-key","model":"gemini-3.5-flash-lite"})
    saved=connection_store.read_connections()
    response=connection_client.post("/api/portfolio/connections/agent/test",json={
        "api_key":None,"model":"gemini-3.6-flash"})
    assert response.json()["status"]=="success"
    assert seen==[("draft-private-key","gemini-3.5-flash-lite"),
                  ("draft-private-key","gemini-3.1-flash-lite"),
                  ("saved-private-key","gemini-3.6-flash")]
    assert connection_store.read_connections()==saved
    assert settings.portfolio_model=="gemini-3.5-flash-lite"
    assert os.environ["SIA_PORTFOLIO_API_KEY"]=="saved-private-key"


def test_market_draft_key_can_be_tested_without_saving(connection_client,monkeypatch):
    def transport(request,**kwargs):
        assert request.get_header("Authorization")=="apikey draft-market-key"
        return io.BytesIO(json.dumps({"symbol":"AAPL","currency":"USD","datetime":"2026-10-30",
                                     "close":"123.45"}).encode())
    monkeypatch.setattr(market_data_api,"urlopen",transport)
    result=connection_client.post("/api/portfolio/connections/market/test",
                                  json={"provider":"twelve_data","api_key":"draft-market-key"})
    assert result.json()["price"]==123.45
    assert "draft-market-key" not in result.text
    assert not connection_store.STORE_PATH.exists()
    assert not connection_client.get("/api/portfolio/connections").json()["market"]["configured"]


@pytest.mark.parametrize("response",[
    types.GenerateContentResponse(),
    types.GenerateContentResponse(candidates=[types.Candidate()]),
    types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(parts=[types.Part(text="hidden reasoning",thought=True)]))]),
])
def test_empty_or_thought_only_model_probe_is_not_a_verified_connection(connection_client,monkeypatch,response):
    from google import genai
    class EmptyClient:
        def __init__(self,**kwargs):
            self.models=self
        def generate_content(self,**kwargs):
            return response
        def close(self):
            pass
    monkeypatch.setattr(genai,"Client",EmptyClient)
    result=connection_client.post("/api/portfolio/connections/agent/test",
                                 json={"api_key":"offline-only"}).json()
    assert result["status"]=="error"
    assert result["error"]["code"]=="EMPTY_MODEL_RESPONSE"


@pytest.mark.parametrize("tab,code",[("agent","MODEL_TIMEOUT"),("market","TIMEOUT")])
def test_connection_probe_has_an_overall_deadline(connection_client,monkeypatch,tab,code):
    import asyncio

    from self_improving_ai.dashboard import connections
    cancelled=[]
    async def never_finishes(*args,**kwargs):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)
    monkeypatch.setattr(connections,"run_in_threadpool",never_finishes)
    monkeypatch.setattr(connections,"TEST_TIMEOUT_SECONDS",.01)
    result=connection_client.post(f"/api/portfolio/connections/{tab}/test",
                                  json={"api_key":"offline-test-key"}).json()
    assert result["error"]["code"]==code
    assert result["error"]["retryable"]
    assert cancelled
    assert not connection_store.STORE_PATH.exists()

