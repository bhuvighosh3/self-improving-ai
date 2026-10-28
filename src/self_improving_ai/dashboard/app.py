"""FastAPI backend for the self-improving AI dashboard."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv

from self_improving_ai.config import settings
from self_improving_ai.agents.briefing.schemas import BriefExportRequest, MeetingBriefRequest
from self_improving_ai.agents.briefing.pdf import render_brief_pdf
from self_improving_ai.agents.briefing.service import generate_meeting_brief
from self_improving_ai.dashboard.meeting_requests import collect_meeting_details
from self_improving_ai.agents.briefing.workflow_models import CheckRequest, ReviewRequest
from self_improving_ai.agents.briefing.store import DraftStore
from self_improving_ai.agents.briefing.review import check_draft

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

app = FastAPI(title="Self-Improving AI Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


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


def _detect_intent(text: str) -> dict:
    """Classify an advisor request into intent + relevant client."""
    t = text.lower()
    clients = _load("clients/households.json")
    client_map = {c["client_id"]: c for c in clients}

    matched_client = None
    for c in clients:
        name = c["profile"]["name"].lower()
        contact = c["profile"]["primary_contact"].lower()
        cid = c["client_id"].lower()
        if name.split()[0] in t or contact.split()[-1].lower() in t or cid in t:
            matched_client = c
            break

    if any(w in t for w in ["brief", "meeting", "ready for", "prepare", "summary", "call in"]):
        intent = "meeting_briefing"
        agents = ["request_orchestrator", "meeting_briefing_agent", "portfolio_estimation_agent"]
    elif any(w in t for w in ["tax", "capital gain", "harvest", "liquidat"]):
        intent = "tax_estimation"
        agents = ["request_orchestrator", "portfolio_estimation_agent"]
    elif any(w in t for w in ["project", "monte carlo", "forecast", "value in"]):
        intent = "portfolio_projection"
        agents = ["request_orchestrator", "portfolio_estimation_agent"]
    elif any(w in t for w in ["risk", "duration", "diversif", "allocation"]):
        intent = "risk_analysis"
        agents = ["request_orchestrator", "portfolio_estimation_agent"]
    elif any(w in t for w in ["withdraw", "income", "sustainable", "rmd", "distribution"]):
        intent = "income_planning"
        agents = ["request_orchestrator", "portfolio_estimation_agent"]
    elif any(w in t for w in ["compliance", "flag", "rule"]):
        intent = "compliance_check"
        agents = ["request_orchestrator", "meeting_briefing_agent"]
    else:
        intent = "general"
        agents = ["request_orchestrator", "meeting_briefing_agent", "portfolio_estimation_agent"]

    return {"intent": intent, "agents": agents, "client": matched_client}


def _build_portfolio_response(client: dict) -> dict:
    """Build a portfolio summary from client data."""
    total = 0
    holdings_detail = []
    for acct in client.get("accounts", []):
        for h in acct.get("holdings", []):
            total += h["market_value"]
            gl = h["market_value"] - h["cost_basis"]
            holdings_detail.append({
                "ticker": h["ticker"],
                "shares": h["shares"],
                "market_value": h["market_value"],
                "cost_basis": h["cost_basis"],
                "gain_loss": gl,
                "gain_pct": round(gl / h["cost_basis"] * 100, 1) if h["cost_basis"] else 0,
                "account": acct["account_id"],
                "account_type": acct["type"],
            })
    holdings_detail.sort(key=lambda x: x["market_value"], reverse=True)
    return {"total_value": total, "holdings": holdings_detail}


def _build_briefing_response(client: dict) -> dict:
    """Build a meeting briefing from client + news data."""
    profile = client.get("profile", {})
    notes = client.get("crm_notes", [])
    all_news = _load("news/market_news.json")

    goals = profile.get("goals", [])
    risk = profile.get("risk_tolerance", "unknown")
    tickers = set()
    for acct in client.get("accounts", []):
        for h in acct.get("holdings", []):
            tickers.add(h["ticker"])

    relevant_news = [
        n for n in all_news
        if n.get("sector") not in ("lifestyle", "entertainment", "health")
        and any(
            kw in n.get("text", "").lower()
            for kw in [t.lower() for t in tickers]
            + goals
            + [risk, "rate", "tax", "rmd", "dividend"]
        )
    ][:3]

    return {
        "profile_summary": {
            "name": profile.get("name"),
            "contact": profile.get("primary_contact"),
            "risk_tolerance": risk,
            "goals": goals,
            "horizon": profile.get("investment_horizon"),
            "income": profile.get("annual_income"),
            "tax_bracket": profile.get("tax_bracket"),
        },
        "recent_notes": notes[:3],
        "relevant_news": relevant_news,
        "key_topics": [n.get("text", "")[:80] + "..." for n in notes[:2]],
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if req.meeting is not None:
        # Both entry points use the same service and return the same brief object.
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

    parsed = _detect_intent(req.message)
    intent = parsed["intent"]
    if intent == "meeting_briefing":
        return {
            "response": "Confirm the client, date, time and meeting focus below, then generate your brief. Times are in New York.",
            "intent": intent, "mode": "simulation", "agents_used": [], "steps": [],
            "meeting_details": collect_meeting_details(req.message, _load("clients/households.json"), req.client_id),
        }
    agents_used = parsed["agents"]
    client = parsed["client"]

    if not client and req.client_id:
        for c in _load("clients/households.json"):
            if c["client_id"] == req.client_id:
                client = c
                break

    steps = []
    portfolio_data = None
    briefing_data = None

    steps.append({
        "agent": "request_orchestrator",
        "action": "parse_intent",
        "detail": f"Classified request as '{intent}'",
        "tools_called": ["search_tool_catalog"],
    })

    if client:
        steps[0]["detail"] += f" for client {client['profile']['name']} ({client['client_id']})"

        if "portfolio_estimation_agent" in agents_used:
            portfolio_data = _build_portfolio_response(client)
            tools = ["get_holdings"]
            if intent == "tax_estimation":
                tools.append("estimate_capital_gains")
            elif intent == "portfolio_projection":
                tools.extend(["get_price_history", "get_capital_market_assumptions"])
            elif intent == "risk_analysis":
                tools.extend(["get_price_history", "get_capital_market_assumptions"])
            elif intent == "income_planning":
                tools.append("calculate_withdrawal_rate")
            steps.append({
                "agent": "portfolio_estimation_agent",
                "action": "analyze_portfolio",
                "detail": f"Retrieved {len(portfolio_data['holdings'])} holdings, total value ${portfolio_data['total_value']:,.0f}",
                "tools_called": tools,
                "data": portfolio_data,
            })

        if "meeting_briefing_agent" in agents_used:
            briefing_data = _build_briefing_response(client)
            tools = ["get_client_profile", "get_crm_notes"]
            if briefing_data["relevant_news"]:
                tools.append("search_market_news")
            if intent == "compliance_check":
                tools.append("check_compliance_flags")
            steps.append({
                "agent": "meeting_briefing_agent",
                "action": "build_briefing",
                "detail": f"Compiled profile, {len(briefing_data['recent_notes'])} CRM notes, {len(briefing_data['relevant_news'])} relevant news articles",
                "tools_called": tools,
                "data": briefing_data,
            })

        steps.append({
            "agent": "request_orchestrator",
            "action": "synthesize",
            "detail": "Merged agent results into final response",
            "tools_called": [],
        })

        response_text = _generate_response_text(intent, client, portfolio_data, briefing_data)
    else:
        response_text = (
            "I couldn't identify a specific client from your request. "
            "Please mention a client name or select one from the dropdown. "
            "Available clients: Garcia Family, Thompson Trust, Chen Household, Okafor Family, Patel Retirement Account."
        )

    return {
        "response": response_text,
        "intent": intent,
        "agents_used": agents_used,
        "client_id": client["client_id"] if client else None,
        "steps": steps,
        "mode": "simulation",
    }


def _generate_response_text(intent, client, portfolio, briefing):
    name = client["profile"]["name"]
    contact = client["profile"]["primary_contact"]

    if intent == "tax_estimation" and portfolio:
        gains = [h for h in portfolio["holdings"] if h["gain_loss"] > 0]
        losses = [h for h in portfolio["holdings"] if h["gain_loss"] < 0]
        total_gain = sum(h["gain_loss"] for h in gains)
        total_loss = sum(h["gain_loss"] for h in losses)
        bracket = client["profile"].get("tax_bracket", "N/A")
        return (
            f"**Tax Analysis: {name}**\n\n"
            f"**Tax Bracket:** {bracket}\n\n"
            f"**Unrealized Gains:** ${total_gain:,.0f} across {len(gains)} positions\n"
            f"**Unrealized Losses:** ${abs(total_loss):,.0f} across {len(losses)} positions\n"
            f"**Net:** ${total_gain + total_loss:,.0f}\n\n"
            + "".join(
                f"- {h['ticker']}: {'gain' if h['gain_loss'] >= 0 else 'loss'} of "
                f"${abs(h['gain_loss']):,} ({h['gain_pct']:+.1f}%)\n"
                for h in sorted(portfolio["holdings"], key=lambda x: abs(x["gain_loss"]), reverse=True)[:5]
            )
        )

    if intent == "portfolio_projection" and portfolio:
        total = portfolio["total_value"]
        projected_7 = total * (1.07 ** 10)
        projected_5 = total * (1.05 ** 10)
        return (
            f"**Portfolio Projection: {name}**\n\n"
            f"**Current Value:** ${total:,.0f}\n\n"
            f"**10-Year Projections:**\n"
            f"- At 7% avg return: **${projected_7:,.0f}**\n"
            f"- At 5% avg return: **${projected_5:,.0f}**\n\n"
            f"*Based on current holdings. Assumes no additional contributions or withdrawals.*"
        )

    if intent == "risk_analysis" and portfolio:
        alloc = {}
        total = portfolio["total_value"]
        for h in portfolio["holdings"]:
            alloc[h["ticker"]] = h["market_value"] / total * 100
        top = sorted(alloc.items(), key=lambda x: x[1], reverse=True)
        return (
            f"**Risk Analysis: {name}**\n\n"
            f"**Risk Tolerance:** {client['profile']['risk_tolerance']}\n\n"
            f"**Current Allocation:**\n"
            + "".join(f"- {t}: {p:.1f}%\n" for t, p in top)
            + f"\n**Concentration Risk:** Top position ({top[0][0]}) is {top[0][1]:.1f}% of portfolio."
        )

    if intent == "income_planning" and portfolio:
        total = portfolio["total_value"]
        rate_4 = total * 0.04 / 12
        rate_3 = total * 0.03 / 12
        return (
            f"**Income Planning: {name}**\n\n"
            f"**Portfolio Value:** ${total:,.0f}\n\n"
            f"**Sustainable Monthly Withdrawals:**\n"
            f"- At 4% rule: **${rate_4:,.0f}/month** (${total * 0.04:,.0f}/year)\n"
            f"- At 3% (conservative): **${rate_3:,.0f}/month** (${total * 0.03:,.0f}/year)\n\n"
            f"*Consider: required minimum distributions, Social Security timing, tax bracket management.*"
        )

    if intent == "compliance_check" and briefing:
        return (
            f"**Compliance Check: {name}**\n\n"
            f"Reviewed compliance flags and recent regulatory updates.\n\n"
            f"**Recent Notes:**\n"
            + "".join(f"- [{n['date']}] {n['text']}\n" for n in briefing.get("recent_notes", []))
            + "\n**Action Items:** Review RMD schedule, confirm beneficiary designations are current."
        )

    if portfolio:
        return (
            f"**{name} — Overview**\n\n"
            f"Portfolio value: ${portfolio['total_value']:,.0f} across {len(portfolio['holdings'])} positions.\n\n"
            f"Please specify what you'd like to know — projections, tax analysis, risk review, or meeting prep."
        )

    return f"Processed request for {name}. How can I help further?"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.fastapi_port)
