"""Regression checks for external-source and independent-review boundaries."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest
from self_improving_ai.agents.briefing.service import generate_meeting_brief
from self_improving_ai.agents.briefing.store import DraftStore
from self_improving_ai.config import settings
from self_improving_ai.dashboard.app import app
from self_improving_ai.tools.briefing.news import fixture_news, search_market_news


@pytest.mark.parametrize("offline", ["decorator", "configuration", "operational_scope"])
def test_offline_news_never_calls_the_provider_when_a_key_is_present(monkeypatch, offline):
    from contextlib import nullcontext

    from self_improving_ai.tools.briefing.workspace_sources import operational_scope

    monkeypatch.setenv("TWELVE_DATA_API_KEY", "test-key-not-a-secret")
    monkeypatch.setattr(settings, "briefing_news_source", "fixture" if offline == "configuration" else "auto")
    scope = fixture_news() if offline == "decorator" else operational_scope("CLI-001", "2026-11-11", ai_mode=False, records=[]) if offline == "operational_scope" else nullcontext()
    with scope, patch("self_improving_ai.tools.briefing.news_api.fetch_market_news") as fetch:
        fetch.return_value = {"status": "ok", "results": []}
        result = search_market_news("retirement", 3)
    fetch.assert_not_called()
    assert result["results"] == []


def test_news_provider_failure_is_not_reported_as_a_successful_empty_search(monkeypatch):
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "test-key-not-a-secret")
    monkeypatch.setattr(settings, "briefing_news_source", "live")
    error = {"status": "error", "error": {"code": "RATE_LIMITED", "message": "Test quota error", "retryable": True}}
    with patch("self_improving_ai.tools.briefing.news_api.fetch_market_news", return_value=error):
        result = search_market_news("retirement", 3)
    assert result["status"] == "error"
    assert result["error"]["code"] == "RATE_LIMITED"
    assert result["results"] == []


@pytest.mark.parametrize("endpoint", ["check", "review"])
def test_invalid_semantic_review_cannot_pass_or_approve_an_ai_brief(tmp_path, monkeypatch, endpoint):
    monkeypatch.setattr(settings, "db_path", tmp_path / "review.db")
    original = generate_meeting_brief(MeetingBriefRequest(client_id="CLI-003", meeting_date="2026-11-11",
        meeting_time="14:00", focus="Retirement planning"))
    original["mode"] = "agent"
    store = DraftStore()
    store.create(original)
    payload = {"brief": deepcopy(original)}
    if endpoint == "review":
        payload.update(revision=1, expected_revision=1, decision="approve")
    with patch("self_improving_ai.agents.briefing.runtime.semantic_check", new=AsyncMock(side_effect=ValueError("Malformed model review"))):
        http = TestClient(app)
        try:
            response = http.post(f"/api/briefings/{endpoint}", json=payload)
        finally:
            http.close()
    assert response.status_code == 502
    assert store.get(original["id"])["status"] == "draft"
