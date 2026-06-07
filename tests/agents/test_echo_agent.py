"""Unit tests for the built-in EchoAgent (shared agents package).

The payload contract is intentionally aligned with LangGraphAgent (echo preset) so the
same dispatch payload (``{"message": "..."}``) works for either agent.
"""

from __future__ import annotations

import pytest

from concierge.agents.application.contracts import AgentRequest
from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.echo_agent import EchoAgent


def _make_request(payload: dict) -> AgentRequest:
    return AgentRequest(
        agent_type=AgentType.ECHO,
        payload=payload,
        context={"task_id": "00000000-0000-0000-0000-000000000001"},
    )


@pytest.mark.anyio
async def test_echo_agent_succeeds_on_message() -> None:
    agent = EchoAgent()
    output = await agent.handle(_make_request({"message": "hello"}))

    assert output.status == "succeeded"
    assert output.result == {"message": "hello", "reply": "hello"}
    assert output.error is None


@pytest.mark.anyio
async def test_echo_agent_fails_when_message_missing() -> None:
    agent = EchoAgent()
    output = await agent.handle(_make_request({}))

    assert output.status == "failed"
    assert output.error == "payload.message is required (non-empty string)"


@pytest.mark.anyio
async def test_echo_agent_fails_when_message_empty() -> None:
    agent = EchoAgent()
    output = await agent.handle(_make_request({"message": "   "}))

    assert output.status == "failed"
    assert output.error == "payload.message is required (non-empty string)"


@pytest.mark.anyio
async def test_echo_agent_fails_when_message_not_string() -> None:
    agent = EchoAgent()
    output = await agent.handle(_make_request({"message": 42}))

    assert output.status == "failed"
    assert output.error == "payload.message is required (non-empty string)"


@pytest.mark.anyio
async def test_echo_agent_acknowledges_image_with_message() -> None:
    agent = EchoAgent()
    output = await agent.handle(
        _make_request({"message": "これは何?", "image_url": "data:image/png;base64,iVBORw0KGgo="})
    )

    assert output.status == "succeeded"
    assert output.result is not None
    assert "画像を受信しました" in output.result["reply"]
    assert output.result["reply"].startswith("これは何?")


@pytest.mark.anyio
async def test_echo_agent_succeeds_on_image_only() -> None:
    """An image with no text still succeeds (acknowledged), exercising the shared contract."""
    agent = EchoAgent()
    output = await agent.handle(_make_request({"image_url": "data:image/png;base64,iVBORw0KGgo="}))

    assert output.status == "succeeded"
    assert output.result is not None
    assert "画像を受信しました" in output.result["reply"]
