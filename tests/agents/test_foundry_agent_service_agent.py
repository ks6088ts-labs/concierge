"""Unit tests for FoundryAgentServiceAgent."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.foundry_agent_service_agent import FoundryAgentServiceAgent

_MODEL = "gpt-5"
_SYSTEM_PROMPT = "You are a helpful assistant."
_AGENT_NAME = "concierge-foundry-agent"
_ENDPOINT = "https://example.api.azureml.ms/api/projects/test"


def _make_request(payload: dict[str, Any]) -> AgentRequest:
    return AgentRequest(
        agent_type=AgentType.FOUNDRY_AGENT_SERVICE,
        payload=payload,
        context={"task_id": "00000000-0000-0000-0000-000000000001"},
    )


def _make_agent() -> FoundryAgentServiceAgent:
    return FoundryAgentServiceAgent(
        project_endpoint=_ENDPOINT,
        model=_MODEL,
        system_prompt=_SYSTEM_PROMPT,
        agent_name=_AGENT_NAME,
    )


def test_extract_message_returns_message_string() -> None:
    assert FoundryAgentServiceAgent._extract_message({"message": "hello"}) == "hello"


def test_extract_message_strips_whitespace() -> None:
    assert FoundryAgentServiceAgent._extract_message({"message": "   "}) == ""


def test_extract_message_missing_key() -> None:
    assert FoundryAgentServiceAgent._extract_message({}) == ""


def test_extract_message_non_string_value() -> None:
    assert FoundryAgentServiceAgent._extract_message({"message": 42}) == ""  # type: ignore[arg-type]


def test_agent_type_is_class_attribute() -> None:
    assert FoundryAgentServiceAgent.agent_type == AgentType.FOUNDRY_AGENT_SERVICE


@pytest.mark.anyio
async def test_handle_empty_message_returns_failed() -> None:
    agent = _make_agent()
    output: AgentResponse = await agent.handle(_make_request({}))
    assert output.status == "failed"
    assert output.error == "payload.message is required (non-empty string)"


@pytest.mark.anyio
async def test_handle_whitespace_message_returns_failed() -> None:
    agent = _make_agent()
    output: AgentResponse = await agent.handle(_make_request({"message": "   "}))
    assert output.status == "failed"
    assert output.error == "payload.message is required (non-empty string)"


@pytest.mark.anyio
async def test_handle_success_returns_reply() -> None:
    agent = _make_agent()

    mock_response = MagicMock()
    mock_response.output_text = "France is approximately 248,573 square miles."

    mock_conversation = MagicMock()
    mock_conversation.id = "conv-123"

    mock_openai = MagicMock()
    mock_openai.conversations.create.return_value = mock_conversation
    mock_openai.responses.create.return_value = mock_response

    mock_project = MagicMock()
    mock_project.get_openai_client.return_value = mock_openai

    with patch.object(agent, "_build_project_client", return_value=mock_project):
        output: AgentResponse = await agent.handle(
            _make_request({"message": "What is the size of France in square miles?"})
        )

    assert output.status == "succeeded"
    assert output.result is not None
    assert output.result["reply"] == "France is approximately 248,573 square miles."
    assert output.result["model"] == _MODEL
    assert output.result["agent_name"] == _AGENT_NAME
    assert output.result["message"] == "What is the size of France in square miles?"


@pytest.mark.anyio
async def test_handle_create_version_called_only_once() -> None:
    """create_version must be called on the first handle() and never again."""
    agent = _make_agent()

    mock_response = MagicMock()
    mock_response.output_text = "ok"

    mock_conversation = MagicMock()
    mock_conversation.id = "conv-456"

    mock_openai = MagicMock()
    mock_openai.conversations.create.return_value = mock_conversation
    mock_openai.responses.create.return_value = mock_response

    mock_project = MagicMock()
    mock_project.get_openai_client.return_value = mock_openai

    with patch.object(agent, "_build_project_client", return_value=mock_project):
        await agent.handle(_make_request({"message": "first call"}))
        await agent.handle(_make_request({"message": "second call"}))
        await agent.handle(_make_request({"message": "third call"}))

    mock_project.agents.create_version.assert_called_once()


@pytest.mark.anyio
async def test_handle_sdk_exception_returns_failed() -> None:
    agent = _make_agent()

    mock_project = MagicMock()
    mock_project.agents.create_version.side_effect = RuntimeError("SDK error")

    with patch.object(agent, "_build_project_client", return_value=mock_project):
        output: AgentResponse = await agent.handle(_make_request({"message": "hello"}))

    assert output.status == "failed"
    assert output.error is not None
    assert "RuntimeError" in output.error
    assert "SDK error" in output.error


@pytest.mark.anyio
async def test_handle_openai_exception_returns_failed() -> None:
    agent = _make_agent()

    mock_conversation = MagicMock()
    mock_conversation.id = "conv-789"

    mock_openai = MagicMock()
    mock_openai.conversations.create.return_value = mock_conversation
    mock_openai.responses.create.side_effect = ValueError("openai error")

    mock_project = MagicMock()
    mock_project.get_openai_client.return_value = mock_openai

    with patch.object(agent, "_build_project_client", return_value=mock_project):
        output: AgentResponse = await agent.handle(_make_request({"message": "hello"}))

    assert output.status == "failed"
    assert output.error is not None
    assert "ValueError" in output.error
    assert "openai error" in output.error


def test_registry_includes_foundry_agent_service() -> None:
    from concierge.agents.infrastructure.registry_factory import get_agent_registry

    get_agent_registry.cache_clear()
    registry = get_agent_registry()
    assert AgentType.FOUNDRY_AGENT_SERVICE in registry.list_agent_types()
