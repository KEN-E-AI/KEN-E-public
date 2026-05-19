"""Tests for the AgentRegistry."""

import pytest

from .. import registry as registry_module
from ..registry import AgentEntry, AgentRegistry, validate_registry_at_startup


@pytest.fixture()
def registry() -> AgentRegistry:
    """Fresh registry with test entries."""
    reg = AgentRegistry()
    reg.register(
        AgentEntry(
            name="alpha",
            module_path="json",  # stdlib module — guaranteed importable
            attr_name="loads",
            description="Test agent alpha",
            capabilities=["chat", "analytics"],
        )
    )
    reg.register(
        AgentEntry(
            name="beta",
            module_path="json",
            attr_name="dumps",
            description="Test agent beta",
            capabilities=["analytics"],
        )
    )
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


class TestGetAllConfigDocIds:
    def test_returns_all_config_doc_ids(self):
        reg = AgentRegistry()
        reg.register(
            AgentEntry(
                name="main",
                module_path="json",
                attr_name="loads",
                description="Main agent",
                config_doc_id="main_config",
                sub_config_doc_ids=["sub_a", "sub_b"],
            )
        )
        reg.register(
            AgentEntry(
                name="helper",
                module_path="json",
                attr_name="dumps",
                description="Helper agent",
                config_doc_id="helper_config",
            )
        )
        assert reg.get_all_config_doc_ids() == {
            "main_config",
            "sub_a",
            "sub_b",
            "helper_config",
        }

    def test_empty_when_no_configs(self):
        reg = AgentRegistry()
        reg.register(
            AgentEntry(
                name="plain",
                module_path="json",
                attr_name="loads",
                description="Plain agent with no configs",
            )
        )
        assert reg.get_all_config_doc_ids() == set()

    def test_deduplicates_overlapping_ids(self):
        reg = AgentRegistry()
        reg.register(
            AgentEntry(
                name="a",
                module_path="json",
                attr_name="loads",
                description="Agent A",
                config_doc_id="shared_id",
                sub_config_doc_ids=["shared_id", "unique_a"],
            )
        )
        reg.register(
            AgentEntry(
                name="b",
                module_path="json",
                attr_name="dumps",
                description="Agent B",
                sub_config_doc_ids=["shared_id"],
            )
        )
        assert reg.get_all_config_doc_ids() == {"shared_id", "unique_a"}


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

    def test_all_config_doc_ids_matches_expected(self):
        from ..registry import get_registry

        expected = {
            "ken_e_chatbot",
            "google_analytics_agent",
            "company_news_agent",
            "business_researcher",
            "business_formatter",
            "competitive_researcher",
            "competitive_formatter",
            "marketing_researcher",
            "marketing_formatter",
            "brand_researcher",
            "brand_formatter",
        }
        assert get_registry().get_all_config_doc_ids() == expected


class TestValidateRegistryAtStartup:
    def test_returns_config_ids(self):
        config_ids = validate_registry_at_startup()
        assert isinstance(config_ids, set)
        assert len(config_ids) == 11
        assert "ken_e_chatbot" in config_ids
        assert "google_analytics_agent" in config_ids
        assert "company_news_agent" in config_ids

    def test_raises_on_empty_registry(self, monkeypatch):
        empty_registry = AgentRegistry()
        monkeypatch.setattr(registry_module, "get_registry", lambda: empty_registry)
        with pytest.raises(ValueError, match="No config doc IDs"):
            validate_registry_at_startup()
