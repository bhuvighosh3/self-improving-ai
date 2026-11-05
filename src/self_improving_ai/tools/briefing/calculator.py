"""Restricted Decimal arithmetic with original-field lineage; no arbitrary code."""

import json
from decimal import Decimal, InvalidOperation
from hashlib import sha256


def calculate(operation: str, operands: list[dict], sources: list[dict]) -> dict:
    if operation not in {"sum", "difference", "ratio"}:
        raise ValueError("Unsupported calculation")
    if not operands or (operation != "sum" and len(operands) != 2):
        raise ValueError("Invalid operand count")
    index = {s["id"]: s for s in sources}
    values, currencies = [], set()
    for operand in operands:
        if operand["source_id"] not in index:
            raise ValueError("Unknown source")
        if index[operand["source_id"]].get("currency") != operand["currency"]:
            raise ValueError("Operand currency must match declared source currency")
        value = json.loads(index[operand["source_id"]]["content"])
        for key in operand["field"].split("."):
            value = value[int(key)] if isinstance(value, list) else value[key]
        try:
            number = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("Source field is not numeric") from exc
        if not number.is_finite():
            raise ValueError("Nonfinite number")
        values.append(number)
        currencies.add(operand["currency"])
    if len(currencies) != 1:
        raise ValueError("Currency conversion is not supported")
    if operation == "ratio" and values[1] == 0:
        raise ValueError("Zero denominator")
    result = (sum(values) if operation == "sum" else values[0] - values[1]
              if operation == "difference" else values[0] / values[1])
    signature = json.dumps([operation, operands], sort_keys=True)
    return {"id": "CALC-" + sha256(signature.encode()).hexdigest()[:12],
            "operation": operation, "operands": operands, "value": str(result),
            "currency": None if operation == "ratio" else next(iter(currencies)),
            "scope": "Referenced fields only; not necessarily the complete household"}
