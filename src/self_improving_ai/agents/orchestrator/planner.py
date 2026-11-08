"""Component C planner: advisor request -> structured plan (intent, client, steps, disclosures).

Two implementations share one interface:

- GeminiPlanner: the real planner. Calls Gemini with structured output (OrchestratorPlan).
  Uses Vertex AI when GOOGLE_GENAI_USE_VERTEXAI=TRUE, otherwise a Gemini API key.
- KeywordPlanner: a deterministic stand-in with no LLM. It exists so the learning loop and
  scorer can be tested offline and in CI. Its numbers are not results.

The four agent variants compared in the evaluation differ only in the PlanContext they get:
static (nothing), hand_tuned (static + hand-written guidance), retrieval (similar past
successful runs as examples) and learner (learned memory).
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from self_improving_ai.agents.orchestrator.memory import scrub, similarity, tokens
from self_improving_ai.agents.orchestrator.schemas import OrchestratorPlan, PlannedStep, StepArg
from self_improving_ai.tools.orchestrator.catalog import Catalog

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "orchestrator"


def load_intents() -> dict[str, dict]:
    return json.loads((_DATA_DIR / "intents.json").read_text())


def load_clients() -> list[dict]:
    """Load the advisor's book of clients from Firestore."""
    from self_improving_ai.client_store import load_households

    households = load_households()
    clients = []
    for h in households:
        profile = h.get("profile", {})
        name = profile.get("name", h.get("name", ""))
        contact = profile.get("primary_contact", profile.get("name", ""))
        aliases = profile.get("aliases") or []
        if not aliases:
            aliases = [name, contact]
            surname = contact.split()[-1] if contact else ""
            if surname:
                aliases.extend([f"the {surname}s", f"{surname} family"])
        clients.append({
            "client_id": h["client_id"],
            "name": name,
            "primary_contact": contact,
            "aliases": aliases,
        })
    return clients


def load_hand_tuned_notes() -> str:
    path = _DATA_DIR / "hand_tuned_notes.md"
    return path.read_text().strip() if path.exists() else ""


@dataclass
class PlanContext:
    intent_corrections: str = ""
    tool_notes: str = ""
    plan_templates: str = ""
    guidance: str = ""
    examples: list[tuple[str, dict]] = field(default_factory=list)


@dataclass
class PlanResult:
    plan: OrchestratorPlan
    input_tokens: int = 0
    output_tokens: int = 0
    error: str = ""


class Planner(Protocol):
    async def plan(self, request_text: str, catalog: Catalog, ctx: PlanContext, seed: int = 0) -> PlanResult: ...


SYSTEM_RULES = """\
You are the Request Orchestrator of a wealth-management copilot. You turn an advisor's \
free-text request into a plan. You do not execute the plan and you never invent results.

Rules:
1. Pick exactly one intent from the taxonomy. If the request could mean several different \
things and the plans would differ, either set needs_clarification with one short question, or \
pick the most likely reading and state it in `interpretation`.
2. Resolve the client from the advisor's book and put the client_id (CLI-xxx) in client_ids \
and in step arguments. If a name matches more than one client, set needs_clarification, ask \
which one, and plan no client-specific steps until the advisor answers.
3. Only use tools whose callable_by_you is true. Work that belongs to the portfolio or \
briefing agents goes through portfolio_estimation_agent or meeting_briefing_agent.
4. Never plan a step that executes a trade or sends a message to a client. If the advisor \
asks for a trade, use intent trade_request, plan no steps, and add a disclosure that the \
copilot cannot place orders.
5. Do not use deprecated tools. If the capability you need is missing from the catalog, do \
not substitute a different tool; plan without it and add a disclosure.
6. Include only the steps needed. Steps that use an earlier step's output must list it in \
depends_on. Use the units documented in each tool's parameters.
"""


def build_prompt(request_text: str, catalog: Catalog, ctx: PlanContext) -> tuple[str, str]:
    intents = load_intents()
    clients = load_clients()
    parts = [SYSTEM_RULES]
    parts.append("## Intent taxonomy\n" + "\n".join(f"- {k}: {v['description']}" for k, v in intents.items()))
    parts.append(
        "## Advisor's book of clients\n"
        + "\n".join(f"- {c['client_id']}: {c['name']} (primary contact {c['primary_contact']})" for c in clients)
    )
    parts.append("## Tool catalog\n" + json.dumps(catalog.planner_view(), indent=1))
    for block in (ctx.guidance, ctx.intent_corrections, ctx.tool_notes, ctx.plan_templates):
        if block:
            parts.append(block)
    if ctx.examples:
        ex_lines = ["## Similar past requests that were handled correctly"]
        for text, plan in ctx.examples:
            ex_lines.append(f"Request: {text}\nPlan: {json.dumps(plan)}")
        parts.append("\n\n".join(ex_lines))
    system = "\n\n".join(parts)
    user = f"Advisor request: {request_text}\n\nReturn the plan."
    return system, user


class GeminiPlanner:
    """Structured-output planner on Gemini (Vertex AI or API key, read from the environment)."""

    def __init__(self, model: str | None = None, temperature: float = 0.4, max_retries: int = 3):
        from google import genai

        from self_improving_ai.config import settings

        self.model = model or settings.agent_model
        self.temperature = temperature
        self.max_retries = max_retries
        self.client = genai.Client()

    async def plan(self, request_text: str, catalog: Catalog, ctx: PlanContext, seed: int = 0) -> PlanResult:
        from google.genai import types

        system, user = build_prompt(request_text, catalog, ctx)
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=OrchestratorPlan,
            temperature=self.temperature,
            seed=seed,
        )
        last_err = ""
        for attempt in range(self.max_retries):
            try:
                resp = await self.client.aio.models.generate_content(
                    model=self.model, contents=user, config=config
                )
                plan = resp.parsed if isinstance(resp.parsed, OrchestratorPlan) else (
                    OrchestratorPlan.model_validate_json(resp.text)
                )
                usage = resp.usage_metadata
                return PlanResult(
                    plan=plan,
                    input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                    output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                )
            except Exception as e:  # noqa: BLE001  network, quota or parse errors are retried
                last_err = f"{type(e).__name__}: {e}"
                await asyncio.sleep(2 * (attempt + 1))
        return PlanResult(plan=OrchestratorPlan(intent="error"), error=last_err)


# Offline stand-in

_INTENT_KEYWORDS: list[tuple[str, list[str]]] = [
    ("trade_request", ["sell", "buy", "order", "dump", "execute", "place the"]),
    ("market_event_outreach", ["call first", "reach out", "outreach", "who should hear", "who needs a call", "triage"]),
    ("market_event_book_exposure", ["my clients", "my book", "households lost", "most exposed", "rank my clients", "got hurt"]),
    ("rmd_check", ["rmd", "required distribution"]),
    ("currency_shock_impact", ["eur/usd", "usd/jpy", "gbp/usd", "currency"]),
    ("rate_shock_impact", ["bps", "basis point", "bp ", "yields", "rates up", "rate increase"]),
    ("tax_loss_harvest", ["harvest"]),
    ("tax_impact", ["tax", "gains", "lots"]),
    ("rebalance_analysis", ["rebal", "drift", "target allocation"]),
    ("income_planning", ["withdraw", "income", "take out"]),
    ("fee_review", ["fee", "expense ratio"]),
    ("diversification_check", ["diversif", "risk tolerance", "risk profile", "concentrated", "signed up"]),
    ("portfolio_risk_return", ["volatility", "vol", "risky", "risk/return", "risk and return"]),
    ("goal_projection", ["on track", "on pace", "chances", "projection", "reach", "monte carlo"]),
    ("compliance_check", ["compliance"]),
    ("open_action_items", ["follow-up", "open items", "outstanding", "promise", "action items", "todo"]),
    ("client_note", ["note", "message", "draft"]),
    ("quick_client_summary", ["summary", "refresher", "tl;dr", "who are", "remind me"]),
    ("schedule_lookup", ["calendar", "schedule", "my meetings", "who am i seeing", "agenda"]),
    ("price_lookup", ["trading at", "price", "quote", "nav", "px"]),
]

# Naive default plans: the kind of first attempt an untuned planner makes. They contain the
# catalog traps on purpose (deprecated price API, holdings tool without tax lots, missing
# triage step, no event context) so offline tests can show the learner fixing them.
_NAIVE_PLANS: dict[str, list[tuple[str, dict, list[int]]]] = {
    "meeting_prep": [("meeting_briefing_agent", {"client_id": "{cid}"}, [])],
    "meeting_prep_goal_check": [("meeting_briefing_agent", {"client_id": "{cid}"}, [])],
    "quick_client_summary": [("get_client_profile", {"client_id": "{cid}"}, [])],
    "goal_projection": [("portfolio_estimation_agent", {"client_id": "{cid}", "task": "goal_projection"}, [])],
    "portfolio_risk_return": [("portfolio_estimation_agent", {"client_id": "{cid}", "task": "risk_return"}, [])],
    "diversification_check": [("portfolio_estimation_agent", {"client_id": "{cid}", "task": "risk_return"}, [])],
    "rebalance_analysis": [("portfolio_estimation_agent", {"client_id": "{cid}", "task": "drift"}, [])],
    "tax_impact": [("getHoldings", {"client_id": "{cid}"}, []), ("portfolio_estimation_agent", {"client_id": "{cid}", "task": "tax_impact"}, [1])],
    "tax_loss_harvest": [("getHoldingsSummary", {"client_id": "{cid}"}, []), ("portfolio_estimation_agent", {"client_id": "{cid}", "task": "tax_loss_harvest"}, [1])],
    "income_planning": [("portfolio_estimation_agent", {"client_id": "{cid}", "task": "income"}, [])],
    "rate_shock_impact": [("portfolio_estimation_agent", {"client_id": "{cid}", "task": "rate_shock", "shock_bps": "{bps_decimal}"}, [])],
    "market_event_book_exposure": [("get_market_event", {}, []), ("compute_book_exposure", {"metric": "pnl"}, [1])],
    "market_event_outreach": [("get_market_event", {}, []), ("compute_book_exposure", {}, [1]), ("draft_client_note", {}, [2])],
    "client_note": [("get_client_profile", {"client_id": "{cid}"}, []), ("draft_client_note", {"client_id": "{cid}"}, [1])],
    "compliance_check": [("check_compliance_flags", {"client_id": "{cid}"}, [])],
    "open_action_items": [("get_crm_notes", {"client_id": "{cid}"}, [])],
    "price_lookup": [("get_prices_v1", {"ticker": "{sym}"}, [])],
    "schedule_lookup": [("get_meeting_schedule", {"date": "{date}"}, [])],
    "trade_request": [("place_trade", {"account_id": "{cid}"}, [])],
    "fee_review": [("calculate_fee_drag", {"client_id": "{cid}"}, [])],
    "currency_shock_impact": [("portfolio_estimation_agent", {"client_id": "{cid}", "task": "currency_shock"}, [])],
    "rmd_check": [("calculate_rmd", {"client_id": "{cid}"}, [])],
}


_FUNDS = {"VFIAX", "FXAIX", "PTTRX", "VBTLX"}


def _resolve_clients(text: str) -> list[str]:
    low = text.lower()
    hits: list[str] = []
    for c in load_clients():
        names = [c["name"], c["primary_contact"], *c["aliases"]]
        if any(n.lower() in low for n in names):
            hits.append(c["client_id"])
    if not hits:
        # surname match, e.g. "patel", "okafor family", "J. Chen"
        for c in load_clients():
            surname = c["primary_contact"].split()[-1].lower()
            if re.search(rf"\b{surname}s?\b", low):
                hits.append(c["client_id"])
    return hits


class KeywordPlanner:
    """Deterministic offline planner that reads the same PlanContext as GeminiPlanner."""

    async def plan(self, request_text: str, catalog: Catalog, ctx: PlanContext, seed: int = 0) -> PlanResult:
        low = request_text.lower()
        intent = "meeting_prep"
        for name, kws in _INTENT_KEYWORDS:
            if any(k in low for k in kws):
                intent = name
                break
        # Learned intent lessons override keyword rules when a close match exists.
        m = re.findall(r'- "(.+?)" -> intent (\w+)', ctx.intent_corrections)
        best = (0.0, None)
        q = tokens(scrub(request_text))
        for text, lesson_intent in m:
            sim = similarity(q, tokens(text))
            if sim > best[0]:
                best = (sim, lesson_intent)
        if best[1] and best[0] >= 0.6:
            intent = best[1]
        for text, plan in ctx.examples:
            if similarity(q, tokens(scrub(text))) >= 0.6:
                intent = plan.get("intent", intent)
                break

        clients = _resolve_clients(request_text)
        cid = clients[0] if clients else ""
        if len(clients) > 1 and "ask which client" in ctx.intent_corrections.lower():
            return PlanResult(plan=OrchestratorPlan(
                intent=intent, needs_clarification=True,
                clarification_question="Which client do you mean?",
            ))

        sym_match = re.search(r"\b([A-Z]{3,5})\b", request_text)
        bps_match = re.search(r"(\d+)\s*(?:bps|bp|basis)", low)
        date_match = re.search(r"(today|tomorrow|tmrw|friday|next monday)", low)
        slots = {
            "cid": cid,
            "sym": sym_match.group(1) if sym_match else "",
            "bps_decimal": str(int(bps_match.group(1)) / 10000) if bps_match else "",
            "bps": bps_match.group(1) if bps_match else "",
            "date": date_match.group(1) if date_match else "today",
        }
        steps_src = _NAIVE_PLANS.get(intent, [])
        tmpl = re.search(rf"- {intent}: (.+)", ctx.plan_templates)
        if tmpl:
            steps_src = _parse_template(tmpl.group(1))
        if ctx.examples:
            for text, plan in ctx.examples:
                if plan.get("intent") == intent and similarity(q, tokens(scrub(text))) >= 0.4:
                    steps_src = [(s["tool"], {a["name"]: a["value"] for a in s.get("args", [])}, s.get("depends_on", [])) for s in plan.get("steps", [])]
                    break
        steps = []
        for i, (tool, args, deps) in enumerate(steps_src, 1):
            tool = _apply_tool_notes(tool, ctx.tool_notes, catalog)
            if tool is None:
                continue
            filled = {}
            for k, v in args.items():
                v = str(v)
                for ph, slot in (("<client_id>", "{cid}"), ("<ticker>", "{sym}"), ("<date>", "{date}"), ("<bps>", "{bps}")):
                    v = v.replace(ph, slot)
                if k == "shock_bps" and bps_match and "basis points" in (ctx.tool_notes + ctx.guidance):
                    v = "{bps}"
                if "<" in v:
                    continue
                filled[k] = v.format(**slots) if "{" in v else v
            notes = ctx.tool_notes + ctx.guidance
            if tool == "get_intraday_price" and slots["sym"] in _FUNDS and "mutual funds" in notes and "get_fund_nav" in notes:
                tool = "get_fund_nav"
            steps.append(PlannedStep(id=i, tool=tool, args=[StepArg(name=k, value=v) for k, v in filled.items()], depends_on=list(deps)))
        disclosures = ["The copilot cannot place orders."] if intent == "trade_request" else []
        return PlanResult(plan=OrchestratorPlan(intent=intent, client_ids=[cid] if cid else [], steps=steps, disclosures=disclosures))


def _parse_template(text: str) -> list[tuple[str, dict, list[int]]]:
    if text.strip() == "no tool calls":
        return []
    out = []
    for chunk in text.split("; "):
        m = re.match(r"(\d+)\. (\w+)\((.*?)\)(?: after \[(.*?)\])?$", chunk.strip())
        if not m:
            continue
        args = {}
        for kv in filter(None, m.group(3).split(", ")):
            k, _, v = kv.partition("=")
            args[k] = v
        deps = [int(x) for x in m.group(4).split(",")] if m.group(4) else []
        out.append((m.group(2), args, deps))
    return out


def _apply_tool_notes(tool: str, notes: str, catalog: Catalog) -> str | None:
    """Follow learned notes of the form 'Do not use X ... use Y instead' or 'Never call X'."""
    for line in notes.splitlines():
        if not line.startswith(f"- {tool}:"):
            continue
        if "Never call" in line:
            return None
        m = re.search(r"use (\w+) instead", line)
        if m and catalog.exists(m.group(1)):
            return m.group(1)
    return tool
