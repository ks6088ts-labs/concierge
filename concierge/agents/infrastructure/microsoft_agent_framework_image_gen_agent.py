from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential
from langchain_core.runnables import RunnableConfig

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.agents.infrastructure.tools import generate_image

RunConfigFactory = Callable[[AgentRequest], RunnableConfig]


def _empty_run_config(_request: AgentRequest) -> RunnableConfig:
    return RunnableConfig()


class MicrosoftAgentFrameworkImageGenAgent:
    agent_type: ClassVar[str] = "microsoft-agent-framework-image-gen"
    _run_config_factory: RunConfigFactory = staticmethod(_empty_run_config)

    def __init__(
        self,
        model: str,
        system_prompt: str,
        project_endpoint: str = "",
        run_config_factory: RunConfigFactory | None = None,
    ) -> None:
        self._model = model
        self._system_prompt = system_prompt
        self._project_endpoint = project_endpoint
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
            agent, generated_images = self._build_agent()
            response = await agent.run(message)
        except Exception as exc:  # noqa: BLE001
            return AgentResponse(status="failed", error=f"{type(exc).__name__}: {exc}")

        return AgentResponse(
            status="succeeded",
            result={
                "reply": self._extract_reply(response),
                "tool_calls": self._extract_tool_calls(response),
                "images": generated_images,
                "model": self._model,
            },
        )

    @staticmethod
    def _extract_message(payload: dict[str, Any]) -> str:
        value = payload.get("message")
        return value if isinstance(value, str) and value.strip() else ""

    def _build_agent(self):
        client = FoundryChatClient(
            project_endpoint=self._project_endpoint or None,
            model=self._model,
            credential=DefaultAzureCredential(),
        )
        save_dir = str((Path.cwd() / "generated_images").resolve())
        generated_images: list[dict[str, Any]] = []

        @tool
        async def generate_image_tool(prompt: str, size: str = "1024x1024", n: int = 1) -> dict[str, Any]:
            """Generate images with Foundry gpt-image-2 and return metadata."""
            generated = await generate_image(prompt, size=size, n=n, save_dir=save_dir)
            full_images = [
                {
                    "b64_json": image.b64_json,
                    "path": image.path,
                    "revised_prompt": image.revised_prompt,
                }
                for image in generated.images
            ]
            generated_images.extend(full_images)
            return {
                "images": [
                    {
                        "path": image["path"],
                        "revised_prompt": image["revised_prompt"],
                    }
                    for image in full_images
                ],
                "size": generated.size,
                "model": generated.model,
            }

        return (
            Agent(
                client=client,
                instructions=self._system_prompt,
                tools=[generate_image_tool],
            ),
            generated_images,
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
