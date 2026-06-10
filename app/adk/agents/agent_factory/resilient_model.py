"""Registry-level retry wiring for every Gemini model call.

Problem
-------
google-genai treats ``retry_options=None`` as a **never-retry** policy
(``retry_args(None)`` → ``tenacity.stop_after_attempt(1)``), and ADK's
``LLMRegistry.new_llm`` constructs a bare ``Gemini`` for every string model —
which is how every KEN-E agent is built (``builder.py`` passes
``config.model`` straight through). Net effect: one transient 429/503 from
Vertex kills the whole turn. Vertex Gemini models carry no per-project quota;
429 means momentary shared-pool contention and Google's documented remedy is
client-side exponential backoff. Quantified in
``docs/spike-vertex-429-long-running-tasks.md``.

Solution
--------
``ResilientGemini`` defaults ``retry_options`` to an empty
``HttpRetryOptions()``, which activates the SDK's full default policy:
5 attempts, exponential backoff 1 s → 60 s (base 2, jitter), retrying
408/429/500/502/503/504 plus connect/timeout errors (~15 s worst-case added
latency before a terminal failure — acceptable for chat turns).

``ensure_resilient_gemini_registered()`` re-registers the gemini-* regexes in
ADK's ``LLMRegistry`` so **every string-model agent in the process** — root,
specialists, review-loop reviewers, AgentTool leaves — resolves to this class
with zero changes at construction sites. ``LLMRegistry.resolve`` is
``lru_cache``d, so registration also clears that cache.

The call site is ``model_routing.apply_model_location_env()``, which already
runs at deploy build time (``hierarchy.build_hierarchy``) and per chat turn
(``sub_agent_attacher.attach_specialists_before_agent_callback``) — i.e. in
the deployed Agent Engine process before any model call, with no pickling of
registry state required.
"""

from __future__ import annotations

from google.adk.models.google_llm import Gemini
from google.adk.models.registry import LLMRegistry
from google.genai import types as genai_types
from pydantic import Field

from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

_REGISTERED = False


class ResilientGemini(Gemini):
    """``Gemini`` with default exponential-backoff retry on transient errors.

    An empty ``HttpRetryOptions()`` is NOT a no-op: genai fills every unset
    field with its defaults (attempts=5, initial_delay=1 s, max_delay=60 s,
    exp_base=2, jitter, http_status_codes=408/429/5xx), whereas ``None`` is
    the never-retry policy.
    """

    retry_options: genai_types.HttpRetryOptions | None = Field(
        default_factory=genai_types.HttpRetryOptions
    )


def ensure_resilient_gemini_registered(force: bool = False) -> None:
    """Idempotently make gemini-* string models resolve to ``ResilientGemini``.

    Args:
        force: Re-register even if this process already did (test hook).
    """
    global _REGISTERED
    if _REGISTERED and not force:
        return

    LLMRegistry.register(ResilientGemini)
    # resolve() is lru_cached; drop any resolutions made before registration.
    LLMRegistry.resolve.cache_clear()
    _REGISTERED = True
    logger.info("ResilientGemini registered for gemini-* model strings.")
