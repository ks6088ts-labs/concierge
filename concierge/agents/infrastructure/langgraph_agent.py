"""Unified LangGraph (LangChain ``create_agent``) agent.

A single agent class that can be configured with any combination of tools.
Different *presets* (echo, image generation, …) are produced by passing
different tool builder lists at construction time; the framework wiring
(chat model creation, message extraction, tool-call aggregation) is shared.

The agent is instantiated (``_build_agent``) fresh on every ``handle()``
call so that Azure credential acquisition does not block worker startup
when the Foundry endpoint is not yet configured, and so per-call tool
state (e.g. the ``images`` accumulator on the image-generation preset) is
isolated between requests.

Each tool builder is a ``Callable[[dict[str, Any]], BaseTool]``. The agent
calls every builder once per ``handle()`` with a fresh ``side_outputs``
dict; builders that emit side artifacts (such as generated images) attach
them to that dict, which is merged into ``AgentResponse.result``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from azure.identity import DefaultAzureCredential
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from concierge.agents.application.contracts import AgentRequest, AgentResponse

RunConfigFactory = Callable[[AgentRequest], RunnableConfig]
LangChainToolBuilder = Callable[[dict[str, Any]], Any]


def _empty_run_config(_request: AgentRequest) -> RunnableConfig:
    return RunnableConfig()


class LangGraphAgent:
    """Configurable LangChain ``create_agent``-based agent."""

    _run_config_factory: RunConfigFactory = staticmethod(_empty_run_config)

    def __init__(
        self,
        *,
        agent_type: str,
        model: str,
        system_prompt: str,
        tool_builders: list[LangChainToolBuilder],
        run_config_factory: RunConfigFactory | None = None,
    ) -> None:
        self.agent_type = agent_type
        self._model = model
        self._system_prompt = system_prompt
        self._tool_builders = list(tool_builders)
        if run_config_factory is not None:
            self._run_config_factory = run_config_factory

    async def handle(self, request: AgentRequest) -> AgentResponse:
        message = self._extract_message(request.payload)
        image_url = self._extract_image_url(request.payload)
        if not message and not image_url:
            return AgentResponse(
                status="failed",
                error="payload.message is required (non-empty string)",
            )

        # Build the user turn. When an image is supplied, send a multimodal
        # content list (text + image) so a vision-capable model can ground its
        # reply in what the user captured. ``image_url`` is an inline
        # ``data:image/*;base64,…`` URL (request-scoped, never persisted). A
        # neutral default prompt is used for image-only turns.
        user_turn: tuple[str, str | list[dict[str, Any]]]
        if image_url:
            text = message or "Please describe this image."
            user_turn = (
                "user",
                [
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            )
        else:
            user_turn = ("user", message)

        side_outputs: dict[str, Any] = {}
        try:
            agent = self._build_agent(side_outputs)
            config = self._run_config_factory(request)
            result = await agent.ainvoke(
                {"messages": [user_turn]},
                config=config,
            )
        except Exception as exc:  # noqa: BLE001
            return AgentResponse(status="failed", error=f"{type(exc).__name__}: {exc}")

        messages = result.get("messages", []) if isinstance(result, dict) else []
        response_result: dict[str, Any] = {
            "message": message,
            "reply": self._final_text(messages),
            "tool_calls": self._collect_tool_calls(messages),
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

    def _build_agent(self, side_outputs: dict[str, Any]):
        chat_model = init_chat_model(
            self._model,
            credential=DefaultAzureCredential(),
        )
        tools = [builder(side_outputs) for builder in self._tool_builders]
        return create_agent(
            model=chat_model,
            tools=tools,
            system_prompt=self._system_prompt,
        )

    @staticmethod
    def _final_text(messages: list[Any]) -> str:
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                content = message.content
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts: list[str] = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if isinstance(text, str):
                                parts.append(text)
                    return "".join(parts)
        return ""

    @staticmethod
    def _collect_tool_calls(messages: list[Any]) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        for message in messages:
            tc = getattr(message, "tool_calls", None)
            if not tc:
                continue
            for tool_call in tc:
                collected.append(
                    {
                        "name": tool_call.get("name"),
                        "args": tool_call.get("args"),
                    }
                )
        return collected
