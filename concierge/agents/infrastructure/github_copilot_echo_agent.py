"""GitHub Copilot SDK based echo agent.

This agent intentionally does not call an LLM. It only instantiates a Copilot
client and returns the input message verbatim so CI can validate SDK wiring
without network dependency.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from copilot import CopilotClient
from langchain_core.runnables import RunnableConfig

from concierge.agents.application.contracts import AgentRequest, AgentResponse

RunConfigFactory = Callable[[AgentRequest], RunnableConfig]


def _empty_run_config(_request: AgentRequest) -> RunnableConfig:
    return RunnableConfig()


class GitHubCopilotEchoAgent:
    """Minimal GitHub Copilot SDK echo agent."""

    agent_type: ClassVar[str] = "github-copilot-echo"
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
            # Validate SDK wiring by instantiating the client. We intentionally
            # do not start the CLI subprocess nor create a session: this echo
            # agent must remain offline-safe in CI, while still confirming the
            # SDK import path and constructor surface are intact.
            self._build_client()
        except Exception as exc:  # noqa: BLE001
            return AgentResponse(status="failed", error=f"{type(exc).__name__}: {exc}")

        return AgentResponse(
            status="succeeded",
            result={
                "echo": message,
                "reply": message,
                "client": {"initialized": True, "model": self._model},
            },
        )

    @staticmethod
    def _extract_message(payload: dict[str, Any]) -> str:
        value = payload.get("message")
        return value if isinstance(value, str) and value.strip() else ""

    @staticmethod
    def _build_client() -> CopilotClient:
        return CopilotClient()
