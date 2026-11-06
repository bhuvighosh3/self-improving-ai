"""Read-only fixture follow-ups, not a regulatory compliance determination."""

from self_improving_ai.tools.briefing.crm import get_client_profile, get_crm_notes


def check_compliance_flags(client_id: str) -> dict:
    """Return sourced items for advisor confirmation from profile and CRM fixtures.

    Args:
        client_id: The client household identifier.

    Returns:
        Active confirmation flags, source locators and explicit partial coverage.
        An empty flags list is not compliance clearance. No legal rules are inferred
        from synthetic news, and no CRM/account records are modified.
    """
    profile = get_client_profile(client_id)
    if "error" in profile:
        return profile
    notes = get_crm_notes(client_id, limit=100)
    if "error" in notes:
        return notes
    flags = []
    if not profile.get("state"):
        flags.append({"id": f"{client_id}-PROFILE-STATE", "code": "PROFILE_STATE_MISSING",
            "status": "needs_confirmation", "severity": "attention",
            "title": "Confirm the state of residence",
            "description": "The provided profile has no state of residence. Confirm it before any state-specific assessment.",
            "source_ids": ["PROFILE"], "locators": [{"source_id": "PROFILE", "field": "state"}],
            "next_action": "Ask the client to confirm their state of residence."})
    for index, note in enumerate(notes["notes"]):
        if "compliance flag:" not in note["text"].lower():
            continue
        flags.append({"id": f"{client_id}-CRM-{index}", "code": "RECORDED_COMPLIANCE_FOLLOWUP",
            "status": "needs_confirmation", "severity": "attention",
            "title": "Verify a recorded compliance follow-up", "description": note["text"],
            "source_ids": [f"NOTE-{index}"],
            "locators": [{"source_id": f"NOTE-{index}", "date": note["date"], "author": note["author"]}],
            "next_action": "Review original account and beneficiary records with the advisor before confirming any distribution schedule."})
    return {"status": "ok", "client_id": client_id, "flags": flags,
        "assessment_status": "not_cleared", "coverage": "partial_synthetic_records",
        "scope": "Profile completeness and explicitly recorded CRM compliance follow-ups only",
        "limitations": ["An empty flags list does not establish compliance.",
            "Account documentation and applicable regulations have not been independently checked.",
            "Flags identify confirmation work, not established violations."],
        "_provenance": profile["_provenance"]}
