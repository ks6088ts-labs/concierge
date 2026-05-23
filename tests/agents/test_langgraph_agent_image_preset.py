"""Unit tests for the unified LangGraphAgent under its image-generation preset."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages.tool import ToolCall

from concierge.agents.application.contracts import AgentRequest
from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.langgraph_agent import LangGraphAgent
from concierge.agents.infrastructure.tools import image_gen_langchain_tool_factory

_MODEL = "azure_ai:gpt-5"
_SYSTEM_PROMPT = "You are an image generation assistant."
_SAVE_DIR = "/tmp/concierge-test-images"


def _make_request(payload: dict[str, Any]) -> AgentRequest:
    return AgentRequest(
        agent_type=AgentType.LANGGRAPH,
        payload=payload,
        context={"task_id": "00000000-0000-0000-0000-000000000001"},
    )


def _make_agent() -> LangGraphAgent:
    return LangGraphAgent(
        agent_type=AgentType.LANGGRAPH.value,
        model=_MODEL,
        system_prompt=_SYSTEM_PROMPT,
        tool_builders=[image_gen_langchain_tool_factory(_SAVE_DIR)],
    )


def _make_agent_result() -> dict[str, list[AIMessage]]:
    ai_message = AIMessage(content="Image generated.")
    ai_message.tool_calls = [
        ToolCall(
            name="generate_image_tool",
            args={"prompt": "a cat", "size": "1024x1024", "n": 1},
            id=None,
            type="tool_call",
        )
    ]
    return {"messages": [ai_message]}


@pytest.mark.anyio
async def test_handle_missing_message_returns_failed() -> None:
    agent = _make_agent()
    output = await agent.handle(_make_request({}))
    assert output.status == "failed"
    assert output.error is not None
    assert "message" in output.error.lower()


@pytest.mark.anyio
async def test_handle_success_returns_tool_calls_and_images() -> None:
    """The image-gen tool builder writes its captured ``generated_images`` list into
    ``side_outputs["images"]``. We simulate that by stubbing ``_build_agent`` so it
    populates the side outputs dict the same way the real implementation does."""
    agent = _make_agent()
    captured_images = [{"b64_json": "base64", "path": "/tmp/generated.png", "revised_prompt": "a cat"}]
    mock_compiled = AsyncMock()
    mock_compiled.ainvoke = AsyncMock(return_value=_make_agent_result())

    def _fake_build_agent(side_outputs: dict[str, Any]):
        side_outputs["images"] = captured_images
        return mock_compiled

    with patch.object(agent, "_build_agent", side_effect=_fake_build_agent):
        output = await agent.handle(_make_request({"message": "draw a cat"}))

    assert output.status == "succeeded"
    assert output.result is not None
    assert output.result["reply"] == "Image generated."
    assert output.result["tool_calls"] == [
        {"name": "generate_image_tool", "args": {"prompt": "a cat", "size": "1024x1024", "n": 1}}
    ]
    assert output.result["images"] == captured_images
    assert output.result["model"] == _MODEL


@pytest.mark.anyio
async def test_tool_calls_generate_image_with_expected_arguments() -> None:
    """End-to-end: the builder produces a real LangChain tool which forwards
    its arguments to ``generate_image``. We patch ``create_agent`` to capture
    that tool and invoke it directly."""
    agent = _make_agent()
    captured_tool: dict[str, Any] = {}
    mock_graph = AsyncMock()

    async def _ainvoke(_inputs, **_kwargs):
        tool_fn = captured_tool["tool"]
        await tool_fn.ainvoke({"prompt": "A cat", "size": "1536x1024", "n": 2})
        return _make_agent_result()

    mock_graph.ainvoke = AsyncMock(side_effect=_ainvoke)

    def _fake_create_agent(*_args, **kwargs):
        captured_tool["tool"] = kwargs["tools"][0]
        return mock_graph

    with patch(
        "concierge.agents.infrastructure.langgraph_agent.create_agent",
        side_effect=_fake_create_agent,
    ):
        with patch("concierge.agents.infrastructure.langgraph_agent.init_chat_model"):
            with patch(
                "concierge.agents.infrastructure.tools.image_generation_tool.generate_image",
                new=AsyncMock(
                    return_value=type(
                        "Result",
                        (),
                        {
                            "images": [
                                type(
                                    "Image", (), {"b64_json": "b64", "path": "/tmp/out.png", "revised_prompt": "cat"}
                                )()
                            ],
                            "model": "gpt-image-2",
                            "size": "1536x1024",
                        },
                    )()
                ),
            ) as mock_generate_image:
                output = await agent.handle(_make_request({"message": "draw something"}))

    assert output.status == "succeeded"
    mock_generate_image.assert_awaited_once()
    assert mock_generate_image.await_args is not None
    called_kwargs = mock_generate_image.await_args.kwargs
    assert called_kwargs["size"] == "1536x1024"
    assert called_kwargs["n"] == 2


def test_agent_type_is_instance_attribute() -> None:
    agent = _make_agent()
    assert agent.agent_type == AgentType.LANGGRAPH
