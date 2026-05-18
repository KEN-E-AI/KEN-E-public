"""Model context-window registry for the Chat component context meter.

Contains context-window token limits only — no pricing fields, no cost math.
Used exclusively to derive context_usage_percent for the status-view bar.

CI lint (`api/scripts/lint/check_context_window_registry_coverage.py`) asserts
that every model= kwarg in app/adk/agents/**/*.py is a key in this registry.
Adding a new model without a registry entry fails the build.
"""

from ..models.chat import ModelContextWindowEntry

# ---------------------------------------------------------------------------
# Context-window values sourced from public model cards.
# Sources:
#   Gemini: https://ai.google.dev/gemini-api/docs/models
#   OpenAI: https://platform.openai.com/docs/models
# ---------------------------------------------------------------------------

MODEL_CONTEXT_WINDOW_REGISTRY: dict[str, ModelContextWindowEntry] = {
    # Gemini 2.5 Flash — 1,048,576 token input context
    # https://ai.google.dev/gemini-api/docs/models#gemini-2.5-flash
    "gemini-2.5-flash": ModelContextWindowEntry(
        model_id="gemini-2.5-flash",
        context_window_max=1_048_576,
    ),
    # Gemini 2.5 Pro — 1,048,576 token input context
    # https://ai.google.dev/gemini-api/docs/models#gemini-2.5-pro
    "gemini-2.5-pro": ModelContextWindowEntry(
        model_id="gemini-2.5-pro",
        context_window_max=1_048_576,
    ),
    # GPT-4o — 128,000 token context window
    # https://platform.openai.com/docs/models/gpt-4o
    "gpt-4o": ModelContextWindowEntry(
        model_id="gpt-4o",
        context_window_max=128_000,
    ),
    # GPT-4o 2024-08-06 — 128,000 token context window
    # https://platform.openai.com/docs/models/gpt-4o
    "gpt-4o-2024-08-06": ModelContextWindowEntry(
        model_id="gpt-4o-2024-08-06",
        context_window_max=128_000,
    ),
}


def get_model_context_window(model_id: str) -> ModelContextWindowEntry:
    """Look up the context-window entry for a model.

    Raises KeyError with a remediation hint if the model is not registered.
    Add missing models to MODEL_CONTEXT_WINDOW_REGISTRY in
    api/src/kene_api/chat/context_windows.py.
    """
    try:
        return MODEL_CONTEXT_WINDOW_REGISTRY[model_id]
    except KeyError:
        raise KeyError(
            f"Model '{model_id}' is not in MODEL_CONTEXT_WINDOW_REGISTRY. "
            "Add it to api/src/kene_api/chat/context_windows.py."
        ) from None
