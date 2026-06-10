"""Single source of truth for the model-identifier catalogue.

Shared by the API layer (hard validation at the write boundary —
``api/src/kene_api/models/agent_config_models.py``) and the ADK agent factory
(advisory warning at load time — ``app/adk/agents/agent_factory/config_loader.py``).
Firestore ``agent_configs`` docs can also be written by MER-E, which has its
own catalogue, so the two repos' lists can lag each other — keep this list in
sync with what is actually served on Vertex.
"""

SUPPORTED_MODELS: frozenset[str] = frozenset(
    {
        # Gemini 3.5 models (GA 2026-05-19)
        "gemini-3.5-flash",
        # Gemini 3 models (preview)
        "gemini-3.1-flash-preview",
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
        # Gemini 2.5 models (stable; retirement floor 2026-10-16 — migrate to
        # 3.x before then). 2.0-flash and 2.0-flash-exp were discontinued
        # upstream 2026-06-01 and are intentionally not listed here.
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        # Gemini 1.5 models (stable fallback)
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        # OpenAI models (used by formatters)
        "gpt-4o",
        "gpt-4o-2024-08-06",
        "gpt-4o-mini",
        "o1-preview",
        "o1-mini",
    }
)
