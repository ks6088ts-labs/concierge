"""Unit tests for the unified MicrosoftAgentFrameworkAgent under its echo preset."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.microsoft_agent_framework_agent import MicrosoftAgentFrameworkAgent
from concierge.agents.infrastructure.tools import build_echo_maf_tool

_MODEL = "gpt-5"
_SYSTEM_PROMPT = "You are a minimal echo agent."


def _make_request(payload: dict[str, Any]) -> AgentRequest:
    return AgentRequest(
        agent_type=AgentType.MICROSOFT_AGENT_FRAMEWORK_ECHO,
        payload=payload,
        context={"task_id": "00000000-0000-0000-0000-000000000001"},
    )


def _make_agent() -> MicrosoftAgentFrameworkAgent:
    return MicrosoftAgentFrameworkAgent(
        agent_type=AgentType.MICROSOFT_AGENT_FRAMEWORK_ECHO.value,
        model=_MODEL,
        system_prompt=_SYSTEM_PROMPT,
        tool_builders=[build_echo_maf_tool],
    )


def test_extract_message_returns_message_string() -> None:
    assert MicrosoftAgentFrameworkAgent._extract_message({"message": "hello"}) == "hello"


def test_extract_message_strips_whitespace() -> None:
    assert MicrosoftAgentFrameworkAgent._extract_message({"message": "   "}) == ""


def test_extract_message_missing_key() -> None:
    assert MicrosoftAgentFrameworkAgent._extract_message({}) == ""


def test_extract_message_non_string_value() -> None:
    assert MicrosoftAgentFrameworkAgent._extract_message({"message": 42}) == ""  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_handle_missing_message_returns_failed() -> None:
    agent = _make_agent()
    output: AgentResponse = await agent.handle(_make_request({}))
    assert output.status == "failed"
    assert output.error is not None
    assert "message" in output.error.lower()


@pytest.mark.anyio
async def test_handle_success() -> None:
    agent = _make_agent()
    mock_framework_agent = AsyncMock()
    mock_framework_agent.run = AsyncMock(return_value=SimpleNamespace(text="Hello MAF"))

    with patch.object(agent, "_build_agent", return_value=mock_framework_agent):
        output: AgentResponse = await agent.handle(_make_request({"message": "Hello MAF"}))

    assert output.status == "succeeded"
    assert output.result is not None
    assert output.result["echo"] == "Hello MAF"
    assert output.result["reply"] == "Hello MAF"
    assert output.result["model"] == _MODEL


@pytest.mark.anyio
async def test_handle_framework_exception_returns_failed() -> None:
    agent = _make_agent()
    mock_framework_agent = AsyncMock()
    mock_framework_agent.run = AsyncMock(side_effect=RuntimeError("framework error"))

    with patch.object(agent, "_build_agent", return_value=mock_framework_agent):
        output: AgentResponse = await agent.handle(_make_request({"message": "hello"}))

    assert output.status == "failed"
    assert output.error is not None
    assert "RuntimeError" in output.error
    assert "framework error" in output.error


def test_agent_type_is_instance_attribute() -> None:
    agent = _make_agent()
    assert agent.agent_type == AgentType.MICROSOFT_AGENT_FRAMEWORK_ECHO


def test_registry_includes_microsoft_agent_framework_echo() -> None:
    from concierge.agents.infrastructure.registry_factory import get_agent_registry

    get_agent_registry.cache_clear()
    registry = get_agent_registry()
    assert AgentType.MICROSOFT_AGENT_FRAMEWORK_ECHO in registry.list_agent_types()
    assert AgentType.ECHO in registry.list_agent_types()
