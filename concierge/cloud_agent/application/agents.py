from __future__ import annotations

import uuid
from typing import Any, ClassVar, Literal, Protocol

from pydantic import BaseModel


class TaskInput(BaseModel):
    task_id: uuid.UUID
    agent_type: str
    payload: dict[str, Any]


class TaskOutput(BaseModel):
    status: Literal["succeeded", "failed"]
    result: dict[str, Any] | None = None
    error: str | None = None


class Agent(Protocol):
    agent_type: ClassVar[str]

    async def handle(self, task_input: TaskInput) -> TaskOutput: ...


class AgentRegistry:
    """Registry mapping agent_type strings to Agent instances."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.agent_type] = agent

    def resolve(self, agent_type: str) -> Agent:
        from concierge.cloud_agent.domain.exceptions import AgentNotFoundError

        agent = self._agents.get(agent_type)
        if agent is None:
            raise AgentNotFoundError(agent_type)
        return agent

    def list_agent_types(self) -> list[str]:
        return list(self._agents.keys())
