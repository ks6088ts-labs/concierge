"""Unit tests for GitHub Copilot SDK tool builders.

These tests instantiate the builders directly and inspect the resulting
:class:`copilot.tools.Tool` objects (name, schema, skip_permission,
handler return values). The Copilot CLI is *not* spawned — the handler
is invoked manually with a fake :class:`copilot.tools.ToolInvocation`.
"""

from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any

import pytest
from copilot.tools import Tool, ToolInvocation

from concierge.agents.infrastructure.tools import (
    build_echo_copilot_sdk_tool,
    image_gen_copilot_sdk_tool_factory,
)

# ---------------------------------------------------------------------------
# Tests: build_echo_copilot_sdk_tool
# ---------------------------------------------------------------------------


def test_build_echo_copilot_sdk_tool_returns_tool_with_expected_metadata() -> None:
    side_outputs: dict[str, Any] = {}

    tool = build_echo_copilot_sdk_tool(side_outputs)

    assert isinstance(tool, Tool)
    assert tool.name == "echo"
    assert tool.description == "Echo back the given text exactly."
    assert tool.skip_permission is True
    assert tool.parameters is not None
    assert "text" in tool.parameters["properties"]


@pytest.mark.anyio
async def test_build_echo_copilot_sdk_tool_handler_echoes_text() -> None:
    side_outputs: dict[str, Any] = {}
    tool = build_echo_copilot_sdk_tool(side_outputs)

    result = await tool.handler(
        ToolInvocation(
            session_id="s1",
            tool_call_id="tc1",
            tool_name="echo",
            arguments={"text": "hello"},
        )
    )

    assert result.result_type == "success"
    assert result.text_result_for_llm == "hello"
    # Echo tool emits no side outputs.
    assert side_outputs == {}


def test_build_echo_copilot_sdk_tool_produces_independent_instances() -> None:
    """Each invocation returns a fresh tool with its own closure."""
    side1: dict[str, Any] = {}
    side2: dict[str, Any] = {}

    tool1 = build_echo_copilot_sdk_tool(side1)
    tool2 = build_echo_copilot_sdk_tool(side2)

    assert tool1 is not tool2
    assert tool1.handler is not tool2.handler


# ---------------------------------------------------------------------------
# Tests: image_gen_copilot_sdk_tool_factory
# ---------------------------------------------------------------------------


def test_image_gen_copilot_sdk_tool_factory_returns_builder() -> None:
    builder = image_gen_copilot_sdk_tool_factory("/tmp/images")

    assert callable(builder)

    side_outputs: dict[str, Any] = {}
    tool = builder(side_outputs)

    assert isinstance(tool, Tool)
    assert tool.name == "generate_image_tool"
    assert tool.skip_permission is True
    assert tool.parameters is not None
    props = tool.parameters["properties"]
    assert "prompt" in props
    assert "size" in props
    assert "n" in props
    # Builder writes the per-request accumulator into side_outputs.
    assert side_outputs["images"] == []


@pytest.mark.anyio
async def test_image_gen_copilot_sdk_tool_handler_invokes_generate_image(tmp_path, monkeypatch) -> None:
    """The handler delegates to ``generate_image`` and writes images into side_outputs."""

    captured: dict[str, Any] = {}

    async def fake_generate_image(prompt: str, **kwargs: Any) -> Any:
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            images=[
                SimpleNamespace(
                    b64_json=base64.b64encode(b"png").decode("utf-8"),
                    path=str(tmp_path / "img-1.png"),
                    revised_prompt="rev",
                )
            ],
            model="gpt-image-2",
            size="1024x1024",
        )

    monkeypatch.setattr(
        "concierge.agents.infrastructure.tools.image_generation_tool.generate_image",
        fake_generate_image,
    )

    side_outputs: dict[str, Any] = {}
    builder = image_gen_copilot_sdk_tool_factory(str(tmp_path))
    tool = builder(side_outputs)

    result = await tool.handler(
        ToolInvocation(
            session_id="s1",
            tool_call_id="tc1",
            tool_name="generate_image_tool",
            arguments={"prompt": "A cat", "size": "1024x1024", "n": 1},
        )
    )

    assert result.result_type == "success"
    assert captured["prompt"] == "A cat"
    assert captured["kwargs"] == {"size": "1024x1024", "n": 1, "save_dir": str(tmp_path)}
    # side_outputs is populated with the generated image metadata.
    assert len(side_outputs["images"]) == 1
    assert side_outputs["images"][0]["path"] == str(tmp_path / "img-1.png")
    assert side_outputs["images"][0]["revised_prompt"] == "rev"


@pytest.mark.anyio
async def test_image_gen_copilot_sdk_tool_handler_failure_returns_failure_result(monkeypatch) -> None:
    """An exception in ``generate_image`` is converted to a failure ToolResult by define_tool."""

    async def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("upstream failure")

    monkeypatch.setattr(
        "concierge.agents.infrastructure.tools.image_generation_tool.generate_image",
        boom,
    )

    builder = image_gen_copilot_sdk_tool_factory("/tmp/imgs")
    tool = builder({})

    result = await tool.handler(
        ToolInvocation(
            session_id="s1",
            tool_call_id="tc1",
            tool_name="generate_image_tool",
            arguments={"prompt": "boom"},
        )
    )

    assert result.result_type == "failure"
    assert result.error is not None
    assert "upstream failure" in result.error


def test_registry_includes_copilot_sdk_tools() -> None:
    """The GitHub Copilot SDK agent in the default registry exposes the tool builders."""
    from concierge.agents.infrastructure.github_copilot_sdk_agent import GitHubCopilotSdkAgent
    from concierge.agents.infrastructure.registry_factory import get_agent_registry

    get_agent_registry.cache_clear()
    registry = get_agent_registry()
    agent = registry.resolve("github-copilot-sdk")
    assert isinstance(agent, GitHubCopilotSdkAgent)

    # Sanity check the builder list directly so the registry wiring is verified
    # without spawning a real Copilot CLI subprocess.
    assert len(agent._tool_builders) == 2
    # Calling the builders with a fresh side_outputs dict must yield Tool instances.
    side_outputs: dict[str, Any] = {}
    for builder in agent._tool_builders:
        built = builder(side_outputs)
        assert isinstance(built, Tool)
