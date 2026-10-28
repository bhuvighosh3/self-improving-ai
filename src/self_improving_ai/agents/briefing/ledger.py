"""Register actual calculations as versioned derived sources for further arithmetic."""

import json


def register_calculation(evidence, calculations, result):
    if any(record["id"] == result["id"] for record in calculations):
        return
    calculations.append(result)
    evidence["sources"].append({
        "id": result["id"], "client_id": evidence["client_id"], "kind": "calculation",
        "title": "Verified " + result["operation"], "date": evidence["as_of"],
        "version": "calculator-v1", "author": "Decimal calculator", "read_state": "full",
        "currency": result["currency"], "content": json.dumps(result)})
