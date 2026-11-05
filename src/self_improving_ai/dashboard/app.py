"""FastAPI backend for the self-improving AI dashboard."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=True)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from self_improving_ai.agents.orchestrator.agent import orchestrator
from self_improving_ai.config import settings
from self_improving_ai.agents.briefing.schemas import BriefExportRequest, MeetingBriefRequest
from self_improving_ai.agents.briefing.pdf import render_brief_pdf
from self_improving_ai.agents.briefing.service import generate_meeting_brief
from self_improving_ai.dashboard.meeting_requests import collect_meeting_details
from self_improving_ai.agents.briefing.workflow_models import CheckRequest, ReviewRequest
from self_improving_ai.agents.briefing.store import DraftStore
from self_improving_ai.agents.briefing.review import check_draft

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

log = logging.getLogger(__name__)

app = FastAPI(title="Self-Improving AI Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

_session_service = InMemorySessionService()
_runner = Runner(
    app_name=orchestrator.name,
    agent=orchestrator,
    session_service=_session_service,
)
_sessions: dict[str, str] = {}


async def _get_or_create_session(user_id: str) -> str:
    if user_id not in _sessions:
        session = await _session_service.create_session(
            app_name=orchestrator.name,
            user_id=user_id,
            state={
                "intent_corrections": "",
                "tool_notes": "",
                "plan_templates": "",
                "advisor_corrections": "",
                "context_preferences": "",
                "relevant_lessons": "",
                "skill_procedures": "",
                "tool_preferences": "",
            },
        )
        _sessions[user_id] = session.id
    return _sessions[user_id]


def _load(relpath: str):
    path = _DATA_DIR / relpath
    if path.exists():
        return json.loads(path.read_text())
    return []


class ChatRequest(BaseModel):
    message: str
    client_id: str | None = None
    meeting: MeetingBriefRequest | None = None


@app.post("/api/briefings")
async def create_meeting_brief(req: MeetingBriefRequest):
    try:
        if req.mode == "agent":
            from self_improving_ai.agents.briefing.runtime import generate_agent_brief

            brief = await asyncio.wait_for(generate_agent_brief(req), timeout=180)
        else:
            brief = await asyncio.to_thread(generate_meeting_brief, req)
        await asyncio.to_thread(DraftStore().create, brief)
        return brief
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Agent timed out; no approved brief was created.") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Agent service unavailable. Check backend credentials or explicitly select Offline demo.") from exc


@app.post("/api/briefings/check")
async def check_meeting_draft(req: CheckRequest):
    try:
        original = DraftStore().get(req.brief["id"])["brief"]
        return await asyncio.wait_for(check_draft(req.brief, original), timeout=90)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Quality reviewer unavailable; draft was not approved.") from exc


@app.post("/api/briefings/review")
async def review_meeting_draft(req: ReviewRequest):
    try:
        store = DraftStore()
        original = store.get(req.brief["id"])["brief"]
        report = await asyncio.wait_for(check_draft(req.brief, original), timeout=90)
        if req.decision == "approve" and report["verdict"] != "pass":
            raise ValueError("Quality check requires revision before approval")
        # Browser-provided workflow/sources can never replace the retained originals.
        retained = {**original, "sections": req.brief["sections"]}
        retained["workflow"] = {**original["workflow"], "quality": report}
        return store.review(retained, req.revision, req.expected_revision,
                            req.decision, req.feedback)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Review failed; no approval was recorded.") from exc


@app.get("/api/briefings/{brief_id}/approved")
async def get_approved_brief(brief_id: str):
    try:
        result = DraftStore().get(brief_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if result["status"] != "approve":
        raise HTTPException(status_code=409, detail="This draft has not been approved")
    return result


@app.post("/api/briefings/export")
async def export_meeting_brief(req: BriefExportRequest):
    try:
        pdf = render_brief_pdf(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="meeting-brief-{req.brief.meeting_date}.pdf"',
    })


@app.get("/api/health")
async def health():
    return {"status": "ok", "model": settings.agent_model}


@app.get("/api/clients")
async def list_clients():
    return _load("clients/households.json")


@app.get("/api/clients/{client_id}")
async def get_client(client_id: str):
    for h in _load("clients/households.json"):
        if h.get("client_id") == client_id:
            return h
    return {"error": "Client not found"}


@app.get("/api/requests")
async def list_requests():
    return _load("requests/advisor_requests.json")


@app.get("/api/tools")
async def list_tools():
    return _load("tool_catalog.json")


@app.get("/api/news")
async def list_news():
    return _load("news/market_news.json")


@app.get("/api/prices")
async def get_prices():
    return _load("prices/price_history.json")


@app.get("/api/stats")
async def get_stats():
    clients = _load("clients/households.json")
    requests = _load("requests/advisor_requests.json")
    tools = _load("tool_catalog.json")

    total_aum = 0
    total_accounts = 0
    for c in clients:
        for acct in c.get("accounts", []):
            total_accounts += 1
            for h in acct.get("holdings", []):
                total_aum += h.get("market_value", 0)

    intent_counts = {}
    agent_counts = {}
    for r in requests:
        intent = r.get("intent", "unknown")
        intent_counts[intent] = intent_counts.get(intent, 0) + 1
        for a in r.get("expected_agents", []):
            agent_counts[a] = agent_counts.get(a, 0) + 1

    return {
        "total_aum": total_aum,
        "total_clients": len(clients),
        "total_accounts": total_accounts,
        "total_requests": len(requests),
        "total_tools": len(tools),
        "intent_breakdown": intent_counts,
        "agent_usage": agent_counts,
        "agents": [
            {
                "name": "Portfolio Estimation Agent",
                "id": "portfolio_estimation_agent",
                "status": "active",
                "model": settings.agent_model,
                "tools": len([t for t in tools if t.get("agent") == "portfolio_estimation_agent"]),
            },
            {
                "name": "Meeting Briefing Agent",
                "id": "meeting_briefing_agent",
                "status": "active",
                "model": settings.agent_model,
                "tools": len([t for t in tools if t.get("agent") == "meeting_briefing_agent"]),
            },
            {
                "name": "Request Orchestrator",
                "id": "request_orchestrator",
                "status": "active",
                "model": settings.agent_model,
                "tools": len([t for t in tools if t.get("agent") == "request_orchestrator"]),
            },
        ],
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if req.meeting is not None:
        brief = await create_meeting_brief(req.meeting)
        sections = {section["id"]: section for section in brief["sections"]}
        highlights = sections["portfolio"]["items"]
        response_text = (
            f"**Meeting brief prepared: {brief['client_name']}**\n\n"
            f"{brief['meeting_date']} at {brief['meeting_time']} · New York\n\n"
            f"**Focus:** {brief['focus']}\n\n"
            f"**Portfolio:** {highlights[0]['text']}\n\n"
            + (highlights[1]["text"] + "\n\n" if len(highlights) > 1 else "")
            + "**Discussion priorities:**\n"
            + "\n".join(f"- {item['title']}" for item in sections["priorities"]["items"])
            + "\n\nOpen this brief to inspect sources, edit, review, or export it."
        )
        return {
            "response": response_text, "intent": "meeting_briefing",
            "client_id": brief["client_id"], "mode": brief["mode"], "brief": brief,
            "agents_used": ["meeting_briefing_agent"],
            "steps": [{"agent": "meeting_briefing_agent", "action": "build_briefing",
                       "detail": f"Prepared six sections from {len(brief['sources'])} mock sources",
                       "tools_called": brief["tools_called"]}],
        }

    user_id = "advisor-001"
    session_id = await _get_or_create_session(user_id)

    message = req.message
    if req.client_id:
        message += f" (client_id: {req.client_id})"

    content = types.Content(
        role="user",
        parts=[types.Part(text=message)],
    )

    steps = []
    response_parts = []

    try:
        async for event in _runner.run_async(
            session_id=session_id,
            user_id=user_id,
            new_message=content,
        ):
            author = event.author or "unknown"
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        steps.append({
                            "agent": author,
                            "action": fc.name,
                            "detail": f"Called {fc.name}",
                            "tools_called": [fc.name],
                        })
                    elif hasattr(part, "text") and part.text:
                        response_parts.append(part.text)
    except Exception as exc:
        log.exception("Orchestrator error")
        err = str(exc)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            response_parts.append("Rate limit reached — the free Gemini tier allows 5 requests/minute. Please wait a moment and try again.")
        else:
            response_parts.append("The orchestrator encountered an error. Please try again.")

    agents_used = list({s["agent"] for s in steps})
    if not agents_used:
        agents_used = ["request_orchestrator"]

    response_text = response_parts[-1] if response_parts else "I'm not sure how to help with that. Could you rephrase?"

    return {
        "response": response_text,
        "intent": "gemini",
        "agents_used": agents_used,
        "client_id": req.client_id,
        "steps": steps,
        "mode": "live",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.fastapi_port)
