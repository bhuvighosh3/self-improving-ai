"""Lightweight completion checker for the orchestrator ReAct loop.

Uses a fast model (flash-lite) to verify whether the orchestrator's response
fully addresses the user's request. Returns a structured verdict.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

_CHECKER_PROMPT = """\
You are a completion checker for a wealth management copilot.
Your job is to verify whether the copilot's response fully addresses the advisor's request.

Original request: {user_message}

Tools called and results summary:
{tools_summary}

Final response:
{response_text}

Evaluate completeness:
1. Does the response address every part of the request?
2. Were all necessary data lookups performed (client info, calendar, holdings, etc.)?
3. Are there unanswered sub-questions or missing details the advisor asked about?
4. Did any tool call fail that should be retried or reported?

Return a JSON object:
{{"complete": true/false, "confidence": 0.0-1.0, "missing": "what is still unaddressed (empty if complete)", "stop_reason": "why the response is complete (empty if incomplete)"}}
"""


@dataclass
class CompletionVerdict:
    complete: bool
    confidence: float
    missing: str = ""
    stop_reason: str = ""


async def check_completion(
    user_message: str,
    steps: list[dict],
    response_parts: list[str],
) -> CompletionVerdict:
    """Call a lightweight model to check if the orchestrator's response is complete."""
    from google import genai
    from google.genai import types

    from self_improving_ai.config import settings

    tools_summary = "\n".join(
        f"- {s['action']}: {s['detail']}" for s in steps
    ) if steps else "(no tools called)"

    response_text = response_parts[-1] if response_parts else "(empty response)"

    prompt = _CHECKER_PROMPT.format(
        user_message=user_message,
        tools_summary=tools_summary,
        response_text=response_text[:2000],
    )

    try:
        client = genai.Client()
        resp = await client.aio.models.generate_content(
            model=settings.agent_model_fallback,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=300,
            ),
        )
        text = resp.text.strip()
        # Parse JSON from the response (handle markdown fences)
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        return CompletionVerdict(
            complete=bool(parsed.get("complete", True)),
            confidence=float(parsed.get("confidence", 0.5)),
            missing=str(parsed.get("missing", "")),
            stop_reason=str(parsed.get("stop_reason", "")),
        )
    except Exception as exc:
        log.warning("Completion check failed, assuming complete: %s", exc)
        return CompletionVerdict(complete=True, confidence=0.5, stop_reason=f"checker error: {exc}")
