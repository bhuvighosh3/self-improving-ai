"""AgentTool wrapper that caps briefing output before it reaches the orchestrator."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import ToolContext

from self_improving_ai.agents.briefing.store import DraftStore

log = logging.getLogger(__name__)

_SECTION_ORDER = ("overview", "changes", "portfolio", "priorities", "actions", "confirm")


def _cap_output(result: dict, brief_id: str) -> dict:
    """Reduce the full AgentWork to a compact summary safe for the orchestrator context."""
    sections = {s["id"]: s for s in result.get("sections", [])}
    overview_items = sections.get("overview", {}).get("items", [])
    summary = overview_items[0]["text"][:350] if overview_items else "The meeting draft is ready to review."
    priorities = [
        item["title"][:100]
        for item in sections.get("priorities", {}).get("items", [])[:3]
    ]
    return {
        "status": "ready",
        "brief_id": brief_id,
        "summary": summary,
        "priorities": priorities,
        "review_status": "draft",
        "next_action": "Open Meeting Brief for sources, editing and advisor review.",
    }


def _persist_draft(work: dict, args: dict) -> str:
    """Save the full agent output as a draft so Meeting Prep can open it."""
    brief_id = str(uuid4())
    sections = sorted(
        work.get("sections", []),
        key=lambda s: _SECTION_ORDER.index(s["id"]) if s["id"] in _SECTION_ORDER else 99,
    )
    brief = {
        "id": brief_id,
        "client_id": args.get("client_id", ""),
        "client_name": work.get("context_summary", "")[:200],
        "contact": "",
        "meeting_date": args.get("meeting_date", ""),
        "meeting_time": args.get("meeting_time", ""),
        "timezone": "America/New_York",
        "meeting_type": args.get("meeting_type", "general_meeting"),
        "focus": args.get("focus", ""),
        "data_as_of": args.get("meeting_date", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "agent",
        "sources": [],
        "sections": sections,
        "news": [],
        "workflow": {"version": "v1", "work": work},
    }
    DraftStore().create(brief)
    return brief_id


class CappedBriefingAgentTool(AgentTool):
    """Runs the real briefing sub-agent, then caps its output for the orchestrator.

    The full AgentWork is persisted via the DraftStore so Meeting Prep can open it.
    Only a compact summary (brief_id, overview, top priorities) is returned upstream.
    """

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> Any:
        full_result = await super().run_async(args=args, tool_context=tool_context)

        if not isinstance(full_result, dict) or "sections" not in full_result:
            return full_result

        brief_id = _persist_draft(full_result, args)
        return _cap_output(full_result, brief_id)
