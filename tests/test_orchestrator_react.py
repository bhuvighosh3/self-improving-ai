"""Integration test for the orchestrator ReAct loop with direct tools.

Sends 10 test questions to the orchestrator, each designed to exercise
different tool combinations and routing paths. Reports expected vs actual
planning steps and output quality.

Run with: SIA_GOOGLE_CLOUD_PROJECT=self-improving-ai-513915 python3 -m pytest tests/test_orchestrator_react.py -v -s
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from google.adk import Runner
from google.adk.sessions import InMemorySessionService

TEST_QUESTIONS = [
    {
        "id": 1,
        "question": "When is my next meeting with the Garcia family?",
        "expected_tools": ["get_upcoming_events"],
        "expected_routing": "direct_tool",
        "description": "Simple calendar lookup — should use get_upcoming_events, no sub-agent",
    },
    {
        "id": 2,
        "question": "What is CLI-002's risk tolerance and do they have any upcoming meetings?",
        "expected_tools": ["get_client_info", "get_upcoming_events"],
        "expected_routing": "multi_direct_tool",
        "description": "Two direct tools — client info + calendar",
    },
    {
        "id": 3,
        "question": "Show me the Garcia family's portfolio holdings and any open CRM tasks",
        "expected_tools": ["get_client_holdings", "get_crm_summary"],
        "expected_routing": "multi_direct_tool",
        "description": "Holdings + CRM summary — two direct tools",
    },
    {
        "id": 4,
        "question": "What is a Required Minimum Distribution and who in my book might need one?",
        "expected_tools": [],
        "expected_routing": "domain_knowledge_then_tool",
        "description": "Generic domain question + possible client lookup",
    },
    {
        "id": 5,
        "question": "Run a risk analysis on CLI-003's portfolio",
        "expected_tools": ["portfolio_estimation_agent"],
        "expected_routing": "sub_agent_delegation",
        "description": "Complex portfolio analysis — should delegate to portfolio agent",
    },
    {
        "id": 6,
        "question": "Are there any emails about the Thompson Trust and what's their risk profile?",
        "expected_tools": ["get_recent_emails", "get_client_info"],
        "expected_routing": "multi_direct_tool",
        "description": "Emails + client profile — two direct tools, must resolve client name",
    },
    {
        "id": 7,
        "question": "Prepare a meeting brief for the Garcia family's upcoming Q4 review",
        "expected_tools": ["meeting_briefing_agent"],
        "expected_routing": "sub_agent_delegation",
        "description": "Meeting prep — should delegate to briefing agent",
    },
    {
        "id": 8,
        "question": "What's on my calendar for December 2026 and which clients have the highest portfolio value?",
        "expected_tools": ["get_upcoming_events", "get_client_holdings"],
        "expected_routing": "multi_tool_mixed",
        "description": "Calendar lookup + multiple holdings lookups",
    },
    {
        "id": 9,
        "question": "Show me CLI-001's CRM notes, their holdings, and any upcoming meetings",
        "expected_tools": ["get_crm_summary", "get_client_holdings", "get_upcoming_events"],
        "expected_routing": "multi_direct_tool",
        "description": "Three direct tools for a single client — full client snapshot",
    },
    {
        "id": 10,
        "question": "What's CLI-005's risk tolerance and can you project if they're on track for a $500K goal in 10 years?",
        "expected_tools": ["get_client_info", "portfolio_estimation_agent"],
        "expected_routing": "direct_plus_delegation",
        "description": "Direct tool for profile + delegate to portfolio agent for projection",
    },
]


@pytest.fixture(scope="module")
def orchestrator_setup():
    """Set up the orchestrator runner once for all tests."""
    from self_improving_ai.agents.orchestrator.agent import orchestrator
    from self_improving_ai.agents.orchestrator.runtime import run_copilot

    session_service = InMemorySessionService()

    async def create_session():
        session = await session_service.create_session(
            app_name=orchestrator.name,
            user_id="test-advisor",
            state={
                "intent_corrections": "",
                "tool_notes": "",
                "plan_templates": "",
            },
        )
        return session.id

    session_id = asyncio.run(create_session())
    runner = Runner(
        app_name=orchestrator.name,
        agent=orchestrator,
        session_service=session_service,
    )
    return runner, session_id, run_copilot


def _run_question(orchestrator_setup, q):
    """Run a single question and collect results."""
    runner, session_id, run_copilot = orchestrator_setup

    start = time.monotonic()
    result = asyncio.run(
        run_copilot(
            runner=runner,
            message=q["question"],
            session_id=session_id,
            user_id="test-advisor",
            max_loops=1,
            max_llm_calls=12,
        )
    )
    elapsed = time.monotonic() - start

    tools_called = [s["action"] for s in result["steps"]]
    response = result["response_parts"][-1] if result["response_parts"] else ""

    return {
        "question_id": q["id"],
        "question": q["question"],
        "expected_tools": q["expected_tools"],
        "actual_tools": tools_called,
        "expected_routing": q["expected_routing"],
        "loops_used": result["loops_used"],
        "elapsed_seconds": round(elapsed, 2),
        "response_preview": response[:200],
        "verdict": result.get("verdict", {}),
    }


@pytest.mark.parametrize("q", TEST_QUESTIONS, ids=[f"q{q['id']}" for q in TEST_QUESTIONS])
def test_orchestrator_question(orchestrator_setup, q):
    """Run each test question and report results.

    These tests are observational — they print the planning vs actual
    comparison but don't fail on tool mismatch (the LLM may choose
    valid alternative paths). They fail only on errors or empty responses.
    """
    result = _run_question(orchestrator_setup, q)

    print(f"\n{'='*60}")
    print(f"Q{result['question_id']}: {result['question']}")
    print(f"Expected tools: {result['expected_tools']}")
    print(f"Actual tools:   {result['actual_tools']}")
    print(f"Routing:        {q['expected_routing']}")
    print(f"Loops used:     {result['loops_used']}")
    print(f"Time:           {result['elapsed_seconds']}s")
    print(f"Response:       {result['response_preview']}")
    print(f"{'='*60}")

    # Soft assertions — report but don't fail on tool mismatch
    assert result["response_preview"], f"Q{q['id']}: Empty response"
    assert result["elapsed_seconds"] < 120, f"Q{q['id']}: Took too long ({result['elapsed_seconds']}s)"
