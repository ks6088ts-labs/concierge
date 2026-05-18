from __future__ import annotations

from concierge.agents.application.contracts import Agent
from concierge.agents.domain.exceptions import AgentNotFoundError


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.agent_type] = agent

    def resolve(self, agent_type: str) -> Agent:
        agent = self._agents.get(agent_type)
        if agent is None:
            raise AgentNotFoundError(agent_type)
        return agent

    def list_agent_types(self) -> list[str]:
        return list(self._agents.keys())
