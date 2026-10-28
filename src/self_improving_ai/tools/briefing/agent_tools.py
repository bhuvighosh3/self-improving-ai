"""ADK tools pin identity/cutoff and retain actual calculations in session state."""

from google.adk.tools import ToolContext

from self_improving_ai.tools.briefing.context import prepare_context
from self_improving_ai.tools.briefing.calculator import calculate
from self_improving_ai.agents.briefing.ledger import register_calculation
from copy import deepcopy


def prepare_meeting_context(client_id: str, tool_context: ToolContext, focus: str = "") -> dict:
    """Load a confirmed client using the server-owned fixture cutoff."""
    existing = tool_context.state.get("meeting_evidence")
    if existing:
        if existing["client_id"] != client_id:
            return {"status": "denied", "error": "Client is locked for this session"}
        return existing
    try:
        evidence = prepare_context(client_id, focus=focus)
    except (LookupError, ValueError) as exc:
        return {"status": "invalid_request", "error": str(exc)}
    tool_context.state["meeting_evidence"] = evidence
    return evidence


def calculate_metrics(operation: str, operands: list[dict[str, str]],
                      tool_context: ToolContext) -> dict:
    """Calculate sourced JSON fields. Operands contain source_id, field and currency."""
    evidence = tool_context.state.get("meeting_evidence")
    if not evidence:
        return {"status": "invalid_request", "error": "Load client evidence first"}
    try:
        result = calculate(operation, operands, evidence["sources"])
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        return {"status": "invalid_request", "error": str(exc)}
    evidence = deepcopy(evidence)
    records = list(tool_context.state.get("meeting_calculations", []))
    register_calculation(evidence, records, result)
    tool_context.state["meeting_evidence"] = evidence
    tool_context.state["meeting_calculations"] = records
    return {"status": "ok", **result}
