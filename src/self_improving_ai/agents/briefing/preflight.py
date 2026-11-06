"""Compute the basic snapshot total before asking the model to write about it."""

import json

from self_improving_ai.tools.briefing.agent_tools import execute_calculation


def prepare_snapshot_total(state: dict, trace: list):
    evidence = state["meeting_evidence"]
    source = next((s for s in evidence["sources"] if s["id"] == "HOLDINGS"), None)
    if not source:
        return
    holdings = json.loads(source["content"])
    operands = [{"source_id": "HOLDINGS", "currency": source["currency"],
                 "field": f"accounts.{a}.holdings.{p}.market_value"}
                for a, account in enumerate(holdings.get("accounts", []))
                for p, _ in enumerate(account.get("holdings", []))]
    if not operands:
        return
    record = next((r for r in state.get("meeting_calculations", [])
                   if r["operation"] == "sum" and r["operands"] == operands), None)
    if record is None:
        arguments = {"operation": "sum", "operands": operands}
        trace.append({"event": "tool_call", "tool": "calculate_metrics", "arguments": arguments,
                      "origin": "backend_preflight"})
        record = execute_calculation(**arguments, state=state)
        trace.append({"event": "tool_response", "tool": "calculate_metrics", "result": record,
                      "origin": "backend_preflight"})
        if record["status"] != "ok":
            raise ValueError("Snapshot total could not be verified from original holdings")
    state["meeting_metrics"] = {"snapshot_account_total": record["id"],
        "scope": "Available account holdings only; not household liquidity or spendable cash"}
