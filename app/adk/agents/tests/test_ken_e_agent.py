"""Test KEN-E agent routing and InstructionProvider."""

import importlib
from unittest.mock import MagicMock, patch

import pytest
from google.adk.agents.llm_agent_config import LlmAgentConfig

from app.adk.agents.utils import config_cache

# Import the module directly (bypass __init__.py's __getattr__ which returns the agent instance)
ken_e_module = importlib.import_module("app.adk.agents.ken_e_agent")

_BASE_INSTRUCTION = ken_e_module._BASE_INSTRUCTION
_make_instruction_provider = ken_e_module._make_instruction_provider
create_ken_e_agent = ken_e_module.create_ken_e_agent


@pytest.fixture(autouse=True)
def _clear_config_cache():
    """Every test starts and ends with a clean agent config cache."""
    config_cache.clear_config_cache()
    yield
    config_cache.clear_config_cache()


def test_ken_e_has_correct_tools():
    """Test that KEN-E only has news and analytics tools."""
    agent = create_ken_e_agent()
    tool_names = [tool.__name__ for tool in agent.tools]

    assert "search_company_news" in tool_names
    assert "query_google_analytics" in tool_names
    assert "create_strategy" not in tool_names  # Should NOT have strategy tool
    assert len(tool_names) == 2  # Only two tools


def test_ken_e_agent_name():
    """Test agent has correct name regardless of config."""
    agent = create_ken_e_agent()
    assert agent.name == "ken_e"


def test_ken_e_instruction_is_callable():
    """Test agent instruction is a callable (InstructionProvider pattern)."""
    agent = create_ken_e_agent()
    assert callable(agent.instruction)


def _seed_cache(doc_id: str, instruction: str, version: str = "v1.0") -> None:
    """Helper: seed the cache so closure reads return a known value."""
    cfg = LlmAgentConfig(
        name=doc_id,
        model="gemini-2.0-flash",
        instruction=instruction,
    )
    with patch.object(config_cache, "load_config_from_firestore") as mock_load:
        mock_load.return_value = (cfg, {"version": version})
        config_cache.get_cached_config(doc_id)


@patch.object(ken_e_module, "load_config_from_firestore")
def test_firestore_config_applied(mock_load):
    """Firestore config fields are applied to the Agent at construction."""
    mock_config = LlmAgentConfig(
        name="ken_e_chatbot",
        model="gemini-2.5-pro",
        instruction="Custom instruction from Firestore",
        description="Custom description",
        generate_content_config={"temperature": 0.3, "max_output_tokens": 2048},
    )
    mock_load.return_value = (mock_config, {"version": "v2.0"})

    agent = create_ken_e_agent()

    assert agent.model == "gemini-2.5-pro"
    assert agent.description == "Custom description"
    assert agent.generate_content_config is not None
    # Instruction is a callable; reading it now goes through the cache.
    assert callable(agent.instruction)

    # Seed cache so the closure returns the Firestore instruction.
    _seed_cache("ken_e_chatbot", "Custom instruction from Firestore", "v2.0")
    ctx = MagicMock()
    ctx.state = {}
    assert agent.instruction(ctx) == "Custom instruction from Firestore"


@patch.object(ken_e_module, "load_config_from_firestore")
def test_firestore_fallback_on_failure(mock_load):
    """Agent uses hardcoded defaults when construction-time Firestore load fails."""
    mock_load.side_effect = Exception("Firestore unavailable")

    agent = create_ken_e_agent()

    assert agent.model == "gemini-2.0-flash"
    assert agent.description == ""
    assert callable(agent.instruction)

    # Closure with a failing cache load must fall back to _BASE_INSTRUCTION.
    with patch.object(config_cache, "load_config_from_firestore") as cache_load:
        cache_load.side_effect = Exception("Firestore still unavailable")
        ctx = MagicMock()
        ctx.state = {}
        assert agent.instruction(ctx) == _BASE_INSTRUCTION


@patch.object(ken_e_module, "load_config_from_firestore")
def test_instruction_provider_uses_cached_firestore_instruction(mock_load):
    """The closure reads the cached Firestore instruction on each turn."""
    custom_instruction = "You are a custom KEN-E agent."
    mock_config = LlmAgentConfig(
        name="ken_e_chatbot",
        model="gemini-2.0-flash",
        instruction=custom_instruction,
    )
    mock_load.return_value = (mock_config, {"version": "v1.1"})

    agent = create_ken_e_agent()

    _seed_cache("ken_e_chatbot", custom_instruction, "v1.1")

    ctx = MagicMock()
    ctx.state = {}
    assert agent.instruction(ctx) == custom_instruction

    ctx.state = {"organization_context": "Acme Corp"}
    result = agent.instruction(ctx)
    assert "Acme Corp" in result
    assert custom_instruction in result
    assert _BASE_INSTRUCTION not in result


@patch.object(ken_e_module, "load_config_from_firestore")
def test_instruction_update_reflects_within_ttl(mock_load):
    """Decision B / AC-6.25: a new instruction in Firestore must show up on
    the next turn after the cache entry expires."""
    initial = LlmAgentConfig(
        name="ken_e_chatbot",
        model="gemini-2.0-flash",
        instruction="version one instruction",
    )
    mock_load.return_value = (initial, {"version": "v1.0"})

    agent = create_ken_e_agent()

    # Seed cache with v1
    _seed_cache("ken_e_chatbot", "version one instruction", "v1.0")
    ctx = MagicMock()
    ctx.state = {}
    assert agent.instruction(ctx) == "version one instruction"

    # Clear cache to simulate TTL expiry, then have Firestore return v2
    config_cache.clear_config_cache()
    _seed_cache("ken_e_chatbot", "version two instruction", "v2.0")

    # Same agent, same closure — new instruction reflected
    assert agent.instruction(ctx) == "version two instruction"


@patch.object(ken_e_module, "load_config_from_firestore")
def test_agent_name_stays_ken_e(mock_load):
    """Agent name must be 'ken_e' regardless of Firestore config."""
    mock_config = LlmAgentConfig(
        name="some_other_name",
        model="gemini-2.5-flash",
        instruction="Some instruction",
    )
    mock_load.return_value = (mock_config, {"version": "v1.0"})

    agent = create_ken_e_agent()
    assert agent.name == "ken_e"


def test_base_instruction_contains_routing_info():
    """Base instruction text preserves its key routing components."""
    assert "KEN-E" in _BASE_INSTRUCTION
    assert "Company News" in _BASE_INSTRUCTION
    assert "Google Analytics" in _BASE_INSTRUCTION
    assert "search_company_news" in _BASE_INSTRUCTION
    assert "query_google_analytics" in _BASE_INSTRUCTION
    assert "Strategy documents are automatically generated" in _BASE_INSTRUCTION


class TestMakeInstructionProvider:
    """Tests for the _make_instruction_provider closure factory.

    Post Sprint 6 Decision B: the closure takes a ``config_doc_id`` and
    reads ``instruction`` from the cache on every turn, so admin PUTs
    propagate within the cache TTL (~60 s) without redeploy.
    """

    def _make_context(self, state: dict) -> MagicMock:
        ctx = MagicMock()
        ctx.state = state
        return ctx

    def _seed(self, doc_id: str, instruction: str) -> None:
        cfg = LlmAgentConfig(
            name=doc_id, model="gemini-2.0-flash", instruction=instruction
        )
        with patch.object(config_cache, "load_config_from_firestore") as mock_load:
            mock_load.return_value = (cfg, {"version": "v1.0"})
            config_cache.get_cached_config(doc_id)

    def test_reads_cached_instruction_each_turn(self):
        """Closure must delegate to get_cached_config; no captured string."""
        self._seed("ken_e_chatbot", "Cached instruction")
        provider = _make_instruction_provider("ken_e_chatbot")
        ctx = self._make_context({})
        assert provider(ctx) == "Cached instruction"

    def test_prepends_org_context(self):
        self._seed("ken_e_chatbot", "Cached base")
        provider = _make_instruction_provider("ken_e_chatbot")
        ctx = self._make_context({"organization_context": "Org info"})
        result = provider(ctx)
        assert "Org info" in result
        assert "Cached base" in result
        assert result.index("[ORGANIZATION CONTEXT]") < result.index("Cached base")

    def test_different_doc_ids_produce_different_instructions(self):
        self._seed("ken_e_chatbot", "Instruction A")
        self._seed("business_researcher", "Instruction B")
        provider_a = _make_instruction_provider("ken_e_chatbot")
        provider_b = _make_instruction_provider("business_researcher")
        ctx = self._make_context({})
        assert provider_a(ctx) == "Instruction A"
        assert provider_b(ctx) == "Instruction B"

    def test_cache_error_falls_back_to_base_instruction(self):
        """If the cache raises (Firestore down, no cached value), the closure
        must not propagate the exception — return _BASE_INSTRUCTION so the
        agent stays functional rather than failing the turn."""
        provider = _make_instruction_provider("ken_e_chatbot")
        with patch.object(config_cache, "get_cached_config") as mock_get:
            mock_get.side_effect = RuntimeError("cache + Firestore both down")
            ctx = self._make_context({})
            assert provider(ctx) == _BASE_INSTRUCTION

    def test_cache_error_with_org_context_still_prepends(self):
        """Even on cache failure, org context should still wrap _BASE_INSTRUCTION."""
        provider = _make_instruction_provider("ken_e_chatbot")
        with patch.object(config_cache, "get_cached_config") as mock_get:
            mock_get.side_effect = RuntimeError("down")
            ctx = self._make_context({"organization_context": "Acme"})
            result = provider(ctx)
            assert "Acme" in result
            assert _BASE_INSTRUCTION in result
