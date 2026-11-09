"""FastAPI backend for the self-improving AI dashboard."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=True)

from self_improving_ai.connection_store import restore_connections

restore_connections()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.genai.errors import APIError

from self_improving_ai.agents.orchestrator.agent import orchestrator
from self_improving_ai.agents.orchestrator.runtime import run_copilot
from self_improving_ai.config import settings
from self_improving_ai.agents.briefing.schemas import BriefExportRequest, MeetingBriefRequest
from self_improving_ai.agents.briefing.pdf import render_brief_pdf
from self_improving_ai.agents.briefing.service import generate_meeting_brief
from self_improving_ai.dashboard.meeting_requests import collect_meeting_details, is_meeting_request
from self_improving_ai.tools.orchestrator.catalog import search_tool_catalog
from self_improving_ai.agents.briefing.workflow_models import CheckRequest, ReviewRequest
from self_improving_ai.agents.briefing.store import DraftStore
from self_improving_ai.agents.briefing.review import check_draft

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app):
    from self_improving_ai.dashboard.preparation import MeetingPreparationMonitor
    from self_improving_ai.telemetry import init_telemetry

    init_telemetry()
    log.info("Telemetry initialized (exporter=%s)", settings.otel_exporter)

    app.state.preparations = MeetingPreparationMonitor(settings.db_path, create_meeting_brief)
    worker = asyncio.create_task(app.state.preparations.serve())
    try:
        yield
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


app = FastAPI(title="Self-Improving AI Dashboard", version="0.1.0", lifespan=lifespan)

from self_improving_ai.dashboard.preparation import router as preparation_router
app.include_router(preparation_router)

from self_improving_ai.dashboard.portfolio import router as portfolio_router

app.include_router(portfolio_router)

from self_improving_ai.dashboard.connections import router as connections_router

app.include_router(connections_router)

from self_improving_ai.dashboard.calendar import router as calendar_router

app.include_router(calendar_router)

from self_improving_ai.dashboard.email import router as email_router

app.include_router(email_router)

from self_improving_ai.client_store import load_households as _load_clients

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

_fallback_runner = None


def _get_fallback_runner():
    global _fallback_runner
    if _fallback_runner is None:
        from google.adk import Agent
        from google.adk.tools.agent_tool import AgentTool
        from self_improving_ai.agents.orchestrator.instructions import ORCHESTRATOR_INSTRUCTION
        from self_improving_ai.agents.portfolio.agent import create_portfolio_agent
        from self_improving_ai.agents.briefing.agent import briefing_agent

        from self_improving_ai.tools.orchestrator.workspace import (
            get_client_holdings, get_client_info, get_crm_summary,
            get_recent_emails, get_upcoming_events,
        )
        fallback_orchestrator = Agent(
            name="request_orchestrator",
            model=settings.agent_model_fallback,
            instruction=ORCHESTRATOR_INSTRUCTION,
            tools=[
                get_upcoming_events, get_recent_emails, get_client_info,
                get_crm_summary, get_client_holdings,
                AgentTool(agent=create_portfolio_agent(settings.agent_model_fallback)),
                AgentTool(agent=briefing_agent),
                search_tool_catalog,
            ],
            output_key="orchestrator_result",
        )
        _fallback_runner = Runner(
            app_name=fallback_orchestrator.name,
            agent=fallback_orchestrator,
            session_service=_session_service,
        )
    return _fallback_runner


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
        return json.loads(path.read_text(encoding="utf-8"))
    return []


class ChatRequest(BaseModel):
    message: str
    client_id: str | None = None
    meeting: MeetingBriefRequest | None = None


def _generation_error(exc: BaseException, status: int, detail: str) -> HTTPException:
    owner = exc if getattr(exc, "briefing_run_id", None) else exc.__cause__
    run_id = getattr(owner, "briefing_run_id", None)
    if run_id:
        detail += (" Progress is saved. Retry the same meeting details to continue."
                   if getattr(owner, "briefing_run_resumable", False)
                   else " Draft progress and quality findings were saved for inspection.")
    return HTTPException(status_code=status, detail=detail,
                         headers={"X-Briefing-Run-ID": run_id} if run_id else None)


@app.post("/api/briefings")
async def create_meeting_brief(req: MeetingBriefRequest):
    from contextlib import nullcontext
    from self_improving_ai.tools.briefing.workspace_sources import operational_scope, client_mail_snapshot
    monitor = getattr(app.state, "preparations", None)
    scope = nullcontext()
    if monitor is not None:
        with monitor.db() as db:
            clock = json.loads(db.execute("SELECT state FROM calendar_simulation WHERE id=1").fetchone()[0])["now"][:10]
    try:
        if monitor is not None:
            cutoff = min(clock, req.meeting_date.isoformat())
            records = await asyncio.to_thread(client_mail_snapshot, req.client_id, cutoff)
            scope = operational_scope(req.client_id, cutoff, ai_mode=req.mode == "agent", records=records)
        with scope:
            if req.mode == "agent":
                from self_improving_ai.agents.briefing.runtime import generate_agent_brief
                try:
                    brief = await asyncio.wait_for(generate_agent_brief(req), timeout=180)
                except APIError as primary:
                    if primary.code not in (503, 504) or not settings.agent_model_fallback or settings.agent_model_fallback == settings.agent_model:
                        raise
                    brief = await asyncio.wait_for(generate_agent_brief(req, model=settings.agent_model_fallback),timeout=180)
                    brief["workflow"]["model_fallback_from"] = settings.agent_model
            else:
                brief = await asyncio.to_thread(generate_meeting_brief, req)
            await asyncio.to_thread(DraftStore().create, brief)
            return brief
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise _generation_error(exc, 422, str(exc)) from exc
    except TimeoutError as exc:
        raise _generation_error(exc, 504, "Agent timed out; no approved brief was created.") from exc
    except APIError as exc:
        if exc.code in (503, 504):
            raise _generation_error(exc, exc.code, "Gemini is temporarily busy or timed out. Please retry later; no approved brief was created.") from exc
        if exc.code == 429:
            raise _generation_error(exc, 429, "Gemini quota or rate limit reached. Check your project's usage limits before retrying.") from exc
        if exc.code == 404:
            raise _generation_error(exc, 502, "The configured Gemini model is unavailable for this account. Update SIA_AGENT_MODEL in the backend configuration.") from exc
        raise _generation_error(exc, 502, "Gemini rejected the request. Check backend configuration and account access.") from exc
    except Exception as exc:
        raise _generation_error(exc, 502, "Agent service unavailable. Check backend credentials or explicitly select Offline demo.") from exc


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


@app.get("/api/briefings/runs/{run_id}")
async def get_briefing_run(run_id: str):
    from self_improving_ai.agents.briefing.runs import BriefRunStore

    try:
        return await asyncio.to_thread(BriefRunStore().get, run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    return await run_in_threadpool(_load_clients)


@app.get("/api/clients/{client_id}")
async def get_client(client_id: str):
    for h in await run_in_threadpool(_load_clients):
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
    from self_improving_ai.tools.briefing.news import search_market_news
    result = await run_in_threadpool(search_market_news, "market outlook", 20)
    return result.get("results", [])


@app.get("/api/prices")
async def get_prices():
    return _load("prices/price_history.json")


@app.get("/api/stats")
async def get_stats():
    clients = await run_in_threadpool(_load_clients)
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
            f"**Portfolio:** {highlights[0]['text'] if highlights else 'See the full brief for portfolio context.'}\n\n"
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
                       "detail": f"Prepared six sections from {len(brief['sources'])} retained sources",
                       "tools_called": brief["tools_called"]}],
        }

    if is_meeting_request(req.message):
        details = collect_meeting_details(req.message, await run_in_threadpool(_load_clients), req.client_id)
        return {
            "response": "Confirm the client, New York meeting time and focus, then choose how to prepare the brief.",
            "intent": "meeting_briefing", "client_id": details["client_id"] or None,
            "meeting_details": details, "agents_used": [], "steps": [], "mode": "confirmation",
        }

    user_id = "advisor-001"
    session_id = await _get_or_create_session(user_id)

    message = req.message
    if req.client_id:
        message += f" (client_id: {req.client_id})"

    steps = []
    response_parts = []

    try:
        result = await run_copilot(
            runner=_runner,
            message=message,
            session_id=session_id,
            user_id=user_id,
        )
        steps = result["steps"]
        response_parts = result["response_parts"]
    except Exception as exc:
        err = str(exc)
        if any(code in err for code in ("503", "504", "UNAVAILABLE", "DEADLINE_EXCEEDED")):
            log.warning("Primary model unavailable or timed out, trying fallback model")
            try:
                result = await run_copilot(
                    runner=_get_fallback_runner(),
                    message=message,
                    session_id=session_id,
                    user_id=user_id,
                )
                steps = result["steps"]
                response_parts = result["response_parts"]
            except Exception as fallback_exc:
                log.exception("Fallback model also failed")
                fallback_err = str(fallback_exc)
                if "429" in fallback_err or "RESOURCE_EXHAUSTED" in fallback_err:
                    response_parts.append("Rate limit reached — please wait a moment and try again.")
                elif any(code in fallback_err for code in ("503", "504", "UNAVAILABLE", "DEADLINE_EXCEEDED")):
                    response_parts.append("The AI service is temporarily busy or timed out. Please try again in a minute.")
                else:
                    response_parts.append("Something went wrong. Please try again.")
        elif "429" in err or "RESOURCE_EXHAUSTED" in err:
            response_parts.append("Rate limit reached — please wait a moment and try again.")
        elif "max_llm_calls" in err.lower() or "exceeded" in err.lower():
            log.warning("Orchestrator hit LLM call budget: %s", err)
            response_parts.append("That request needed more steps than I could complete in one pass. Try asking about fewer clients at once, or be more specific about what you need.")
        else:
            log.exception("Orchestrator error")
            response_parts.append("Something went wrong. Please try again.")

    agents_used = list({s["agent"] for s in steps})
    if not agents_used:
        agents_used = ["Copilot"]

    response_text = response_parts[-1] if response_parts else "I'm not sure how to help with that. Could you rephrase?"

    return {
        "response": response_text,
        "intent": "gemini",
        "agents_used": agents_used,
        "client_id": req.client_id,
        "steps": steps,
        "mode": "live",
    }


_FRONTEND_DIR = Path.cwd() / "dashboard" / "dist"
if not _FRONTEND_DIR.is_dir():
    _FRONTEND_DIR = Path(__file__).resolve().parents[3] / "dashboard" / "dist"
if _FRONTEND_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIR / "assets"), name="static")

    @app.get("/")
    async def serve_frontend():
        """Serve the dashboard entry page."""
        return FileResponse(_FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.fastapi_port)
