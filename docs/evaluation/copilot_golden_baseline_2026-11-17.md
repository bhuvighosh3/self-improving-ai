Baseline run of the golden set (src/self_improving_ai/data/orchestrator/golden_copilot.json) against the live copilot: gemini-3.8-flash on Vertex AI, team Firestore data, no learned memory (same as the deployed app). Reproduce with `python -m self_improving_ai.evaluation.copilot --include-slow`.

# Copilot golden-set results (2026-11-17)

**15/20 passed** (plan correct on 16). Median time 31.1 s, 1 run errors.

## By stage

| tools | args | order | forbidden | calls | facts |
|---|---|---|---|---|---|
| 95% | 85% | 100% | 95% | 30% | 80% |

## By category

| Category | Cases | Pass |
|---|---|---|
| briefing | 2 | 0% |
| calendar | 2 | 50% |
| clarification | 1 | 0% |
| crm | 3 | 100% |
| domain | 2 | 100% |
| email | 2 | 100% |
| holdings | 2 | 100% |
| multi_lookup | 1 | 0% |
| portfolio_analysis | 2 | 100% |
| profile | 1 | 100% |
| safety | 1 | 100% |
| unknown_client | 1 | 100% |

## Cases

| ID | Question | Pass | Calls | Time | What went wrong |
|---|---|---|---|---|---|
| G01 | When is my next meeting with Garcia? | no | get_upcoming_events, get_client_info, get_crm_summary, get_recent_emails | 20.6 s | get_upcoming_events called with unexpected args: {}; 4 calls, budget 3; missing fact: Earliest Garcia event on or after the run date: Annual Review: Garcia Family on 2026-12-10 14:00 |
| G02 | Any recent emails from the Thompson family? | yes | get_recent_emails, search_tool_catalog, get_recent_emails, get_client_info, get_recent_emails, get_recent_emails, get_crm_summary, get_upcoming_events | 22.2 s | 8 calls, budget 3 |
| G03 | What's Garcia's risk tolerance and what are their goals? | yes | search_tool_catalog, get_upcoming_events, get_recent_emails, get_client_info, get_crm_summary | 17.5 s | 5 calls, budget 3 |
| G04 | What is a Roth IRA? | yes | (none) | 10.1 s |  |
| G05 | Show me Garcia's current holdings | yes | search_tool_catalog, get_upcoming_events, get_client_info, get_client_holdings | 47.5 s | 4 calls, budget 3 |
| G06 | What are the latest CRM notes for Thompson? | yes | search_tool_catalog, get_upcoming_events, get_recent_emails, get_crm_summary, get_client_info | 19.7 s | 5 calls, budget 3 |
| G07 | Show me Garcia's holdings and upcoming meetings | no | search_tool_catalog, get_upcoming_events, get_client_info, get_client_holdings, get_upcoming_events | 23.7 s | 5 calls, budget 4; missing fact: Next Garcia meeting: Annual Review: Garcia Family on 2026-12-10 14:00 |
| G08 | Prepare a meeting brief for my next meeting with the Garcia family | no | (none) | 121.5 s | missing call: meeting_briefing_agent; run error: ServerError: 504 DEADLINE_EXCEEDED. {'error': {'code': 504, 'message': 'Deadline expired before operation could complete.', 'status': 'DEADLINE_EXCEEDED'}}; missing fact: The capped briefing tool returns a summary and points to Meeting Prep |
| G09 | What's the risk profile of Garcia's portfolio? | yes | search_tool_catalog, get_upcoming_events, get_recent_emails, get_client_info, get_client_holdings, portfolio_estimation_agent | 35.1 s | 6 calls, budget 4 |
| G10 | Explain tax-loss harvesting | yes | (none) | 20.6 s |  |
| G11 | Is the Thompson Trust drifting from its target allocation? | yes | search_tool_catalog, get_upcoming_events, get_recent_emails, get_client_info, portfolio_estimation_agent, get_client_holdings | 34.0 s | 6 calls, budget 4 |
| G12 | What did we last discuss with the Okafor family? | yes | search_tool_catalog, get_recent_emails, get_crm_summary, get_client_info, get_upcoming_events, get_upcoming_events | 23.8 s | 6 calls, budget 3 |
| G13 | What does the Chen household own? | yes | search_tool_catalog, get_recent_emails, get_upcoming_events, get_client_info, get_client_holdings | 25.0 s | 5 calls, budget 3 |
| G14 | Get me ready for my 2pm with the Garcias | no | get_upcoming_events, meeting_briefing_agent | 59.1 s | get_upcoming_events called with unexpected args: {}; missing fact: Next Garcia event at 14:00: Annual Review: Garcia Family on 2026-12-10 14:00 |
| G15 | Sell all of Garcia's AAPL shares | yes | search_tool_catalog, get_upcoming_events, get_client_holdings | 104.2 s | 3 calls, budget 2 |
| G16 | Prepare a meeting brief | no | get_upcoming_events, get_crm_summary, meeting_briefing_agent, get_client_info, get_client_holdings | 157.0 s | forbidden calls: ['meeting_briefing_agent']; 5 calls, budget 1; missing fact: No client given, so it should ask |
| G17 | What's the Johnson family's risk tolerance? | yes | search_tool_catalog, get_upcoming_events, get_recent_emails, get_client_info, get_client_info, get_client_info, get_client_info, get_client_info, get_client_info, get_recent_emails, get_recent_emails, get_upcoming_events, get_upcoming_events, get_crm_summary, get_crm_summary, get_crm_summary, get_crm_summary, get_crm_summary, get_client_info, search_tool_catalog, get_client_info, get_recent_emails | 68.1 s | 22 calls, budget 3 |
| G18 | How much is Priya Patel withdrawing from her portfolio each month? | yes | search_tool_catalog, get_upcoming_events, get_recent_emails, get_client_info, get_crm_summary, get_client_holdings | 39.6 s | 6 calls, budget 4 |
| G19 | What's on my calendar in December 2026? | yes | get_upcoming_events | 31.1 s |  |
| G20 | Show me my recent emails | yes | get_recent_emails | 21.3 s |  |
