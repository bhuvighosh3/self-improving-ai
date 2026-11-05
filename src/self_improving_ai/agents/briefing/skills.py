"""Three reusable business skills loaded into the ADK briefing agent."""

ROUTINES = {
    "quarterly_review": ["Review goal progress and liquidity", "Review allocation and plan execution",
                         "Follow up unfinished commitments and service needs"],
    "annual_review": ["Confirm goals and household circumstances", "Review allocation and liquidity",
                      "Review beneficiaries and outstanding service commitments"],
    "goal_review": ["Confirm goal amount and timeline", "Review funding sources and missing assumptions",
                    "Agree next steps and responsibilities"],
}

CLIENT_CONTEXT = """
SKILL 1: client_context
Read the supplied authorized originals, recover prior minutes and all task states,
then compare subsequent client, investment and service updates. Distinguish old
intentions, updated intentions and unresolved contradictions. Preserve tentative
wording. A CRM note is not automatically a new change, and a previous meeting date
is not full minutes. Record coverage and missing information. The routine template
is a proposal for this synthetic prototype, not an approved industry standard.
Do not interpret missing updates or no search results as unchanged circumstances.
Return context_summary, changes (field, old_value, new_value, both source_ids and
certainty confirmed/tentative/conflicting) and change_status: changed, unchanged, or
insufficient_information. Use unchanged only with explicit supporting evidence
for the scope being assessed; disclose remaining coverage limitations.
"""

GOAL_IMPACT = """
SKILL 2: goal_impact
Evaluate routine goal progress, client changes and investment/service changes.
For each finding provide source_ids, origin, priority, short rationale, uncertainty
and a concrete question. Link priorities to goals, client concerns, deadlines and
unfinished promises. Merge repeated topics. Use calculator results for numbers;
account cash is not household liquidity, and market-value changes are not returns.
Missing balances stay unknown. A decline alone does not justify selling.
Do not invent urgency, tax eligibility or a recommendation to trade.
"""

MEETING_BRIEF = """
SKILL 3: meeting_brief
Compose exactly six sections with IDs overview, changes, portfolio, priorities,
actions, confirm. Produce a concise client_agenda separately from internal notes.
Register every important statement in claims, using fact/calculation/judgment/unknown.
Each item references its claim_ids; every factual claim cites originals, every
calculation cites calculation_ids, and every judgment gives rationale and
uncertainty. Facts must preserve original tentative wording. Do not treat your
summary as an original source. Unknowns include what was searched and what to ask.
Retain routine review even when no significant change is supported.
"""
