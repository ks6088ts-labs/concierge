"""Unit tests for the built-in EchoAgent (shared agents package).

The payload contract is intentionally aligned with LangGraphEchoAgent so the
same dispatch payload (``{"message": "..."}``) works for either agent.
"""

from __future__ import annotations

import pytest

from concierge.agents.application.contracts import AgentRequest
from concierge.agents.infrastructure.echo_agent import EchoAgent


def _make_request(payload: dict) -> AgentRequest:
    return AgentRequest(agent_type="echo", payload=payload, context={"task_id": "00000000-0000-0000-0000-000000000001"})


@pytest.mark.anyio
async def test_echo_agent_succeeds_on_message() -> None:
    agent = EchoAgent()
    output = await agent.handle(_make_request({"message": "hello"}))

    assert output.status == "succeeded"
    assert output.result == {"echo": "hello", "reply": "hello"}
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
