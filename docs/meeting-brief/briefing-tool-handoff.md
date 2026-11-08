# Component B catalog tools: implementation handoff

Status: implemented and offline-tested. This file concerns the four tools marked
Briefing on the dashboard. It does not change Component A or C registration.
The catalog is descriptive; the functions below execute the tools.

```python
from self_improving_ai.tools.briefing import (
    get_client_profile,
    get_crm_notes,
    search_market_news,
    check_compliance_flags,
    BRIEFING_TOOLS,
)

profile = get_client_profile("CLI-005")
notes = get_crm_notes("CLI-005", limit=10)
news = search_market_news("inherited IRA RMD", max_results=5)
followups = check_compliance_flags("CLI-005")
```

| Catalog name | Input | Successful result | Source |
| --- | --- | --- | --- |
| `get_client_profile` | `client_id` | Existing flat profile keys plus `_provenance` | Synthetic household profile |
| `get_crm_notes` | `client_id`, `limit=10` | `notes`, `client_id`, `total_available`, `truncated`, `_provenance` | CRM notes, dated descending, cutoff applied before limit |
| `search_market_news` | `query`, `max_results=10` | `results`, `matched_ids`, `includes_distractors`, `relevance_verified=false`, `_provenance` | Dated fixtures or configured Twelve Data news; provenance identifies the source |
| `check_compliance_flags` | `client_id` | `flags`, `assessment_status=not_cleared`, `coverage`, `limitations`, `_provenance` | Team policy checks, missing profile fields and recorded CRM follow-ups |

All tools are read-only. Profile/CRM/holdings fixtures retain their manifest date, currently 2026-10-27. The operational Inbox cutoff is server-owned; it does not refresh dated account facts.
Limits accept integers from 0 to 100, excluding booleans. Unknown clients, invalid
arguments and unavailable files return `status=error`, `error_code` and `error`.
Existing profile keys and the `notes`/`results` envelopes remain compatible.
`BRIEFING_TOOLS` maps these four catalog names to executable callables. ADK
FunctionTool declaration tests check parameter names against the dashboard catalog;
a real ADK Runner with a local model verifies all four function calls offline.

News deliberately retains distractors required by the repository's research
fixtures. Keyword matches are candidate relevance only. Consumers must select
relevant originals; an empty query is an input error and an unmatched query can
still return disclosed distractors. With a configured Twelve Data key, the existing external news adapter is available in AI mode and to legacy callers. Provider failure falls back to disclosed fixtures. Offline brief generation always forces fixture news and never makes external calls.

Compliance flags are confirmation tasks, not legal conclusions. Okafor's missing
state cites PROFILE.state; Patel's recorded follow-up cites the original dated CRM
note. The teammate's age/account, concentration, suitability, beneficiary and unrealized-gain/loss checks are retained as illustrative policy review triggers. They do not establish a violation, regulatory eligibility or a due amount.
An empty list never establishes compliance clearance. The checks do not inspect
regulatory sources or the complete account documentation.

## Meeting Prep integration

`prepare_context` actually calls the compliance tool and retains its result/trace
as COMPLIANCE beside profile/CRM originals. Offline preparation attaches relevant
flags to Items to Confirm and preserves resolvable original references. AI writing
receives the same result and explicit wording boundaries. This is evidence
collection by the backend; it is not represented as an LLM-selected tool call.

The current content/checkpoint version is `content-v4-workspace-integration`, preventing
an interrupted pre-change writer run from resuming with mismatched evidence/rules.
Existing ready drafts remain historical retained drafts; new generation uses these
contracts. No existing ready draft is silently rewritten.

## Integration boundary

These are local fixture adapters, not authenticated production APIs. An autonomous
LLM must receive session-scoped wrappers that bind the authorized client/cutoff;
do not register unrestricted raw client lookups in a shared user session. The
existing backend-controlled preparation already binds the client through its
confirmed MeetingBriefRequest. The next discovery-stage design is separate in
[agent integration design](agent-integration-design.md).

Verification command:

```bash
PYTHONPATH=src python -m pytest tests/test_tools/test_briefing_tools.py -q
```
