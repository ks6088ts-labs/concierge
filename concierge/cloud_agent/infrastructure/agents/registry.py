"""Default agent registry.

Agents are registered here at application startup.
"""

from __future__ import annotations

from functools import lru_cache

from concierge.cloud_agent.application.agents import AgentRegistry
from concierge.cloud_agent.infrastructure.agents.echo_agent import EchoAgent


@lru_cache(maxsize=1)
def get_agent_registry() -> AgentRegistry:
    """Return the default AgentRegistry with all built-in agents registered."""
    registry = AgentRegistry()
    registry.register(EchoAgent())
    return registry
