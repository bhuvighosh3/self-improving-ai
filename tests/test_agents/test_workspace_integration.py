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
from self_improving_ai.agents.briefing.store import DraftStore

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


def test_calendar_type_is_optional_and_existing_metadata_survives_editing(workspace):
    http, _ = workspace
    untyped = {key: value for key, value in EVENT.items() if key != "type"}
    created = http.post("/api/calendar/events", json=untyped)
    assert created.status_code == 201, created.text
    assert created.json()["type"] == "general_meeting"
    legacy = http.post("/api/calendar/events", json=EVENT).json()
    edited = http.put(f"/api/calendar/events/{legacy['id']}", json={"title": "Updated meeting title"})
    assert edited.status_code == 200
    assert edited.json()["type"] == EVENT["type"]
    assert edited.json()["date"] == EVENT["date"]
    assert edited.json()["start_time"] == EVENT["start_time"]


def test_copilot_saved_brief_is_visible_in_meeting_workspace_without_regeneration(workspace):
    http, monitor = workspace
    before = http.get("/api/calendar/events?year=2026&month=11").json()
    response = http.post("/api/chat", json={"message": "prepare a meeting prep for Thompson Trust"})
    assert response.status_code == 200, response.text
    brief = response.json()["brief"]
    state = monitor.state()
    jobs = [job for job in state["preparations"] if job["event_id"] == "EVT-e5f6a7b8" and job["status"] == "ready"]
    assert len(jobs) == 1, "The calendar preparation index must include a brief generated in Copilot"
    assert jobs[0]["brief_id"] == brief["id"]
    with patch("self_improving_ai.dashboard.app.generate_meeting_brief") as generate:
        reopened = http.get(f"/api/meeting-preparations/{jobs[0]['id']}/brief")
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()["id"] == brief["id"]
        generate.assert_not_called()
    assert http.get("/api/calendar/events?year=2026&month=11").json() == before
    switched = http.post("/api/meeting-preparations/simulation", json={"action": "pause", "mode": "agent"}).json()
    assert any(job["brief_id"] == brief["id"] and job["status"] == "ready" for job in switched["preparations"])


def test_unlinked_earlier_brief_is_recovered_without_changing_reviewed_content(workspace):
    http, monitor = workspace
    request = MeetingBriefRequest(client_id="CLI-002", meeting_date="2026-11-14", meeting_time="10:00", focus="Bond discussion")
    with operational_scope(request.client_id, "2026-11-11"):
        brief = generate_meeting_brief(request)
    store = DraftStore(settings.db_path)
    store.create(brief)
    before = store.get(brief["id"])
    store.review(brief, 1, 1, "approve", "Reviewed before calendar linking")
    state = monitor.state()
    job = next(job for job in state["preparations"] if job["brief_id"] == brief["id"])
    assert job["event_id"] == "EVT-e5f6a7b8" and job["status"] == "ready"
    assert store.get(brief["id"])["digest"] == before["digest"]
    assert store.get(brief["id"])["status"] == "approve"
    assert http.get(f"/api/meeting-preparations/{job['id']}/brief").json() == brief
    http.put("/api/calendar/events/EVT-e5f6a7b8", json={"notes": "A changed meeting topic"})
    assert http.get(f"/api/meeting-preparations/{job['id']}/brief").status_code == 409


def test_new_preparation_creates_one_calendar_meeting_and_reuses_its_brief(workspace):
    http, monitor = workspace
    before = http.get("/api/calendar/events?year=2026&month=11").json()
    request = {"client_id": "CLI-002", "meeting_date": "2026-11-16",
        "meeting_time": "13:15", "focus": "Discuss new client questions", "mode": "simulation"}
    response = http.post("/api/briefings", json=request)
    assert response.status_code == 200, response.text
    brief = response.json()
    after = http.get("/api/calendar/events?year=2026&month=11").json()
    assert len(after) == len(before) + 1
    event = next(event for event in after if event["id"] == brief["calendar_event"]["id"])
    assert event["date"] == request["meeting_date"] and event["start_time"] == request["meeting_time"]
    assert event["notes"] == request["focus"]
    assert not monitor.state().get("saved_meetings")
    with patch("self_improving_ai.dashboard.app.generate_meeting_brief") as generate:
        repeated = http.post("/api/briefings", json=request)
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["id"] == brief["id"]
        generate.assert_not_called()
    assert http.get(f"/api/briefings/{brief['id']}").json()["id"] == brief["id"]


def test_editing_a_prepared_meeting_refreshes_the_same_meeting_even_outside_the_window(workspace):
    http, monitor = workspace
    event = http.post("/api/calendar/events", json={**EVENT, "date": "2026-11-24"}).json()
    job = http.post(f"/api/meeting-preparations/events/{event['id']}").json()
    asyncio.run(monitor.tick())
    old = http.get(f"/api/meeting-preparations/{job['id']}/brief").json()
    change = {"title": "Updated home funding review", "date": "2026-11-25", "start_time": "15:00",
        "end_time": "15:45", "notes": "Confirm revised home budget and timing", "location": "Video call"}
    assert http.put(f"/api/calendar/events/{event['id']}", json=change).status_code == 200
    state = monitor.state()
    jobs = [row for row in state["preparations"] if row["event_id"] == event["id"]]
    assert len(jobs) == 1 and jobs[0]["status"] == "queued"
    assert http.get(f"/api/meeting-preparations/{job['id']}/brief").status_code == 409
    assert http.post("/api/briefings/check", json={"brief": old}).status_code == 422
    assert http.post("/api/briefings/review", json={"brief": old, "revision": 1,
        "expected_revision": 1, "decision": "approve"}).status_code == 409
    asyncio.run(monitor.tick())
    current = next(row for row in monitor.state()["preparations"] if row["event_id"] == event["id"])
    updated = http.get(f"/api/meeting-preparations/{current['id']}/brief").json()
    assert updated["id"] != old["id"]
    assert updated["calendar_event"]["id"] == event["id"]
    assert updated["meeting_date"] == change["date"] and updated["meeting_time"] == change["start_time"]
    assert updated["focus"] == change["notes"] and updated["calendar_event"]["location"] == change["location"]
    assert DraftStore(settings.db_path).get(old["id"])["brief"] == old


def test_edit_during_generation_does_not_publish_an_obsolete_brief(workspace):
    http, monitor = workspace
    event = http.post("/api/calendar/events", json=EVENT).json()
    def edit_then_generate(request):
        assert http.put(f"/api/calendar/events/{event['id']}", json={"notes": "Updated during preparation"}).status_code == 200
        return generate_meeting_brief(request)
    with patch("self_improving_ai.dashboard.app.generate_meeting_brief", side_effect=edit_then_generate):
        response = http.post("/api/briefings", json={"calendar_event_id": event["id"],
            "client_id": EVENT["client_id"], "meeting_date": EVENT["date"], "meeting_time": EVENT["start_time"],
            "focus": EVENT["notes"], "mode": "simulation"})
    assert response.status_code == 422
    assert not DraftStore(settings.db_path).summaries()
    assert not any(job["status"] == "ready" for job in monitor.state()["preparations"])
    assert next(job for job in monitor.state()["preparations"] if job["event_id"] == event["id"])["status"] == "queued"
    asyncio.run(monitor.tick())
    assert next(job for job in monitor.state()["preparations"] if job["event_id"] == event["id"])["status"] == "ready"


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
