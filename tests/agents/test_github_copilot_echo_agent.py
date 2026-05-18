"""Unit tests for GitHubCopilotEchoAgent (shared agents package)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.agents.infrastructure.github_copilot_echo_agent import GitHubCopilotEchoAgent

_MODEL = "gpt-5"
_SYSTEM_PROMPT = "You are a minimal echo agent."


def _make_request(payload: dict[str, Any]) -> AgentRequest:
    return AgentRequest(
        agent_type="github-copilot-echo",
        payload=payload,
        context={"task_id": "00000000-0000-0000-0000-000000000001"},
    )


def test_extract_message_returns_message_string() -> None:
    agent = GitHubCopilotEchoAgent.__new__(GitHubCopilotEchoAgent)
    assert agent._extract_message({"message": "hello"}) == "hello"


def test_extract_message_strips_whitespace() -> None:
    agent = GitHubCopilotEchoAgent.__new__(GitHubCopilotEchoAgent)
    assert agent._extract_message({"message": "   "}) == ""


def test_extract_message_missing_key() -> None:
    agent = GitHubCopilotEchoAgent.__new__(GitHubCopilotEchoAgent)
    assert agent._extract_message({}) == ""


def test_extract_message_non_string_value() -> None:
    agent = GitHubCopilotEchoAgent.__new__(GitHubCopilotEchoAgent)
    assert agent._extract_message({"message": 42}) == ""  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_handle_success_returns_input_verbatim() -> None:
    agent = GitHubCopilotEchoAgent(model=_MODEL, system_prompt=_SYSTEM_PROMPT)

    mock_client_cm = AsyncMock()
    mock_client = AsyncMock()
    mock_session_cm = AsyncMock()
    mock_client_cm.__aenter__.return_value = mock_client
    mock_client.create_session = AsyncMock(return_value=mock_session_cm)
    mock_session_cm.__aenter__.return_value = mock_session_cm

    with patch.object(agent, "_build_client", return_value=mock_client_cm):
        request = _make_request({"message": "Hello Copilot"})
        output: AgentResponse = await agent.handle(request)

    assert output.status == "succeeded"
    assert output.result == {
        "echo": "Hello Copilot",
        "reply": "Hello Copilot",
        "client": {"initialized": True, "model": "gpt-5"},
    }
    assert output.error is None


@pytest.mark.anyio
async def test_handle_missing_message_returns_failed() -> None:
    agent = GitHubCopilotEchoAgent(model=_MODEL, system_prompt=_SYSTEM_PROMPT)

    output: AgentResponse = await agent.handle(_make_request({}))

    assert output.status == "failed"
    assert output.error == "payload.message is required (non-empty string)"


@pytest.mark.anyio
async def test_handle_sdk_initialization_error_returns_failed() -> None:
    agent = GitHubCopilotEchoAgent(model=_MODEL, system_prompt=_SYSTEM_PROMPT)

    with patch.object(agent, "_build_client", side_effect=RuntimeError("sdk init failed")):
        output: AgentResponse = await agent.handle(_make_request({"message": "hello"}))

    assert output.status == "failed"
    assert output.error == "RuntimeError: sdk init failed"


def test_registry_includes_github_copilot_echo() -> None:
    from concierge.agents.infrastructure.registry_factory import get_agent_registry

    get_agent_registry.cache_clear()
    registry = get_agent_registry()
    assert "github-copilot-echo" in registry.list_agent_types()
    assert "echo" in registry.list_agent_types()


def test_agent_type() -> None:
    assert GitHubCopilotEchoAgent.agent_type == "github-copilot-echo"
