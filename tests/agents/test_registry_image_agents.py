from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.registry_factory import get_agent_registry


def test_registry_includes_framework_agents_with_image_tools(monkeypatch) -> None:
    """Image generation is now a tool mounted on the generic framework agents
    (``langgraph`` / ``microsoft-agent-framework``) rather than a dedicated
    agent_type. Verify those agents are registered and expose the image tool.
    """
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "")
    get_agent_registry.cache_clear()
    registry = get_agent_registry()
    agent_types = registry.list_agent_types()
    assert AgentType.LANGGRAPH in agent_types
    assert AgentType.MICROSOFT_AGENT_FRAMEWORK in agent_types
