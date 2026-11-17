"""Recheck edited content against server-retained originals, never browser evidence."""

from copy import deepcopy

from self_improving_ai.agents.briefing.checks import check_work


async def check_draft(submitted: dict, original: dict) -> dict:
    for field in ("id", "client_id", "meeting_date", "meeting_time", "focus", "data_as_of",
                  "meeting_type", "timezone", "mode"):
        if submitted.get(field) != original.get(field):
            raise ValueError("Meeting identity or inputs changed; regenerate the draft")
    work = deepcopy(original["workflow"]["work"])
    work["sections"] = submitted["sections"]
    # The reviewer must inspect the edited assertion, not a stale claim ledger.
    claims = {claim["id"]: claim for claim in work["claims"]}
    for section in work["sections"]:
        for item in section["items"]:
            if len(item.get("claim_ids", [])) == 1 and item["claim_ids"][0] in claims:
                claims[item["claim_ids"][0]]["text"] = item["text"]
    report = check_work(work, original["workflow"]["evidence"], original["workflow"]["calculations"])
    if original["mode"] == "agent" and report["verdict"] == "pass":
        from pydantic import ValidationError

        from self_improving_ai.agents.briefing.runtime import semantic_check

        trace = []
        try:
            semantic = await semantic_check(work, original["workflow"]["evidence"],
                                            original["workflow"]["calculations"], trace, model=original["workflow"].get("model"))
        except (ValidationError, ValueError) as exc:
            raise RuntimeError("Automatic review returned an invalid result. Save again before approving.") from exc
        report["verdict"] = semantic["verdict"]
        report["findings"].extend(semantic["findings"])
        report["semantic_support"] = "independent_model_reviewed"
        report["trace"] = trace
    else:
        report["semantic_support"] = "manual_advisor_review_required_offline"
    return report
