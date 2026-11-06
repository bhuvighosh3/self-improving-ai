"""Public read-only tools owned by Component B."""

from self_improving_ai.tools.briefing.crm import get_client_profile, get_crm_notes
from self_improving_ai.tools.briefing.news import search_market_news
from self_improving_ai.tools.briefing.compliance import check_compliance_flags

BRIEFING_TOOLS = {
    tool.__name__: tool for tool in
    (get_client_profile, get_crm_notes, search_market_news, check_compliance_flags)
}

__all__ = ["get_client_profile", "get_crm_notes", "search_market_news", "check_compliance_flags", "BRIEFING_TOOLS"]
