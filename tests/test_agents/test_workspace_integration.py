"""Canonical Calendar/Inbox persistence and Part B evidence integration."""

import asyncio
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from google.genai.errors import ServerError
import pytest

from self_improving_ai.config import settings
from self_improving_ai.dashboard.app import app, create_meeting_brief
from self_improving_ai.dashboard.preparation import MeetingPreparationMonitor
from self_improving_ai.workspace_store import LocalWorkspaceStore, invalidate_snapshots
from self_improving_ai.tools.briefing.workspace_sources import operational_scope
from self_improving_ai.tools.briefing.context import load_context, search_sources, read_source
from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest
from self_improving_ai.agents.briefing.service import generate_meeting_brief

EVENT = {"title":"Home funding confirmation", "client_id":"CLI-004", "date":"2026-11-12",
         "start_time":"16:00", "end_time":"16:45", "type":"goal_review", "notes":"Confirm current purchase timing"}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    path = tmp_path / "workspace.db"
    monkeypatch.setattr(settings, "db_path", path)
    monkeypatch.setattr(settings, "workspace_store", "local")
    monkeypatch.setattr(settings, "briefing_news_source", "fixture")
    monitor = MeetingPreparationMonitor(path, create_meeting_brief)
    monkeypatch.setattr(app.state, "preparations", monitor, raising=False)
    invalidate_snapshots()
    http = TestClient(app)
    http.post("/api/meeting-preparations/simulation", json={"action":"pause"})
    try:
        yield http, monitor
    finally:
        http.close()
        invalidate_snapshots()


def test_calendar_crud_and_preparation_use_one_event_record(workspace):
    http, monitor = workspace
    created = http.post("/api/calendar/events", json=EVENT)
    assert created.status_code == 201, created.text
    event = created.json()
    assert event["id"] in {row["id"] for row in http.get("/api/calendar/events?year=2026&month=11").json()}
    normalized = next(row for row in monitor.state()["events"] if row["id"] == event["id"])
    assert normalized["focus"] == EVENT["notes"] and normalized["meeting_type"] == "goal_review"
    queued = http.post(f"/api/meeting-preparations/events/{event['id']}").json()
    assert queued["status"] == "queued"
    asyncio.run(monitor.tick())
    brief = http.get(f"/api/meeting-preparations/{queued['id']}/brief").json()
    assert brief["meeting_time"] == "16:00"
    assert "EML-a3b4c5d6" in {source["id"] for source in brief["sources"]}
    assert brief["workflow"]["quality"]["verdict"] == "pass"
    assert http.put(f"/api/calendar/events/{event['id']}", json={"start_time":"16:15"}).status_code == 200
    assert http.get(f"/api/meeting-preparations/{queued['id']}/brief").status_code == 409
    assert http.delete(f"/api/calendar/events/{event['id']}").status_code == 204
    assert http.post(f"/api/meeting-preparations/events/{event['id']}").status_code == 404


@pytest.mark.parametrize("change", [{"date":"2026-02-30"},{"start_time":"27:00"},{"end_time":"15:00"},{"client_id":"CLI-999"}])
def test_invalid_calendar_records_are_rejected_before_storage(workspace, change):
    http, _ = workspace
    assert http.post("/api/calendar/events", json={**EVENT,**change}).status_code == 422
    created = http.post("/api/calendar/events", json=EVENT).json()
    assert http.put(f"/api/calendar/events/{created['id']}", json=change).status_code == 422
    assert http.get(f"/api/calendar/events/{created['id']}").json()["start_time"] == "16:00"


def test_inbox_is_client_scoped_original_evidence_with_cutoff_and_draft_boundaries(workspace):
    _, _ = workspace
    store = LocalWorkspaceStore("email", settings.db_path)
    future = store.create_email({"subject":"Future plan", "client_id":"CLI-004", "body":"Do not read yet", "folder":"inbox"})
    store.update_email(future["id"], {"date":"2026-12-30"})
    draft = store.create_email({"subject":"Unsent plan", "client_id":"CLI-004", "body":"Draft only", "folder":"drafts"})
    late = store.create_email({"subject":"Backdated plan", "client_id":"CLI-004", "body":"Ingested later", "folder":"inbox"})
    store.update_email(late["id"], {"date":"2026-11-01","created_at":"2026-12-30T12:00:00Z"})
    with operational_scope("CLI-004","2026-11-11"):
        ids = {hit["id"] for hit in search_sources("CLI-004")["hits"]}
        assert "EML-a3b4c5d6" in ids
        assert not {future["id"],draft["id"],late["id"],"EML-e7f8a9b0","EML-c1d2e3f4"} & ids
        original = read_source("CLI-004","EML-a3b4c5d6")["record"]
        assert original["origin"] == "workspace_inbox" and "mid-December" in original["text"]
        assert read_source("CLI-004","EML-e7f8a9b0")["status"] == "denied"
        with pytest.raises(ValueError):
            search_sources("CLI-005")
    with operational_scope("CLI-004","2026-10-27"):
        assert read_source("CLI-004","EML-a3b4c5d6")["status"] == "denied"
    assert load_context("CLI-004")["as_of"] == "2026-10-27"


def test_new_mail_invalidates_ready_preparation_but_read_star_archive_do_not(workspace):
    http, monitor = workspace
    event_id = "EVT-a1b2c3d4"
    job = http.post(f"/api/meeting-preparations/events/{event_id}").json()
    asyncio.run(monitor.tick())
    before = next(event for event in monitor.events if event["id"] == event_id)["version"]
    assert http.patch("/api/email/messages/EML-a1b2c3d4",json={"read":True,"starred":True,"folder":"archive"}).status_code == 200
    assert next(event for event in monitor.events if event["id"] == event_id)["version"] == before
    assert http.get(f"/api/meeting-preparations/{job['id']}/brief").status_code == 200
    created = http.post("/api/email/messages",json={"subject":"Confirm college discussion", "to_name":"Garcia Family",
        "to_addr":"garcia@example.com", "body":"Please confirm the college discussion agenda", "client_id":"CLI-001"})
    assert created.status_code == 201
    after = next(event for event in monitor.events if event["id"] == event_id)["version"]
    assert before != after
    assert http.get(f"/api/meeting-preparations/{job['id']}/brief").status_code == 409
    replacement = http.post(f"/api/meeting-preparations/events/{event_id}").json()
    assert replacement["id"] != job["id"]
    asyncio.run(monitor.tick())
    brief = http.get(f"/api/meeting-preparations/{replacement['id']}/brief").json()
    assert created.json()["id"] in {source["id"] for source in brief["sources"]}


def test_scope_freezes_mail_content_and_keeps_reported_amounts_separate_from_holdings(workspace):
    _, _ = workspace
    store = LocalWorkspaceStore("email", settings.db_path)
    with operational_scope("CLI-005","2026-11-11"):
        old_revision = load_context("CLI-005")["context_revision"]
        original = read_source("CLI-005","EML-e7f8a9b0")["record"]["text"]
        store.update_email("EML-e7f8a9b0",{"body":"Changed while preparing"})
        assert read_source("CLI-005","EML-e7f8a9b0")["record"]["text"] == original
        brief = generate_meeting_brief(MeetingBriefRequest(client_id="CLI-005",meeting_date="2026-11-22",meeting_time="09:00",focus="Withdrawal planning"))
        assert brief["workflow"]["quality"]["verdict"] == "pass"
        confirm = next(section for section in brief["sections"] if section["id"] == "confirm")
        assert any(item["id"] == "mail-verification" for item in confirm["items"])
    with operational_scope("CLI-005","2026-11-11"):
        assert load_context("CLI-005")["context_revision"] != old_revision


def test_explicit_firestore_configuration_failure_is_visible_without_local_fallback(workspace, monkeypatch):
    http, _ = workspace
    from self_improving_ai import workspace_store
    real_store = workspace_store._store
    def unavailable(kind, backend, path, project):
        if backend == "firestore":
            raise RuntimeError("Private provider details must stay private")
        return real_store(kind, backend, path, project)
    monkeypatch.setattr(settings,"workspace_store","firestore")
    monkeypatch.setattr(workspace_store,"_store",unavailable)
    invalidate_snapshots()
    for url in ["/api/calendar/events","/api/email/messages","/api/meeting-preparations"]:
        response = http.get(url)
        assert response.status_code == 503
        assert "Private provider" not in response.text
    assert http.get("/api/health").status_code == 200


def test_typed_provider_fallback_records_effective_model_and_never_uses_offline(workspace, monkeypatch):
    http, _ = workspace
    request = {"client_id":"CLI-004","meeting_date":"2026-11-20","meeting_time":"15:30","focus":"Home funding","mode":"agent"}
    brief = generate_meeting_brief(MeetingBriefRequest(**{**request,"mode":"simulation"}))
    brief["mode"] = "agent"
    brief["workflow"]["model"] = "fallback-test"
    monkeypatch.setattr(settings,"agent_model","primary-test")
    monkeypatch.setattr(settings,"agent_model_fallback","fallback-test")
    with patch("self_improving_ai.agents.briefing.runtime.generate_agent_brief",new=AsyncMock(side_effect=[ServerError(503,{"error":{"message":"Busy"}}),brief])) as generate, patch("self_improving_ai.dashboard.app.generate_meeting_brief") as offline:
        response = http.post("/api/briefings",json=request)
        assert response.status_code == 200, response.text
        assert response.json()["workflow"]["model"] == "fallback-test"
        assert response.json()["workflow"]["model_fallback_from"] == "primary-test"
        assert generate.await_args_list[1].kwargs == {"model":"fallback-test"}
        offline.assert_not_called()
