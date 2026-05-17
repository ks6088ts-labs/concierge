"""Unit tests for LangGraphEchoAgent.

LLM calls are fully mocked; no Azure credentials or network access required.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from concierge.cloud_agent.application.agents import TaskInput, TaskOutput
from concierge.cloud_agent.infrastructure.agents.langgraph_echo_agent import LangGraphEchoAgent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_TASK_ID = "00000000-0000-0000-0000-000000000001"


def _make_task_input(payload: dict[str, Any]) -> TaskInput:
    import uuid

    return TaskInput(
        task_id=uuid.UUID(_FAKE_TASK_ID),
        agent_type="langgraph-echo",
        payload=payload,
    )


def _make_agent_result(reply: str, tool_call_name: str = "echo", tool_call_args: dict | None = None) -> dict:
    """Build a fake ``ainvoke`` result that mimics a LangGraph compiled graph output."""
    ai_msg = AIMessage(content=reply)
    ai_msg.tool_calls = [  # type: ignore[attr-defined]
        {"name": tool_call_name, "args": tool_call_args or {"text": reply}}
    ]
    return {"messages": [ai_msg]}


# ---------------------------------------------------------------------------
# Tests: _extract_message
# ---------------------------------------------------------------------------


def test_extract_message_returns_message_string() -> None:
    agent = LangGraphEchoAgent.__new__(LangGraphEchoAgent)
    assert agent._extract_message({"message": "hello"}) == "hello"


def test_extract_message_strips_whitespace() -> None:
    agent = LangGraphEchoAgent.__new__(LangGraphEchoAgent)
    # strip() must succeed → empty string → falsy
    assert agent._extract_message({"message": "   "}) == ""


def test_extract_message_missing_key() -> None:
    agent = LangGraphEchoAgent.__new__(LangGraphEchoAgent)
    assert agent._extract_message({}) == ""


def test_extract_message_non_string_value() -> None:
    agent = LangGraphEchoAgent.__new__(LangGraphEchoAgent)
    assert agent._extract_message({"message": 42}) == ""  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests: _final_text
# ---------------------------------------------------------------------------


def test_final_text_string_content() -> None:
    msg = AIMessage(content="hello world")
    assert LangGraphEchoAgent._final_text([msg]) == "hello world"


def test_final_text_list_content() -> None:
    msg = AIMessage(content=[{"type": "text", "text": "part1"}, {"type": "text", "text": "part2"}])
    assert LangGraphEchoAgent._final_text([msg]) == "part1part2"


def test_final_text_ignores_non_text_blocks() -> None:
    msg = AIMessage(content=[{"type": "reasoning", "text": "thinking"}, {"type": "text", "text": "answer"}])
    assert LangGraphEchoAgent._final_text([msg]) == "answer"


def test_final_text_empty_messages() -> None:
    assert LangGraphEchoAgent._final_text([]) == ""


def test_final_text_uses_last_ai_message() -> None:
    msg1 = AIMessage(content="first")
    msg2 = AIMessage(content="second")
    assert LangGraphEchoAgent._final_text([msg1, msg2]) == "second"


# ---------------------------------------------------------------------------
# Tests: _collect_tool_calls
# ---------------------------------------------------------------------------


def test_collect_tool_calls_with_tool_calls() -> None:
    msg = AIMessage(content="")
    msg.tool_calls = [{"name": "echo", "args": {"text": "hello"}}]  # type: ignore[attr-defined]
    result = LangGraphEchoAgent._collect_tool_calls([msg])
    assert result == [{"name": "echo", "args": {"text": "hello"}}]


def test_collect_tool_calls_no_tool_calls() -> None:
    msg = AIMessage(content="plain")
    assert LangGraphEchoAgent._collect_tool_calls([msg]) == []


# ---------------------------------------------------------------------------
# Tests: handle()
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_handle_missing_message_returns_failed() -> None:
    agent = LangGraphEchoAgent.__new__(LangGraphEchoAgent)
    agent._settings = MagicMock()  # type: ignore[attr-defined]

    task_input = _make_task_input({})
    output: TaskOutput = await agent.handle(task_input)

    assert output.status == "failed"
    assert output.error is not None
    assert "message" in output.error.lower()


@pytest.mark.anyio
async def test_handle_empty_message_returns_failed() -> None:
    agent = LangGraphEchoAgent.__new__(LangGraphEchoAgent)
    agent._settings = MagicMock()  # type: ignore[attr-defined]

    task_input = _make_task_input({"message": "   "})
    output: TaskOutput = await agent.handle(task_input)

    assert output.status == "failed"


@pytest.mark.anyio
async def test_handle_success() -> None:
    agent = LangGraphEchoAgent.__new__(LangGraphEchoAgent)
    agent._settings = MagicMock()  # type: ignore[attr-defined]

    fake_result = _make_agent_result(reply="Hello LangGraph", tool_call_args={"text": "Hello LangGraph"})
    mock_compiled = AsyncMock()
    mock_compiled.ainvoke = AsyncMock(return_value=fake_result)

    with patch.object(agent, "_build_agent", return_value=mock_compiled):
        task_input = _make_task_input({"message": "Hello LangGraph"})
        output: TaskOutput = await agent.handle(task_input)

    assert output.status == "succeeded"
    assert output.result is not None
    assert output.result["echo"] == "Hello LangGraph"
    assert output.result["reply"] == "Hello LangGraph"
    assert output.result["tool_calls"] == [{"name": "echo", "args": {"text": "Hello LangGraph"}}]


@pytest.mark.anyio
async def test_handle_llm_exception_returns_failed() -> None:
    agent = LangGraphEchoAgent.__new__(LangGraphEchoAgent)
    agent._settings = MagicMock()  # type: ignore[attr-defined]

    mock_compiled = AsyncMock()
    mock_compiled.ainvoke = AsyncMock(side_effect=RuntimeError("network error"))

    with patch.object(agent, "_build_agent", return_value=mock_compiled):
        task_input = _make_task_input({"message": "hello"})
        output: TaskOutput = await agent.handle(task_input)

    assert output.status == "failed"
    assert output.error is not None
    assert "RuntimeError" in output.error
    assert "network error" in output.error


# ---------------------------------------------------------------------------
# Tests: agent_type
# ---------------------------------------------------------------------------


def test_agent_type() -> None:
    assert LangGraphEchoAgent.agent_type == "langgraph-echo"


# ---------------------------------------------------------------------------
# Tests: registry includes langgraph-echo
# ---------------------------------------------------------------------------


def test_registry_includes_langgraph_echo() -> None:
    """langgraph-echo must be registered in the default AgentRegistry."""
    from concierge.cloud_agent.infrastructure.agents.registry import get_agent_registry

    # Clear lru_cache so we always get a fresh registry
    get_agent_registry.cache_clear()
    registry = get_agent_registry()
    assert "langgraph-echo" in registry.list_agent_types()
    assert "echo" in registry.list_agent_types()
