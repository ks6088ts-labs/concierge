"""Unified Microsoft Agent Framework agent.

A single class that can be configured with any combination of tools.
See :mod:`concierge.agents.infrastructure.langgraph_agent` for the
rationale — this class mirrors :class:`LangGraphAgent` on the Microsoft
Agent Framework side.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_framework import Agent, Content, Message
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

from concierge.agents.application.contracts import AgentRequest, AgentResponse

MAFToolBuilder = Callable[[dict[str, Any]], Any]


class MicrosoftAgentFrameworkAgent:
    """Configurable Microsoft Agent Framework-backed agent."""

    def __init__(
        self,
        *,
        agent_type: str,
        model: str,
        system_prompt: str,
        tool_builders: list[MAFToolBuilder],
        project_endpoint: str = "",
    ) -> None:
        self.agent_type = agent_type
        self._model = model
        self._system_prompt = system_prompt
        self._tool_builders = list(tool_builders)
        self._project_endpoint = project_endpoint

    async def handle(self, request: AgentRequest) -> AgentResponse:
        message = self._extract_message(request.payload)
        image_url = self._extract_image_url(request.payload)
        if not message and not image_url:
            return AgentResponse(
                status="failed",
                error="payload.message is required (non-empty string)",
            )

        side_outputs: dict[str, Any] = {}
        try:
            agent = self._build_agent(side_outputs)
            response = await agent.run(self._build_run_input(message, image_url))
        except Exception as exc:  # noqa: BLE001
            return AgentResponse(status="failed", error=f"{type(exc).__name__}: {exc}")

        response_result: dict[str, Any] = {
            "message": message,
            "reply": self._extract_reply(response),
            "tool_calls": self._extract_tool_calls(response),
            "model": self._model,
        }
        response_result.update(side_outputs)
        return AgentResponse(status="succeeded", result=response_result)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_message(payload: dict[str, Any]) -> str:
        value = payload.get("message")
        return value if isinstance(value, str) and value.strip() else ""

    @staticmethod
    def _extract_image_url(payload: dict[str, Any]) -> str:
        value = payload.get("image_url")
        return value if isinstance(value, str) and value.strip() else ""

    @staticmethod
    def _build_run_input(message: str, image_url: str) -> str | Message:
        """Build the ``agent.run`` input for a single user turn.

        Text-only turns pass the bare ``message`` string (unchanged behaviour).
        When an inline ``data:image/*;base64,…`` URL is supplied, a multimodal
        :class:`~agent_framework.Message` (text + image) is built so a
        vision-capable model can ground its reply in what the user captured.
        ``image_url`` is request-scoped and never persisted. A neutral default
        prompt is used for image-only turns.
        """
        if not image_url:
            return message
        text = message or "Please describe this image."
        return Message(
            "user",
            contents=[Content.from_text(text), Content.from_uri(uri=image_url)],
        )

    def _build_agent(self, side_outputs: dict[str, Any]) -> Any:
        client = FoundryChatClient(
            project_endpoint=self._project_endpoint or None,
            model=self._model,
            credential=DefaultAzureCredential(),
        )
        tools = [builder(side_outputs) for builder in self._tool_builders]
        return Agent(
            client=client,
            instructions=self._system_prompt,
            tools=tools,
        )

    @staticmethod
    def _extract_reply(response: Any) -> str:
        text = getattr(response, "text", "")
        return text if isinstance(text, str) else ""

    @staticmethod
    def _extract_tool_calls(response: Any) -> list[dict[str, Any]]:
        raw = getattr(response, "tool_calls", None) or []
        extracted: list[dict[str, Any]] = []
        for tool_call in raw:
            if isinstance(tool_call, dict):
                extracted.append({"name": tool_call.get("name"), "args": tool_call.get("args")})
        return extracted
