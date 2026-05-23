"""Unit tests for the unified MicrosoftAgentFrameworkAgent under its image-generation preset."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from concierge.agents.application.contracts import AgentRequest
from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.microsoft_agent_framework_agent import MicrosoftAgentFrameworkAgent
from concierge.agents.infrastructure.tools import image_gen_maf_tool_factory

_MODEL = "gpt-5"
_SYSTEM_PROMPT = "You are an image generation assistant."
_SAVE_DIR = "/tmp/concierge-test-images"


def _make_request(payload: dict[str, Any]) -> AgentRequest:
    return AgentRequest(
        agent_type=AgentType.MICROSOFT_AGENT_FRAMEWORK,
        payload=payload,
        context={"task_id": "00000000-0000-0000-0000-000000000001"},
    )


def _make_agent(project_endpoint: str = "") -> MicrosoftAgentFrameworkAgent:
    return MicrosoftAgentFrameworkAgent(
        agent_type=AgentType.MICROSOFT_AGENT_FRAMEWORK.value,
        model=_MODEL,
        system_prompt=_SYSTEM_PROMPT,
        tool_builders=[image_gen_maf_tool_factory(_SAVE_DIR)],
        project_endpoint=project_endpoint,
    )


@pytest.mark.anyio
async def test_handle_missing_message_returns_failed() -> None:
    agent = _make_agent()
    output = await agent.handle(_make_request({}))
    assert output.status == "failed"
    assert output.error is not None
    assert "message" in output.error.lower()


@pytest.mark.anyio
async def test_handle_success_returns_images_and_reply() -> None:
    agent = _make_agent()
    mock_framework_agent = AsyncMock()
    mock_framework_agent.run = AsyncMock(
        return_value=SimpleNamespace(
            text="Generated image",
            tool_calls=[{"name": "generate_image_tool", "args": {"prompt": "cat"}}],
        )
    )
    captured_images = [{"b64_json": "base64", "path": "/tmp/generated.png", "revised_prompt": "a cat"}]

    def _fake_build_agent(side_outputs: dict[str, Any]):
        side_outputs["images"] = captured_images
        return mock_framework_agent

    with patch.object(agent, "_build_agent", side_effect=_fake_build_agent):
        output = await agent.handle(_make_request({"message": "draw a cat"}))

    assert output.status == "succeeded"
    assert output.result is not None
    assert output.result["reply"] == "Generated image"
    assert output.result["tool_calls"] == [{"name": "generate_image_tool", "args": {"prompt": "cat"}}]
    assert output.result["images"] == captured_images
    assert output.result["model"] == _MODEL


@pytest.mark.anyio
async def test_handle_framework_exception_returns_failed() -> None:
    agent = _make_agent()
    mock_framework_agent = AsyncMock()
    mock_framework_agent.run = AsyncMock(side_effect=RuntimeError("framework error"))

    with patch.object(agent, "_build_agent", return_value=mock_framework_agent):
        output = await agent.handle(_make_request({"message": "hello"}))

    assert output.status == "failed"
    assert output.error is not None
    assert "RuntimeError" in output.error


@pytest.mark.anyio
async def test_tool_calls_generate_image_with_expected_arguments() -> None:
    agent = _make_agent(project_endpoint="https://example.services.ai.azure.com/api/projects/test")
    captured_tool: dict[str, Any] = {}
    mock_framework_agent = AsyncMock()

    async def _run(_message: str):
        await captured_tool["tool"]("A cat", "1024x1536", 2)
        return SimpleNamespace(text="done", tool_calls=[])

    mock_framework_agent.run = AsyncMock(side_effect=_run)

    def _fake_agent(*_args, **kwargs):
        captured_tool["tool"] = kwargs["tools"][0]
        return mock_framework_agent

    with patch(
        "concierge.agents.infrastructure.microsoft_agent_framework_agent.Agent",
        side_effect=_fake_agent,
    ):
        with patch(
            "concierge.agents.infrastructure.tools.image_generation_tool.generate_image",
            new=AsyncMock(return_value=SimpleNamespace(images=[], model="gpt-image-2", size="1024x1536")),
        ) as mock_generate_image:
            output = await agent.handle(_make_request({"message": "draw something"}))

    assert output.status == "succeeded"
    mock_generate_image.assert_awaited_once()
    assert mock_generate_image.await_args is not None
    called_kwargs = mock_generate_image.await_args.kwargs
    assert called_kwargs["size"] == "1024x1536"
    assert called_kwargs["n"] == 2


def test_agent_type_is_instance_attribute() -> None:
    agent = _make_agent()
    assert agent.agent_type == AgentType.MICROSOFT_AGENT_FRAMEWORK
