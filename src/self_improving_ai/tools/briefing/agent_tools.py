"""ADK tools pin identity/cutoff and retain actual calculations in session state."""

from google.adk.tools import ToolContext

from self_improving_ai.tools.briefing.context import prepare_context
from self_improving_ai.tools.briefing.calculator import calculate
from self_improving_ai.tools.briefing.compliance import check_compliance_flags
from self_improving_ai.agents.briefing.ledger import register_calculation
from copy import deepcopy
import json
from typing import Literal
from pydantic import BaseModel
from self_improving_ai.agents.briefing.instructions import evidence_for_model


def prepare_meeting_context(client_id: str, tool_context: ToolContext, focus: str = "") -> dict:
    """Load a confirmed client using the server-owned fixture cutoff."""
    existing = tool_context.state.get("meeting_evidence")
    if existing:
        if existing["client_id"] != client_id:
            return {"status": "denied", "error": "Client is locked for this session"}
        return evidence_for_model(existing)
    try:
        evidence = prepare_context(client_id, focus=focus)
    except (LookupError, ValueError) as exc:
        return {"status": "invalid_request", "error": str(exc)}
    tool_context.state["meeting_evidence"] = evidence
    return evidence_for_model(evidence)


class CalculationOperand(BaseModel):
    source_id: str
    field: str
    currency: str


def _numeric_fields(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _numeric_fields(item, f"{prefix}.{key}" if prefix else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _numeric_fields(item, f"{prefix}.{index}")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield prefix


def calculate_metrics(operation: Literal["sum", "difference", "ratio"], operands: list[CalculationOperand],
                      tool_context: ToolContext) -> dict:
    """Use sum, difference or ratio. JSON field paths use dots, e.g. accounts.0.holdings.0.market_value."""
    return execute_calculation(operation, operands, tool_context.state)


def execute_calculation(operation, operands, state):
    """Shared calculator implementation for ADK calls and explicit backend preflight."""
    evidence = state.get("meeting_evidence")
    if not evidence:
        return {"status": "invalid_request", "error": "Load client evidence first"}
    operation = operation.strip().lower()
    operands = [o.model_dump() if isinstance(o, CalculationOperand) else o for o in operands]
    try:
        result = calculate(operation, operands, evidence["sources"])
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        fields = {}
        for source in evidence["sources"]:
            if source["id"] not in {o.get("source_id") for o in operands}:
                continue
            try:
                fields[source["id"]] = list(_numeric_fields(json.loads(source["content"])))[:30]
            except (ValueError, TypeError):
                pass
        return {"status": "invalid_request", "error": str(exc),
                "allowed_operations": ["sum", "difference", "ratio"], "valid_numeric_fields": fields}
    evidence = deepcopy(evidence)
    records = list(state.get("meeting_calculations", []))
    register_calculation(evidence, records, result)
    state["meeting_evidence"] = evidence
    state["meeting_calculations"] = records
    return {"status": "ok", **result}


def check_compliance(client_id: str, tool_context: ToolContext) -> dict:
    """Check compliance flags for a client. Returns active flags with severity."""
    evidence = tool_context.state.get("meeting_evidence")
    if evidence and evidence["client_id"] != client_id:
        return {"status": "denied", "error": "Client is locked for this session"}
    return check_compliance_flags(client_id)
