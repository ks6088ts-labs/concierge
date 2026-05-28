"""Foundry Agent Service (Prompt Agent) backed agent."""

from __future__ import annotations

from threading import Lock
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.agents.domain.agent_types import AgentType


class FoundryAgentServiceAgent:
    """Foundry Agent Service (Prompt Agent) backed agent."""

    agent_type: str = AgentType.FOUNDRY_AGENT_SERVICE.value

    def __init__(
        self,
        *,
        project_endpoint: str,
        model: str,
        system_prompt: str,
        agent_name: str,
    ) -> None:
        self._project_endpoint = project_endpoint
        self._model = model
        self._system_prompt = system_prompt
        self._agent_name = agent_name
        self._ensured = False
        self._lock = Lock()

    async def handle(self, request: AgentRequest) -> AgentResponse:
        message = self._extract_message(request.payload)
        if not message:
            return AgentResponse(
                status="failed",
                error="payload.message is required (non-empty string)",
            )
        try:
            project = self._build_project_client()
            self._ensure_agent_once(project)
            # pyrefly: ignore[missing-attribute]
            openai = project.get_openai_client()  # ty: ignore[unresolved-attribute]
            conversation = openai.conversations.create()
            response = openai.responses.create(
                conversation=conversation.id,
                extra_body={
                    "agent_reference": {
                        "name": self._agent_name,
                        "type": "agent_reference",
                    }
                },
                input=message,
            )
        except Exception as exc:  # noqa: BLE001
            return AgentResponse(status="failed", error=f"{type(exc).__name__}: {exc}")

        return AgentResponse(
            status="succeeded",
            result={
                "message": message,
                "reply": getattr(response, "output_text", "") or "",
                "model": self._model,
                "agent_name": self._agent_name,
            },
        )

    # --- helpers (private) ---

    @staticmethod
    def _extract_message(payload: dict[str, Any]) -> str:
        value = payload.get("message")
        return value if isinstance(value, str) and value.strip() else ""

    def _build_project_client(self) -> AIProjectClient:
        return AIProjectClient(
            endpoint=self._project_endpoint,
            credential=DefaultAzureCredential(),
        )

    def _ensure_agent_once(self, project: AIProjectClient) -> None:
        with self._lock:
            if self._ensured:
                return
            project.agents.create_version(
                agent_name=self._agent_name,
                definition=PromptAgentDefinition(
                    model=self._model,
                    instructions=self._system_prompt,
                ),
            )
            self._ensured = True
