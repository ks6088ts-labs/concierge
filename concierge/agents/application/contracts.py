from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar, Literal, Protocol

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    agent_type: str
    payload: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    status: Literal["succeeded", "failed"]
    result: dict[str, Any] | None = None
    error: str | None = None


class AgentChunk(BaseModel):
    """StreamingAgent chunk event (Protocol declaration only in this release)."""

    delta: str | None = None
    tool_call: dict[str, Any] | None = None
    done: bool = False


class Agent(Protocol):
    agent_type: ClassVar[str]

    async def handle(self, request: AgentRequest) -> AgentResponse: ...


class StreamingAgent(Protocol):
    """Non-breaking extension for streaming agents (declaration only; implementation is a follow-up)."""

    agent_type: ClassVar[str]

    async def stream(self, request: AgentRequest) -> AsyncIterator[AgentChunk]: ...
