"""Tests for ``ResilientGemini`` registry-level retry wiring.

Context: genai treats ``retry_options=None`` as a *never-retry* policy
(``retry_args(None)`` → ``stop_after_attempt(1)``), and ADK's
``LLMRegistry.new_llm`` builds a bare ``Gemini`` for every string model — so
without this registration every model call in the process fails permanently on
the first transient 429/503. See ``docs/spike-vertex-429-long-running-tasks.md``.
"""

import pytest
from google.adk.models.google_llm import Gemini
from google.adk.models.registry import LLMRegistry

from app.adk.agents.agent_factory import resilient_model
from app.adk.agents.agent_factory.model_routing import apply_model_location_env
from app.adk.agents.agent_factory.resilient_model import (
    ResilientGemini,
    ensure_resilient_gemini_registered,
)


@pytest.fixture(autouse=True)
def _restore_production_registration():
    """Leave the registry in the production state after each test."""
    yield
    ensure_resilient_gemini_registered(force=True)


def _register_base_gemini() -> None:
    """Simulate the cold-start state where ADK's stock Gemini owns gemini-*."""
    LLMRegistry.register(Gemini)
    LLMRegistry.resolve.cache_clear()


class TestResilientGeminiRegistration:
    def test_new_llm_resolves_to_resilient_gemini_with_retry(self) -> None:
        ensure_resilient_gemini_registered(force=True)
        llm = LLMRegistry.new_llm("gemini-3.5-flash")
        assert isinstance(llm, ResilientGemini)
        assert llm.retry_options is not None

    def test_registration_overrides_stale_resolve_cache(self) -> None:
        # resolve() is lru_cached; a stale cached resolution to stock Gemini
        # must not survive registration.
        _register_base_gemini()
        assert not isinstance(LLMRegistry.new_llm("gemini-2.5-flash"), ResilientGemini)
        ensure_resilient_gemini_registered(force=True)
        assert isinstance(LLMRegistry.new_llm("gemini-2.5-flash"), ResilientGemini)

    def test_idempotent_without_force(self) -> None:
        ensure_resilient_gemini_registered(force=True)
        ensure_resilient_gemini_registered()
        assert isinstance(LLMRegistry.new_llm("gemini-2.5-pro"), ResilientGemini)

    def test_apply_model_location_env_registers(self, monkeypatch) -> None:
        # The per-turn callback path (sub_agent_attacher) and the deploy-time
        # path (build_hierarchy) both run apply_model_location_env(); it must
        # carry the registration so the deployed runtime gets retry without a
        # separate hook.
        _register_base_gemini()
        monkeypatch.setattr(resilient_model, "_REGISTERED", False)
        # apply_model_location_env writes GOOGLE_CLOUD_LOCATION process-wide;
        # registering it with monkeypatch first scopes the write to this test.
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "sentinel-before-apply")
        apply_model_location_env()
        assert isinstance(
            LLMRegistry.new_llm("gemini-3.1-pro-preview"), ResilientGemini
        )


class TestRetryPolicy:
    def test_default_retry_policy_is_not_never_retry(self) -> None:
        # Pins the exact genai boundary this exists for: retry_args(None)
        # returns the never-retry config (no 'retry' predicate, stop after
        # attempt 1); a default ResilientGemini must produce a real policy.
        from google.genai._api_client import retry_args

        llm = ResilientGemini(model="gemini-2.5-flash")
        args = retry_args(llm.retry_options)
        assert "retry" in args

    def test_plain_string_model_round_trips_name(self) -> None:
        ensure_resilient_gemini_registered(force=True)
        llm = LLMRegistry.new_llm("gemini-3.5-flash")
        assert llm.model == "gemini-3.5-flash"
