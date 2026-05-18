"""LangGraph-based echo agent.

Minimal LangChain ``create_agent`` agent that exposes a single ``echo`` tool.
It serves as the reference pattern for adding LangChain / LangGraph agents to
the ``cloud_agent`` service.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from azure.identity import DefaultAzureCredential
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from concierge.agents.application.contracts import AgentRequest, AgentResponse

RunConfigFactory = Callable[[AgentRequest], RunnableConfig]
"""Factory that builds a ``RunnableConfig`` for a given request.

The factory is the injection point for cross-cutting concerns such as
tracing callbacks, run metadata, and tags.  Agents themselves stay
decoupled from observability backends; the wiring lives in the registry /
DI layer.
"""


def _empty_run_config(_request: AgentRequest) -> RunnableConfig:
    return RunnableConfig()


class LangGraphEchoAgent:
    """LangChain ``create_agent``-based minimal agent.

    ``AgentRequest.payload["message"]`` is forwarded to the LLM.  The LLM calls
    the ``echo`` tool with the user text verbatim, and the final AI message
    together with the tool-call history are returned in ``AgentResponse.result``.

    The agent is instantiated (``_build_agent``) fresh on every ``handle()``
    call so that Azure credential acquisition does not block worker startup
    when the Foundry endpoint is not yet configured.

    :param model: Model string for ``init_chat_model`` (e.g. ``"azure_ai:gpt-5"``).
    :param system_prompt: System prompt injected into the agent.
    :param run_config_factory: Optional factory producing a
        :class:`RunnableConfig` for each request. Used to inject tracing
        callbacks / run metadata without coupling this class to a specific
        observability backend. Defaults to a no-op factory returning an
        empty config.
    """

    agent_type: ClassVar[str] = "langgraph-echo"

    # Class-level fallback so instances constructed via ``__new__`` (used in
    # some unit tests to bypass settings loading) still have a usable factory.
    _run_config_factory: RunConfigFactory = staticmethod(_empty_run_config)

    def __init__(
        self,
        model: str,
        system_prompt: str,
        run_config_factory: RunConfigFactory | None = None,
    ) -> None:
        self._model = model
        self._system_prompt = system_prompt
        if run_config_factory is not None:
            self._run_config_factory = run_config_factory

    async def handle(self, request: AgentRequest) -> AgentResponse:
        message = self._extract_message(request.payload)
        if not message:
            return AgentResponse(
                status="failed",
                error="payload.message is required (non-empty string)",
            )

        try:
            agent = self._build_agent()
            config = self._run_config_factory(request)
            result = await agent.ainvoke(
                {"messages": [("user", message)]},
                config=config,
            )
        except Exception as exc:  # noqa: BLE001
            return AgentResponse(status="failed", error=f"{type(exc).__name__}: {exc}")

        messages = result.get("messages", []) if isinstance(result, dict) else []
        final_text = self._final_text(messages)
        tool_calls = self._collect_tool_calls(messages)

        return AgentResponse(
            status="succeeded",
            result={
                "echo": message,
                "reply": final_text,
                "tool_calls": tool_calls,
            },
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_message(payload: dict[str, Any]) -> str:
        value = payload.get("message")
        return value if isinstance(value, str) and value.strip() else ""

    def _build_agent(self):
        chat_model = init_chat_model(
            self._model,
            credential=DefaultAzureCredential(),
        )

        @tool
        def echo(text: str) -> str:
            """Echo back the given text exactly."""
            return text

        return create_agent(
            model=chat_model,
            tools=[echo],
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
