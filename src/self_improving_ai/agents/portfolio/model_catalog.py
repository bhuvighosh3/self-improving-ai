"""Curated text/tool models whose standard API pricing includes a free tier.

Verified against https://ai.google.dev/gemini-api/docs/pricing on 2026-11-02.
This does not establish an account's billing tier, entitlement or remaining quota.
"""

GEMINI_MODELS = [
    {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite",
     "description": "Recommended for this prototype; the live portfolio tool check passed.",
     "free_tier_available": True, "recommended": True},
    {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash-Lite",
     "description": "A lightweight alternative for routine portfolio requests.",
     "free_tier_available": True, "recommended": False},
    {"id": "gemini-3.6-flash", "label": "Gemini 3.6 Flash",
     "description": "A previous-generation Flash option for general agent tasks.",
     "free_tier_available": True, "recommended": False},
    {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash",
     "description": "A newer Flash option; our last attempt received a temporary busy response.",
     "free_tier_available": True, "recommended": False},
]

FREE_TIER_MODEL_IDS = frozenset(model["id"] for model in GEMINI_MODELS)
DEFAULT_MODEL = "gemini-3.5-flash-lite"
