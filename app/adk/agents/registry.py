"""Local agent registry for lazy loading and discovery.

Replaces the hardcoded if/elif chain in __init__.py with a declarative
registry. Each agent is registered with metadata and loaded on first access.
"""

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentEntry:
    """Metadata for a registered agent."""

    name: str
    module_path: str  # Relative to agents package, e.g. ".ken_e_agent"
    attr_name: str  # Attribute to import, e.g. "ken_e_agent"
    description: str
    capabilities: list[str] = field(default_factory=list)


class AgentRegistry:
    """Registry for local in-process agents with lazy loading.

    Agents are registered declaratively and loaded on first access.
    Subsequent accesses return the cached instance.
    """

    def __init__(self) -> None:
        self._entries: dict[str, AgentEntry] = {}
        self._cache: dict[str, Any] = {}
        self._aliases: dict[str, str] = {}

    def register(self, entry: AgentEntry) -> None:
        """Register an agent entry.

        Args:
            entry: Agent metadata including module path and attribute name
        """
        self._entries[entry.name] = entry

    def alias(self, alias_name: str, target_name: str) -> None:
        """Create an alias that resolves to another agent name.

        Args:
            alias_name: The alias to create
            target_name: The registered agent name it points to
        """
        self._aliases[alias_name] = target_name

    def get(self, name: str) -> Any:
        """Get an agent by name, lazy-loading on first access.

        Args:
            name: Agent name or alias

        Returns:
            The loaded agent instance

        Raises:
            KeyError: If no agent with that name is registered
        """
        resolved_name = self._aliases.get(name, name)

        if resolved_name in self._cache:
            return self._cache[resolved_name]

        if resolved_name not in self._entries:
            raise KeyError(
                f"No agent registered with name {name!r}. "
                f"Available: {list(self._entries.keys())}"
            )

        entry = self._entries[resolved_name]
        try:
            module = importlib.import_module(entry.module_path, package=__package__)
            agent = getattr(module, entry.attr_name)
            self._cache[resolved_name] = agent
            logger.info(f"Loaded agent {resolved_name!r} from {entry.module_path}")
            return agent
        except Exception as e:
            logger.error(f"Failed to load agent {resolved_name!r}: {e}")
            raise

    def find_by_capability(self, capability: str) -> list[AgentEntry]:
        """Find agents that have a given capability.

        Args:
            capability: Capability string to search for

        Returns:
            List of matching AgentEntry objects
        """
        return [
            entry
            for entry in self._entries.values()
            if capability in entry.capabilities
        ]

    def list_agents(self) -> list[AgentEntry]:
        """List all registered agent entries.

        Returns:
            List of all AgentEntry objects
        """
        return list(self._entries.values())


# Module-level singleton
_registry = AgentRegistry()

# Register all known agents
_registry.register(AgentEntry(
    name="ken_e",
    module_path=".ken_e_agent",
    attr_name="ken_e_agent",
    description="Frontend-facing chat agent for company news and analytics",
    capabilities=["chat", "marketing", "news", "analytics"],
))

_registry.register(AgentEntry(
    name="news",
    module_path=".company_news_chatbot.agent",
    attr_name="root_agent",
    description="Specialized agent for company news and financial data",
    capabilities=["news", "financial"],
))

_registry.register(AgentEntry(
    name="google_analytics",
    module_path=".google_analytics_agent_v4",
    attr_name="google_analytics_agent_v4",
    description="Specialized agent for Google Analytics queries",
    capabilities=["analytics", "ga4"],
))

_registry.register(AgentEntry(
    name="strategy",
    module_path=".create_strategy_docs_supervisor",
    attr_name="create_strategy_docs_supervisor",
    description="Supervisor agent for strategy document generation",
    capabilities=["strategy", "documents"],
))

# Backward-compatible aliases
_registry.alias("root_agent", "ken_e")
_registry.alias("multi_agent_root", "strategy")


def get_registry() -> AgentRegistry:
    """Get the module-level agent registry singleton."""
    return _registry
