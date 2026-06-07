"""Bridge: ChatbotResponder backed by a shared concierge.agents.Agent."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

from concierge.agents.application.contracts import Agent, AgentRequest
from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.value_objects import MessageRole


class AgentChatbotResponder:
    """Calls a shared Agent.handle() and yields its reply as a single chunk.

    The yielded "stream" is non-incremental in this issue; true streaming via
    StreamingAgent.stream() will be added in a follow-up.

    This class is intentionally synchronous because FastAPI routes that use it
    are declared with ``def`` (not ``async def``) and therefore execute in a
    thread-pool worker — ``asyncio.run`` is safe in that context.
    """

    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def stream_reply(
        self,
        conversation: Conversation,
        history: list[Message],
        image_url: str | None = None,
    ) -> Iterator[str]:
        # history is newest-first (GenerateBotReplyUseCase.execute specification)
        latest_user_text = next(
            (m.content for m in history if m.role == MessageRole.USER),
            "",
        )
        # Carry an optional camera image to the agent as part of the request
        # payload. The payload is a free-form ``dict[str, Any]`` so this needs no
        # contract change; vision-capable agents (e.g. LangGraph) read
        # ``payload['image_url']`` while others ignore it. The image is
        # request-scoped and never persisted (ephemeral, like realtime voice).
        payload: dict[str, str] = {"message": latest_user_text}
        if image_url:
            payload["image_url"] = image_url
        request = AgentRequest(
            agent_type=self._agent.agent_type,
            payload=payload,
            context={"conversation_id": str(conversation.id)},
        )
        response = asyncio.run(self._agent.handle(request))
        if response.status != "succeeded":
            yield response.error or "(agent returned failed status)"
            return
        result = response.result or {}
        reply = result.get("reply") or result.get("message") or ""
        if reply:
            yield reply
