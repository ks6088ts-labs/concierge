"""Unit tests for the unified LangGraphAgent under its echo preset.

LLM calls are fully mocked; no Azure credentials or network access required.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages.tool import ToolCall

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.langgraph_agent import LangGraphAgent
from concierge.agents.infrastructure.tools import build_echo_langchain_tool

_MODEL = "azure_ai:gpt-5"
_SYSTEM_PROMPT = "You are a minimal echo agent."


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
        tool_builders=[build_echo_langchain_tool],
    )


def _make_agent_result(reply: str, tool_call_name: str = "echo", tool_call_args: dict | None = None) -> dict:
    """Build a fake ``ainvoke`` result that mimics a LangGraph compiled graph output."""
    ai_msg = AIMessage(content=reply)
    ai_msg.tool_calls = [
        ToolCall(name=tool_call_name, args=tool_call_args or {"text": reply}, id=None, type="tool_call")
    ]
    return {"messages": [ai_msg]}


# ---------------------------------------------------------------------------
# Tests: _extract_message
# ---------------------------------------------------------------------------


def test_extract_message_returns_message_string() -> None:
    assert LangGraphAgent._extract_message({"message": "hello"}) == "hello"


def test_extract_message_strips_whitespace() -> None:
    assert LangGraphAgent._extract_message({"message": "   "}) == ""


def test_extract_message_missing_key() -> None:
    assert LangGraphAgent._extract_message({}) == ""


def test_extract_message_non_string_value() -> None:
    assert LangGraphAgent._extract_message({"message": 42}) == ""  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests: _final_text
# ---------------------------------------------------------------------------


def test_final_text_string_content() -> None:
    msg = AIMessage(content="hello world")
    assert LangGraphAgent._final_text([msg]) == "hello world"


def test_final_text_list_content() -> None:
    msg = AIMessage(content=[{"type": "text", "text": "part1"}, {"type": "text", "text": "part2"}])
    assert LangGraphAgent._final_text([msg]) == "part1part2"


def test_final_text_ignores_non_text_blocks() -> None:
    msg = AIMessage(content=[{"type": "reasoning", "text": "thinking"}, {"type": "text", "text": "answer"}])
    assert LangGraphAgent._final_text([msg]) == "answer"


def test_final_text_empty_messages() -> None:
    assert LangGraphAgent._final_text([]) == ""


def test_final_text_uses_last_ai_message() -> None:
    msg1 = AIMessage(content="first")
    msg2 = AIMessage(content="second")
    assert LangGraphAgent._final_text([msg1, msg2]) == "second"


# ---------------------------------------------------------------------------
# Tests: _collect_tool_calls
# ---------------------------------------------------------------------------


def test_collect_tool_calls_with_tool_calls() -> None:
    msg = AIMessage(content="")
    msg.tool_calls = [ToolCall(name="echo", args={"text": "hello"}, id=None, type="tool_call")]
    result = LangGraphAgent._collect_tool_calls([msg])
    assert result == [{"name": "echo", "args": {"text": "hello"}}]


def test_collect_tool_calls_no_tool_calls() -> None:
    msg = AIMessage(content="plain")
    assert LangGraphAgent._collect_tool_calls([msg]) == []


# ---------------------------------------------------------------------------
# Tests: handle()
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_handle_missing_message_returns_failed() -> None:
    agent = _make_agent()
    output: AgentResponse = await agent.handle(_make_request({}))
    assert output.status == "failed"
    assert output.error is not None
    assert "message" in output.error.lower()


@pytest.mark.anyio
async def test_handle_empty_message_returns_failed() -> None:
    agent = _make_agent()
    output: AgentResponse = await agent.handle(_make_request({"message": "   "}))
    assert output.status == "failed"


@pytest.mark.anyio
async def test_handle_success() -> None:
    agent = _make_agent()
    fake_result = _make_agent_result(reply="Hello LangGraph", tool_call_args={"text": "Hello LangGraph"})
    mock_compiled = AsyncMock()
    mock_compiled.ainvoke = AsyncMock(return_value=fake_result)

    with patch.object(agent, "_build_agent", return_value=mock_compiled):
        output: AgentResponse = await agent.handle(_make_request({"message": "Hello LangGraph"}))

    assert output.status == "succeeded"
    assert output.result is not None
    assert output.result["echo"] == "Hello LangGraph"
    assert output.result["reply"] == "Hello LangGraph"
    assert output.result["tool_calls"] == [{"name": "echo", "args": {"text": "Hello LangGraph"}}]


@pytest.mark.anyio
async def test_handle_llm_exception_returns_failed() -> None:
    agent = _make_agent()
    mock_compiled = AsyncMock()
    mock_compiled.ainvoke = AsyncMock(side_effect=RuntimeError("network error"))

    with patch.object(agent, "_build_agent", return_value=mock_compiled):
        output: AgentResponse = await agent.handle(_make_request({"message": "hello"}))

    assert output.status == "failed"
    assert output.error is not None
    assert "RuntimeError" in output.error
    assert "network error" in output.error


# ---------------------------------------------------------------------------
# Tests: agent_type
# ---------------------------------------------------------------------------


def test_agent_type_is_instance_attribute() -> None:
    """``agent_type`` is set per-instance so the same class can power multiple presets."""
    agent = _make_agent()
    assert agent.agent_type == AgentType.LANGGRAPH


# ---------------------------------------------------------------------------
# Tests: registry includes langgraph
# ---------------------------------------------------------------------------


def test_registry_includes_langgraph() -> None:
    """langgraph must be registered in the default AgentRegistry."""
    from concierge.agents.infrastructure.registry_factory import get_agent_registry

    get_agent_registry.cache_clear()
    registry = get_agent_registry()
    assert AgentType.LANGGRAPH in registry.list_agent_types()
