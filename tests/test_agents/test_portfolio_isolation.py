"""Shared team settings remain intact when the independent A connection changes."""
import json

from fastapi.testclient import TestClient

from self_improving_ai import connection_store
from self_improving_ai.agents.portfolio.agent import create_portfolio_agent
from self_improving_ai.agents.portfolio.model_settings import portfolio_api_key
from self_improving_ai.agents.portfolio.schemas import PortfolioResult
from self_improving_ai.config import settings
from self_improving_ai.dashboard.app import app


def test_a_save_remove_and_restore_leave_shared_model_key_and_vertex_unchanged(tmp_path,monkeypatch):
    monkeypatch.setattr(connection_store,"STORE_PATH",tmp_path/"connections.json")
    monkeypatch.setattr(settings,"agent_model","shared-team-model")
    monkeypatch.setattr(settings,"judge_model","shared-team-judge")
    monkeypatch.setattr(settings,"portfolio_model","gemini-3.5-flash-lite")
    monkeypatch.setenv("GOOGLE_API_KEY","shared-team-key")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI","TRUE")
    for key in ("SIA_PORTFOLIO_API_KEY","SIA_PORTFOLIO_MODEL"):
        monkeypatch.setenv(key,"")
        monkeypatch.delenv(key)
    assert portfolio_api_key()=="shared-team-key"
    with TestClient(app,base_url="http://127.0.0.1",client=("127.0.0.1",50000)) as client:
        result=client.put("/api/portfolio/connections/agent",json={
            "api_key":"separate-portfolio-key","model":"gemini-3.6-flash"})
        assert result.status_code==200
        agent=create_portfolio_agent()
        assert agent.model.model=="gemini-3.6-flash"
        assert agent.model.api_key.get_secret_value()=="separate-portfolio-key"
        assert "separate-portfolio-key" not in repr(agent)
        assert "separate-portfolio-key" not in json.dumps(agent.model.model_dump())
        assert client.delete("/api/portfolio/connections/agent").status_code==200
        connection_store.restore_connections()
        assert portfolio_api_key()==""
    import os
    assert settings.agent_model=="shared-team-model"
    assert settings.judge_model=="shared-team-judge"
    assert os.environ["GOOGLE_API_KEY"]=="shared-team-key"
    assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"]=="TRUE"
    saved=connection_store.read_connections()
    assert not {"GOOGLE_API_KEY","GEMINI_API_KEY","GOOGLE_GENAI_USE_VERTEXAI","SIA_AGENT_MODEL"}&saved.keys()


def test_explicit_portfolio_client_uses_its_own_key_and_developer_api(monkeypatch):
    from self_improving_ai.agents.portfolio import model_settings
    monkeypatch.setenv("GOOGLE_API_KEY","team-key")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI","TRUE")
    monkeypatch.setenv("SIA_PORTFOLIO_API_KEY","isolated-key")
    calls=[]
    def client(**kwargs):
        calls.append(kwargs)
        return object()
    monkeypatch.setattr(model_settings,"Client",client)
    agent=create_portfolio_agent()
    _=agent.model.api_client
    assert calls[0]["api_key"]=="isolated-key"
    assert calls[0]["vertexai"] is False


def test_legacy_portfolio_result_schema_still_accepts_original_team_payload():
    result=PortfolioResult(answer_value=123.4,unit="USD",reasoning="Fixture calculation")
    assert result.answer_value==123.4
