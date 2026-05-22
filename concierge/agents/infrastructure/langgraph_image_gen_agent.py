from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

from azure.identity import DefaultAzureCredential
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.agents.infrastructure.tools import generate_image

RunConfigFactory = Callable[[AgentRequest], RunnableConfig]


def _empty_run_config(_request: AgentRequest) -> RunnableConfig:
    return RunnableConfig()


class LangGraphImageGenAgent:
    agent_type: ClassVar[str] = "langgraph-image-gen"
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
            agent, generated_images = self._build_agent()
            result = await agent.ainvoke(
                {"messages": [("user", message)]},
                config=self._run_config_factory(request),
            )
        except Exception as exc:  # noqa: BLE001
            return AgentResponse(status="failed", error=f"{type(exc).__name__}: {exc}")

        messages = result.get("messages", []) if isinstance(result, dict) else []
        return AgentResponse(
            status="succeeded",
            result={
                "reply": self._final_text(messages),
                "tool_calls": self._collect_tool_calls(messages),
                "images": generated_images,
                "model": self._model,
            },
        )

    @staticmethod
    def _extract_message(payload: dict[str, Any]) -> str:
        value = payload.get("message")
        return value if isinstance(value, str) and value.strip() else ""

    def _build_agent(self):
        chat_model = init_chat_model(
            self._model,
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
            create_agent(
                model=chat_model,
                tools=[generate_image_tool],
                system_prompt=self._system_prompt,
            ),
            generated_images,
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
