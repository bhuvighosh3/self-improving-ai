"""Regression checks for actionable model failures without credential disclosure."""
import json

import pytest
from google.genai import errors

from self_improving_ai.agents.portfolio.model_errors import classify_model_error
from self_improving_ai.agents.portfolio.service import run_portfolio_agent
from tests.test_agents.test_portfolio_agent import ScriptedModel


@pytest.mark.parametrize("status,code,retryable",[
    (503,"MODEL_BUSY",True),(429,"MODEL_RATE_LIMITED",True),
    (401,"MODEL_AUTHENTICATION_FAILED",False),(403,"MODEL_ACCESS_DENIED",False),
    (404,"MODEL_NOT_FOUND",False),(400,"MODEL_INVALID_REQUEST",False),
])
def test_provider_errors_are_specific_and_do_not_echo_credentials(status,code,retryable):
    kind=errors.ServerError if status>=500 else errors.ClientError
    exc=kind(status,{"error":{"message":"sensitive-provider-detail-abc","status":"UNAVAILABLE"}})
    result=classify_model_error(exc)
    assert result["error"]["code"]==code
    assert result["error"]["retryable"]==retryable
    assert result["error"]["provider_http_status"]==status
    assert result["source"]=="gemini"
    assert "sensitive-provider-detail" not in json.dumps(result)


def test_timeout_is_distinct_from_authentication():
    result=classify_model_error(TimeoutError("do not expose this"))
    assert result["error"]["code"]=="MODEL_TIMEOUT"
    assert result["error"]["retryable"]


@pytest.mark.asyncio
async def test_agent_reports_busy_instead_of_generic_configuration_failure(monkeypatch):
    from self_improving_ai.agents.portfolio import agent
    def busy(*args):
        raise errors.ServerError(503,{"error":{"message":"temporary overload","status":"UNAVAILABLE"}})
    monkeypatch.setattr(agent,"create_portfolio_agent",busy)
    run=await run_portfolio_agent("Show CLI-001 allocation",model=ScriptedModel())
    assert run["status"]=="error"
    assert run["result"]["error"]["code"]=="MODEL_BUSY"
    assert run["trace"]==[]

