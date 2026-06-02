"""Agent-as-a-tool implementations (AH-98).

Each module here builds a leaf sub-agent and registers it as an ``AgentTool``
under its catalogue name via ``agent_tool_registry.register_agent_tool``. The
agent factory imports these modules at startup (see
``app/adk/agents/agent_factory/hierarchy.py``) so the registrations are in place
before specialist rosters resolve.
"""
