"""Tests for the AgentRegistry."""

import pytest

from ..registry import AgentEntry, AgentRegistry


@pytest.fixture()
def registry() -> AgentRegistry:
    """Fresh registry with test entries."""
    reg = AgentRegistry()
    reg.register(AgentEntry(
        name="alpha",
        module_path="json",  # stdlib module — guaranteed importable
        attr_name="loads",
        description="Test agent alpha",
        capabilities=["chat", "analytics"],
    ))
    reg.register(AgentEntry(
        name="beta",
        module_path="json",
        attr_name="dumps",
        description="Test agent beta",
        capabilities=["analytics"],
    ))
    reg.alias("default", "alpha")
    return reg


class TestAgentRegistry:

    def test_get_loads_agent_on_first_access(self, registry: AgentRegistry):
        import json
        result = registry.get("alpha")
        assert result is json.loads

    def test_get_returns_cached_instance(self, registry: AgentRegistry):
        first = registry.get("alpha")
        second = registry.get("alpha")
        assert first is second

    def test_get_unknown_name_raises_key_error(self, registry: AgentRegistry):
        with pytest.raises(KeyError, match="no_such_agent"):
            registry.get("no_such_agent")

    def test_alias_resolves_to_target(self, registry: AgentRegistry):
        import json
        result = registry.get("default")
        assert result is json.loads

    def test_find_by_capability_returns_matching(self, registry: AgentRegistry):
        results = registry.find_by_capability("analytics")
        names = [e.name for e in results]
        assert names == ["alpha", "beta"]

    def test_find_by_capability_no_match(self, registry: AgentRegistry):
        results = registry.find_by_capability("nonexistent")
        assert results == []

    def test_list_agents_returns_all(self, registry: AgentRegistry):
        agents = registry.list_agents()
        names = [e.name for e in agents]
        assert names == ["alpha", "beta"]


class TestModuleLevelRegistry:
    """Test the pre-configured module-level registry."""

    def test_get_registry_returns_singleton(self):
        from ..registry import get_registry
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2

    def test_known_agents_registered(self):
        from ..registry import get_registry
        reg = get_registry()
        names = [e.name for e in reg.list_agents()]
        assert "ken_e" in names
        assert "news" in names
        assert "google_analytics" in names
        assert "strategy" in names

    def test_root_agent_alias_registered(self):
        from ..registry import get_registry
        reg = get_registry()
        # Should not raise — alias is registered
        assert reg._aliases.get("root_agent") == "ken_e"

    def test_multi_agent_root_alias_registered(self):
        from ..registry import get_registry
        reg = get_registry()
        assert reg._aliases.get("multi_agent_root") == "strategy"
