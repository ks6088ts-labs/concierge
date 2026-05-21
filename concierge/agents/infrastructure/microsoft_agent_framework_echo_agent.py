"""Microsoft Agent Framework based echo agent."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential
from langchain_core.runnables import RunnableConfig

from concierge.agents.application.contracts import AgentRequest, AgentResponse

RunConfigFactory = Callable[[AgentRequest], RunnableConfig]


def _empty_run_config(_request: AgentRequest) -> RunnableConfig:
    return RunnableConfig()


class MicrosoftAgentFrameworkEchoAgent:
    """Microsoft Agent Framework backed minimal echo agent."""

    agent_type: ClassVar[str] = "microsoft-agent-framework-echo"
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
            self._run_config_factory(request)
            agent = self._build_agent()
            response = await agent.run(message)
        except Exception as exc:  # noqa: BLE001
            return AgentResponse(status="failed", error=f"{type(exc).__name__}: {exc}")

        reply = self._extract_reply(response)
        return AgentResponse(
            status="succeeded",
            result={
                "echo": message,
                "reply": reply,
                "model": self._model,
            },
        )

    @staticmethod
    def _extract_message(payload: dict[str, Any]) -> str:
        value = payload.get("message")
        return value if isinstance(value, str) and value.strip() else ""

    def _build_agent(self) -> Any:
        client = FoundryChatClient(
            model=self._model,
            credential=DefaultAzureCredential(),
        )

        @tool
        def echo(text: str) -> str:
            """Echo back the given text exactly."""
            return text

        return Agent(
            client=client,
            instructions=self._system_prompt,
            tools=[echo],
        )

    @staticmethod
    def _extract_reply(response: Any) -> str:
        text = getattr(response, "text", "")
        return text if isinstance(text, str) else ""
