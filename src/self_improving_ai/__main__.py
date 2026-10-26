"""Entry point: run the orchestrator on a sample request."""

from __future__ import annotations

import asyncio
import sys

from google.adk import Runner, InMemorySessionService
from google.genai import types

from self_improving_ai.agents.orchestrator.agent import orchestrator
from self_improving_ai.telemetry import init_telemetry


async def main(request_text: str) -> None:
    init_telemetry()

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=orchestrator.name,
        user_id="advisor-001",
        state={
            "intent_corrections": "",
            "tool_notes": "",
            "plan_templates": "",
        },
    )

    runner = Runner(agent=orchestrator, session_service=session_service)

    content = types.Content(
        role="user",
        parts=[types.Part(text=request_text)],
    )

    print(f"\n--- Request: {request_text} ---\n")
    async for event in runner.run_async(
        session_id=session.id,
        user_id="advisor-001",
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"[{event.author}] {part.text}")


if __name__ == "__main__":
    request = " ".join(sys.argv[1:]) or "Get me ready for my 2pm with the Garcias"
    asyncio.run(main(request))
