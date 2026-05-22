from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.registry_factory import get_agent_registry


def test_registry_includes_image_generation_agents() -> None:
    get_agent_registry.cache_clear()
    registry = get_agent_registry()
    agent_types = registry.list_agent_types()
    assert AgentType.LANGGRAPH_IMAGE_GEN in agent_types
    assert AgentType.MICROSOFT_AGENT_FRAMEWORK_IMAGE_GEN in agent_types
